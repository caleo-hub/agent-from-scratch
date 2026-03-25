import asyncio
import hashlib
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import httpx
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.aio import SearchClient
from azure.search.documents.models import VectorizedQuery
from langchain.tools import tool


DEFAULT_CROSS_ENCODER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

DOCUMENT_GUIDE = """
Taxonomia dos documentos disponíveis:
- RFP (Request for Proposal): documento do cliente com necessidades, requisitos, escopo, SLA esperado, volumes e expectativas.
- Proposta Técnica: resposta do fornecedor explicando serviço será executado, incluindo abordagem, escopo proposto e modelo operacional.
- Proposta Comercial / Econômica: qualquer documento com preço, custo, valor total, valor mensal, pricing, FTE, planilhas econômicas ou dados financeiros de oferta.
- Anexos: documentos complementares com detalhes adicionais, referências externas ou informações críticas fora da RFP principal.
- Deal Review: documento interno de aprovação com análise da oportunidade, custos, margem, P&L, competitividade e estratégia.

Regras de classificação e prioridade:
- Se houver preço, custo ou valor, trate como Proposta Comercial, mesmo se o arquivo misturar outros conteúdos.
- Se a pergunta for sobre requisito, necessidade, escopo pedido pelo cliente, SLA ou volume, priorize RFP.
- Se a pergunta for sobre solução, execução, abordagem, operação, transição, staffing proposto ou entrega, priorize Proposta Técnica.
- Se a pergunta pedir complemento, detalhe escondido, material de apoio ou referência adicional, considere Anexos.
- Se a pergunta envolver aprovação interna, viabilidade financeira, margem, P&L, competitividade ou estratégia, priorize Deal Review.
- Um mesmo arquivo pode misturar tipos de conteúdo; planeje consultas capazes de localizar o tipo dominante para a necessidade do usuário.
"""


@dataclass
class RetrievedDoc:
    id: str
    source: str
    content: str
    score: float
    subquery: str
    rerank_score: float
    payload: dict[str, Any]


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def _safe_get_text(doc: dict[str, Any], keys: list[str], fallback: str = "") -> str:
    for key in keys:
        value = doc.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return fallback


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _split_components(question: str) -> list[str]:
    raw_parts = re.split(r",|\be\b|\bou\b|\bcom\b|\bpara\b", question, flags=re.IGNORECASE)
    cleaned = [_normalize_text(part).strip(".?!") for part in raw_parts if _normalize_text(part)]

    if not cleaned:
        return [question]

    unique: list[str] = []
    seen: set[str] = set()
    for item in cleaned:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)

    if len(unique) == 1:
        unique.append(f"detalhes sobre {unique[0]}")

    return unique[:4]


def _infer_doc_types(question: str, history: str) -> list[str]:
    haystack = f"{question} {history}".lower()
    inferred: list[str] = []

    hint_map = {
        "rfp": ["requisito", "necessidade", "sla", "volume", "escopo pedido", "rfp"],
        "proposta_tecnica": ["solucao", "execucao", "abordagem", "operacao", "transicao", "staffing"],
        "proposta_comercial": ["preco", "custo", "valor", "pricing", "fte", "economica"],
        "anexos": ["anexo", "complemento", "material de apoio", "referencia"],
        "deal_review": ["aprovacao interna", "viabilidade", "margem", "p&l", "competitividade", "estrategia"],
    }

    for doc_type, tokens in hint_map.items():
        if any(token in haystack for token in tokens):
            inferred.append(doc_type)

    seen: set[str] = set()
    deduped: list[str] = []
    for item in inferred:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _plan_queries(question: str, history: str = "") -> dict[str, Any]:
    corrected_question = _normalize_text(question).strip(" ?")
    components = _split_components(corrected_question)
    inferred_doc_types = _infer_doc_types(corrected_question, history)
    should_generate_paraphrases = len(corrected_question.split()) >= 4

    return {
        "corrected_question": corrected_question,
        "components": components[: max(2, min(4, len(components)))],
        "should_generate_paraphrases": should_generate_paraphrases,
        "inferred_doc_types": inferred_doc_types,
        "history_used": _normalize_text(history)[:1200],
        "document_guide": DOCUMENT_GUIDE,
    }


def _build_queries(plan: dict[str, Any], fanout: int) -> list[str]:
    corrected_question = str(plan.get("corrected_question", ""))
    components = [str(c) for c in plan.get("components", [])]
    inferred_doc_types = [str(d) for d in plan.get("inferred_doc_types", [])]
    should_generate_paraphrases = bool(plan.get("should_generate_paraphrases", False))

    queries: list[str] = []
    seen: set[str] = set()
    candidates: list[str] = [corrected_question]

    for component in components:
        candidates.append(component)
        if should_generate_paraphrases:
            candidates.append(f"resumo {component}")
            candidates.append(f"detalhes {component}")

    if inferred_doc_types:
        for component in components[:2]:
            candidates.append(f"{component} {' '.join(inferred_doc_types[:2])}")

    for candidate in candidates:
        normalized = candidate.strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        queries.append(normalized)
        if len(queries) >= fanout:
            break

    return queries


async def _embed_query(text: str) -> list[float] | None:
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    deployment = os.getenv("AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")

    if not endpoint or not api_key or not deployment:
        return None

    url = (
        f"{endpoint.rstrip('/')}/openai/deployments/{deployment}/embeddings"
        f"?api-version={api_version}"
    )
    payload = {"input": text}
    headers = {"Content-Type": "application/json", "api-key": api_key}

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        body = response.json()

    data = body.get("data", [])
    if not data:
        return None
    vector = data[0].get("embedding")
    if isinstance(vector, list) and vector:
        return [float(v) for v in vector]
    return None


def _row_to_doc(row: dict[str, Any], subquery: str) -> RetrievedDoc:
    content = _safe_get_text(
        row,
        ["content", "chunk", "text", "body", "summary", "metadata"],
    )
    source = _safe_get_text(
        row,
        [
            "source",
            "original_file_name",
            "original_document_name",
            "file_name",
            "name_hint",
            "relative_path",
            "blob_name",
            "id",
        ],
        fallback="unknown-source",
    )
    doc_id = _safe_get_text(row, ["id"], fallback=f"doc-{hash(source)}")
    score = float(row.get("@search.score", 0.0) or 0.0)

    return RetrievedDoc(
        id=doc_id,
        source=source,
        content=content,
        score=score,
        subquery=subquery,
        rerank_score=0.0,
        payload=row,
    )


async def _search_vector_only(
    endpoint: str,
    index_name: str,
    api_key: str,
    query: str,
    source_filter: str | None,
    top: int,
) -> list[RetrievedDoc]:
    vector = await _embed_query(query)
    if not vector:
        return []

    credential = AzureKeyCredential(api_key)
    client = SearchClient(endpoint=endpoint, index_name=index_name, credential=credential)

    filter_expr = None
    if source_filter:
        safe_source = source_filter.replace("'", "''")
        filter_expr = f"source eq '{safe_source}'"

    vector_query = VectorizedQuery(vector=vector, k=top, fields="content_vector")

    docs: list[RetrievedDoc] = []
    async with client:
        results = await client.search(
            search_text=None,
            vector_queries=[vector_query],
            filter=filter_expr,
            top=top,
        )
        async for row in results:
            if isinstance(row, dict):
                docs.append(_row_to_doc(row, query))
    return docs


async def _search_hybrid_fallback(
    endpoint: str,
    index_name: str,
    api_key: str,
    query: str,
    source_filter: str | None,
    top: int,
) -> list[RetrievedDoc]:
    vector = await _embed_query(query)
    credential = AzureKeyCredential(api_key)
    client = SearchClient(endpoint=endpoint, index_name=index_name, credential=credential)

    filter_expr = None
    if source_filter:
        safe_source = source_filter.replace("'", "''")
        filter_expr = f"source eq '{safe_source}'"

    vector_queries = None
    if vector:
        vector_queries = [
            VectorizedQuery(vector=vector, k=top, fields="content_vector")
        ]

    docs: list[RetrievedDoc] = []
    async with client:
        results = await client.search(
            search_text=query,
            vector_queries=vector_queries,
            filter=filter_expr,
            top=top,
        )
        async for row in results:
            if isinstance(row, dict):
                docs.append(_row_to_doc(row, query))
    return docs


def _lexical_score(query: str, content: str) -> float:
    query_terms = set(part.lower() for part in query.split() if len(part) > 2)
    content_terms = set(part.lower() for part in content.split() if len(part) > 2)
    if not query_terms:
        return 0.0
    overlap = len(query_terms.intersection(content_terms))
    return overlap / max(1, len(query_terms))


@lru_cache(maxsize=1)
def _get_cross_encoder_model():
    use_cross_encoder = _bool_env("RAG_ENABLE_CROSS_ENCODER", False)
    if not use_cross_encoder:
        return None

    model_name = os.getenv("RAG_CROSS_ENCODER_MODEL") or DEFAULT_CROSS_ENCODER_MODEL

    try:
        from sentence_transformers import CrossEncoder  # type: ignore

        return CrossEncoder(model_name)
    except Exception:
        return None


def _cross_encoder_like_score(query: str, content: str) -> float:
    model = _get_cross_encoder_model()
    if model is not None:
        try:
            score = model.predict([(query, content)])[0]
            return float(score)
        except Exception:
            pass
    return _lexical_score(query, content)


def _rerank_by_subquery(
    retrieved_by_query: dict[str, list[RetrievedDoc]],
    per_query_top_k: int,
) -> dict[str, list[RetrievedDoc]]:
    reranked: dict[str, list[RetrievedDoc]] = {}

    for subquery, docs in retrieved_by_query.items():
        scored: list[RetrievedDoc] = []
        for doc in docs:
            local_score = _cross_encoder_like_score(subquery, doc.content)
            final_score = (doc.score * 0.65) + (local_score * 0.35)
            doc.rerank_score = final_score
            scored.append(doc)

        reranked[subquery] = sorted(
            scored,
            key=lambda d: d.rerank_score,
            reverse=True,
        )[:per_query_top_k]

    return reranked


def _build_chunk_label(payload: dict[str, Any]) -> str:
    page = _safe_get_text(payload, ["page", "page_number", "pagina"])
    chunk_value = _safe_get_text(payload, ["chunk_index", "chunkId", "chunk_id", "chunk_number"])

    parts: list[str] = []
    if page:
        parts.append(f"pagina {page}")
    if chunk_value:
        parts.append(f"chunk {chunk_value}")

    return " · ".join(parts) if parts else "chunk nao identificado"


def _fix_azure_blob_url(url: str) -> str:
    """
    Fix malformed Azure Blob Storage URLs with SAS tokens.
    Ensures SAS token comes after the file path: blob.core.windows.net/container/path?sas_token
    """
    if not url or "blob.core.windows.net" not in url:
        return url

    # Check if URL has a SAS token (contains ?sv=)
    if "?sv=" not in url:
        return url

    # Split on the first ?sv= to separate base URL from SAS token part
    parts = url.split("?sv=", 1)
    if len(parts) != 2:
        return url

    base_part = parts[0]  # URL before ?sv=
    sas_part = parts[1]   # SAS token parameters and possibly more path

    # If there's a / in sas_part, it means path comes after SAS token (malformed)
    if "/" in sas_part:
        sas_split = sas_part.split("/", 1)
        if len(sas_split) == 2:
            sas_params = sas_split[0]  # sv=..&sig=..
            blob_path = sas_split[1]    # path/to/file.pdf
            # Reconstruct: container/path/to/file.pdf?sv=...&sig=...
            return f"{base_part}/{blob_path}?sv={sas_params}"

    return url


def _build_document_name(doc: RetrievedDoc) -> str:
    return _safe_get_text(
        doc.payload,
        [
            "original_document_name",
            "original_file_name",
            "file_name",
            "name_hint",
            "blob_name",
            "relative_path",
            "source",
        ],
        fallback=doc.source,
    )


def _merge_docs(
    question: str,
    reranked_by_query: dict[str, list[RetrievedDoc]],
    max_docs: int,
) -> tuple[str, list[dict[str, Any]], dict[str, int]]:
    merged: list[RetrievedDoc] = []
    dedupe_stats = {
        "by_id": 0,
        "by_source_page_chunk": 0,
        "by_content_hash": 0,
    }

    seen_id: set[str] = set()
    seen_source_page_chunk: set[str] = set()
    seen_content_hash: set[str] = set()

    for _, docs in reranked_by_query.items():
        for doc in docs:
            if doc.id and doc.id in seen_id:
                dedupe_stats["by_id"] += 1
                continue

            page = _safe_get_text(doc.payload, ["page", "page_number", "pagina"])
            chunk_index = _safe_get_text(doc.payload, ["chunk_index", "chunkId", "chunk_id"])
            spc_key = f"{doc.source}::{page}::{chunk_index}".lower().strip(":")

            if spc_key and spc_key != doc.source.lower() and spc_key in seen_source_page_chunk:
                dedupe_stats["by_source_page_chunk"] += 1
                continue

            content_hash = hashlib.md5(doc.content.encode("utf-8")).hexdigest()
            if content_hash in seen_content_hash:
                dedupe_stats["by_content_hash"] += 1
                continue

            if doc.id:
                seen_id.add(doc.id)
            if spc_key:
                seen_source_page_chunk.add(spc_key)
            seen_content_hash.add(content_hash)

            merged.append(doc)
            if len(merged) >= max_docs:
                break
        if len(merged) >= max_docs:
            break

    context_lines = [f"Pergunta do usuário: {question}", "", "Contexto recuperado:"]
    sources: list[dict[str, Any]] = []

    for idx, doc in enumerate(merged, start=1):
        snippet = (doc.content or "").replace("\n", " ").strip()
        snippet = snippet[:360] + ("..." if len(snippet) > 360 else "")
        context_lines.append(f"[{idx}] Fonte: {doc.source}")
        context_lines.append(f"[{idx}] Conteúdo: {snippet}")
        context_lines.append("")

        document_name = _build_document_name(doc)
        chunk_label = _build_chunk_label(doc.payload)

        source_url = _safe_get_text(
            doc.payload,
            ["source_url", "url", "uri", "blob_url", "file_url"],
        )
        if not source_url and doc.source.startswith("http"):
            source_url = doc.source
        
        # Fix malformed Azure Blob URLs with SAS tokens
        source_url = _fix_azure_blob_url(source_url)

        sources.append(
            {
                "rank": idx,
                "source": doc.source,
                "document_name": document_name,
                "source_url": source_url,
                "id": doc.id,
                "score": round(doc.score, 4),
                "rerank_score": round(doc.rerank_score, 4),
                "subquery": doc.subquery,
                "snippet": snippet,
                "chunk": {
                    "label": chunk_label,
                    "page": _safe_get_text(doc.payload, ["page", "page_number", "pagina"]),
                    "index": _safe_get_text(
                        doc.payload,
                        ["chunk_index", "chunkId", "chunk_id", "chunk_number"],
                    ),
                },
                "tooltip": f"Documento: {document_name} | Trecho: {chunk_label}",
                "metadata": {
                    key: value
                    for key, value in doc.payload.items()
                    if key
                    in {
                        "document_type",
                        "customer",
                        "service_requested",
                        "file_name",
                        "relative_path",
                        "folder_name",
                    }
                },
            }
        )

    return "\n".join(context_lines).strip(), sources, dedupe_stats


@tool
def agentic_rag(
    query: str,
    history: str = "",
    fanout: int = 4,
    top_k: int = 10,
    source_filter: str = "",
) -> str:
    """
    Agentic RAG sobre Azure AI Search.

    Substeps internos:
    - plan_queries
    - build_queries
    - retrieve_fanout
    - rerank
    - merge_docs

    Estratégia de retrieval:
    - Base: vector search pelo Azure Search SDK
    - Fallback opcional: hybrid search (texto + vetor) via env RAG_ENABLE_HYBRID_FALLBACK

    Cross-encoder:
    - Desligado por padrão
    - Para habilitar: RAG_ENABLE_CROSS_ENCODER=true
    - Modelo: RAG_CROSS_ENCODER_MODEL (default pronto: cross-encoder/ms-marco-MiniLM-L-6-v2)
    """

    endpoint = _required_env("AZURE_AI_SEARCH_ENDPOINT")
    api_key = _required_env("AZURE_AI_SEARCH_ADMIN_KEY")
    index_name = _required_env("AZURE_AI_SEARCH_INDEX_NAME")

    fanout = max(2, min(fanout, 8))
    top_k = max(1, min(top_k, 20))
    source_filter = _normalize_text(source_filter)

    plan = _plan_queries(query, history)
    built_queries = _build_queries(plan, fanout)

    enable_hybrid_fallback = _bool_env("RAG_ENABLE_HYBRID_FALLBACK", False)

    async def _retrieve_one(subquery: str, per_query_top: int) -> tuple[str, list[RetrievedDoc], str]:
        vector_docs = await _search_vector_only(
            endpoint=endpoint,
            index_name=index_name,
            api_key=api_key,
            query=subquery,
            source_filter=source_filter or None,
            top=per_query_top,
        )
        if vector_docs:
            return subquery, vector_docs, "vector_only"

        if enable_hybrid_fallback:
            hybrid_docs = await _search_hybrid_fallback(
                endpoint=endpoint,
                index_name=index_name,
                api_key=api_key,
                query=subquery,
                source_filter=source_filter or None,
                top=per_query_top,
            )
            return subquery, hybrid_docs, "hybrid_fallback"

        return subquery, [], "vector_only"

    async def _run() -> dict[str, Any]:
        per_query_top = max(3, min(8, top_k))
        tasks = [_retrieve_one(q, per_query_top) for q in built_queries]
        retrieval_results = await asyncio.gather(*tasks)

        retrieved_by_query: dict[str, list[RetrievedDoc]] = {}
        retrieve_mode_by_query: dict[str, str] = {}
        for subquery, docs, mode in retrieval_results:
            retrieved_by_query[subquery] = docs
            retrieve_mode_by_query[subquery] = mode

        reranked_by_query = _rerank_by_subquery(
            retrieved_by_query=retrieved_by_query,
            per_query_top_k=max(2, min(6, top_k)),
        )

        context, sources, dedupe_stats = _merge_docs(
            question=query,
            reranked_by_query=reranked_by_query,
            max_docs=top_k,
        )

        flat_docs = [doc for docs in retrieved_by_query.values() for doc in docs]
        reranked_flat = [doc for docs in reranked_by_query.values() for doc in docs]

        artifacts = [
            {
                "type": "document_sources",
                "title": "Fontes utilizadas",
                "collapsible": True,
                "show_only_when_complete": True,
                "items": [
                    {
                        "rank": source.get("rank"),
                        "document_name": source.get("document_name") or source.get("source"),
                        "source_label": source.get("source"),
                        "source_url": source.get("source_url"),
                        "chunk": source.get("chunk"),
                        "tooltip": source.get("tooltip"),
                        "doc_type": str(
                            (source.get("metadata") or {}).get("document_type") or ""
                        ).strip(),
                        "snippet": source.get("snippet"),
                        "score": source.get("score"),
                        "rerank_score": source.get("rerank_score"),
                    }
                    for source in sources
                ],
            }
        ]

        return {
            "schema_version": "1.0",
            "query": query,
            "substeps": [
                "plan_queries",
                "build_queries",
                "retrieve_fanout",
                "rerank",
                "merge_docs",
            ],
            "context": context,
            "sources": sources,
            "artifacts": artifacts,
            "ui": {
                "accordion_title": "Fontes utilizadas na resposta",
                "empty_state": "Nenhuma fonte estruturada foi retornada.",
                "show_sources_only_when_complete": True,
            },
            "trace": {
                "plan": plan,
                "queries_planned": [plan.get("corrected_question", ""), *plan.get("components", [])],
                "queries_built": built_queries,
                "retrieve_counts": {k: len(v) for k, v in retrieved_by_query.items()},
                "retrieve_mode_by_query": retrieve_mode_by_query,
                "total_retrieved": len(flat_docs),
                "total_after_rerank": len(reranked_flat),
                "dedupe_stats": dedupe_stats,
                "rerank_strategy": (
                    "cross_encoder" if _get_cross_encoder_model() is not None else "lexical_fallback"
                ),
                "cross_encoder_default_model": DEFAULT_CROSS_ENCODER_MODEL,
                "cross_encoder_enabled": _bool_env("RAG_ENABLE_CROSS_ENCODER", False),
                "hybrid_fallback_enabled": enable_hybrid_fallback,
                "source_filter": source_filter,
            },
            "document_guide": DOCUMENT_GUIDE,
            "usage_instructions": (
                "Responda usando prioritariamente o campo context e cite as fontes pelo campo sources."
            ),
        }

    result = asyncio.run(_run())
    return result
