"use client";

import { useEffect, useRef } from "react";

interface ToolReasoningProps {
  name: string;
  args?: object | unknown;
  status: string;
}

export interface AgenticRagResult {
  schema_version?: string;
  query?: string;
  context?: string;
  substeps?: string[];
  sources?: Array<{
    rank?: number;
    source?: string;
    document_name?: string;
    source_url?: string;
    id?: string;
    score?: number;
    rerank_score?: number;
    subquery?: string;
    snippet?: string;
    tooltip?: string;
    chunk?: {
      label?: string;
      page?: string;
      index?: string;
    };
    metadata?: Record<string, unknown>;
  }>;
  artifacts?: Array<{
    type?: string;
    title?: string;
    collapsible?: boolean;
    show_only_when_complete?: boolean;
    items?: Array<{
      rank?: number;
      document_name?: string;
      source_label?: string;
      source_url?: string;
      doc_type?: string;
      tooltip?: string;
      snippet?: string;
      score?: number;
      rerank_score?: number;
      chunk?: {
        label?: string;
        page?: string;
        index?: string;
      };
    }>;
  }>;
  ui?: {
    accordion_title?: string;
    empty_state?: string;
    show_sources_only_when_complete?: boolean;
  };
  trace?: {
    total_retrieved?: number;
    total_after_rerank?: number;
    queries_planned?: string[];
    queries_built?: string[];
    retrieve_counts?: Record<string, number>;
    retrieve_mode_by_query?: Record<string, string>;
    rerank_strategy?: string;
  };
}

const statusIndicator = {
  executing: (
    <span className="inline-block h-3 w-3 rounded-full border-2 border-gray-400 border-t-transparent animate-spin" />
  ),
  inProgress: (
    <span className="inline-block h-3 w-3 rounded-full border-2 border-gray-400 border-t-transparent animate-spin" />
  ),
  complete: <span className="text-green-500 text-xs">✓</span>,
};

function formatValue(value: unknown): string {
  if (Array.isArray(value)) return `[${value.length} items]`;
  if (typeof value === "object" && value !== null)
    return `{${Object.keys(value).length} keys}`;
  if (typeof value === "string") return `"${value}"`;
  return String(value);
}

export function ToolReasoning({ name, args, status }: ToolReasoningProps) {
  const entries = args ? Object.entries(args) : [];
  const detailsRef = useRef<HTMLDetailsElement>(null);
  const toolStatus = status as "complete" | "inProgress" | "executing";

  // Auto-open while executing, auto-close when complete
  useEffect(() => {
    if (!detailsRef.current) return;
    detailsRef.current.open = status === "executing";
  }, [status]);

  return (
    <div className="my-2 text-sm">
      {entries.length > 0 ? (
        <details ref={detailsRef} open>
          <summary className="flex items-center gap-2 text-gray-600 dark:text-gray-400 cursor-pointer list-none">
            {statusIndicator[toolStatus]}
            <span className="font-medium">{name}</span>
            <span className="text-[10px]">▼</span>
          </summary>
          <div className="pl-5 mt-1 space-y-1 text-xs text-gray-500 dark:text-zinc-400">
            {entries.map(([key, value]) => (
              <div key={key} className="flex gap-2 min-w-0">
                <span className="font-medium shrink-0">{key}:</span>
                <span className="text-gray-600 dark:text-gray-400 truncate">
                  {formatValue(value)}
                </span>
              </div>
            ))}
          </div>
        </details>
      ) : (
        <div className="flex items-center gap-2 text-gray-600 dark:text-gray-400">
          {statusIndicator[toolStatus]}
          <span className="font-medium">{name}</span>
        </div>
      )}
    </div>
  );
}

const ragSteps = [
  "plan_queries",
  "build_queries",
  "retrieve_fanout",
  "rerank",
  "merge_docs",
];

function titleize(step: string) {
  return step.replaceAll("_", " ");
}

const DOC_TYPE_ICON: Record<string, string> = {
  rfp: "📋",
  proposta_tecnica: "🔧",
  proposta_comercial: "💰",
  deal_review: "📊",
  anexos: "📎",
};

function normalizeDocType(docType?: string) {
  return (docType || "").trim().toLowerCase().replaceAll(" ", "_");
}

function getDocTypeIcon(docType?: string) {
  return DOC_TYPE_ICON[normalizeDocType(docType)] || "📄";
}

export function AgenticRagToolCard({
  status,
  result,
}: {
  status: string;
  result?: AgenticRagResult;
}) {
  const isComplete = status === "complete";
  
  // Parse result if it's a string (JSON) — LangGraph can return serialized objects
  let parsedResult = result;
  if (typeof result === 'string') {
    try {
      parsedResult = JSON.parse(result);
    } catch (e) {
      console.error('[AgenticRagToolCard] Failed to parse result as JSON:', e);
    }
  }
  
  const documentSources = parsedResult?.artifacts?.find(
    (artifact) => artifact.type === "document_sources",
  );
  const sources = documentSources?.items || [];
  const accordionTitle =
    parsedResult?.ui?.accordion_title || documentSources?.title || "Fontes utilizadas";
  const emptyState =
    parsedResult?.ui?.empty_state || "Nenhuma fonte estruturada foi retornada.";
  const showOnlyWhenComplete = parsedResult?.ui?.show_sources_only_when_complete !== false;
  const shouldShowSources = isComplete || !showOnlyWhenComplete;
  const totalRetrieved = (parsedResult as any)?.trace?.total_retrieved;
  const totalAfterRerank = (parsedResult as any)?.trace?.total_after_rerank;
  const queriesPlanned = parsedResult?.trace?.queries_planned || [];
  const queriesBuilt = parsedResult?.trace?.queries_built || [];
  const retrieveCounts = parsedResult?.trace?.retrieve_counts || {};
  const retrieveModes = parsedResult?.trace?.retrieve_mode_by_query || {};
  const rerankStrategy = parsedResult?.trace?.rerank_strategy;

  return (
    <section
      className="my-3 rounded-lg border border-zinc-200 bg-zinc-50 p-3 dark:border-zinc-700 dark:bg-zinc-900"
      aria-live="polite"
      aria-label="Execucao da ferramenta de busca documental"
    >
      <header className="mb-2 flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-zinc-800 dark:text-zinc-100">
          Agentic RAG
        </h3>
        <span
          className={`text-xs ${
            isComplete ? "text-emerald-600" : "text-amber-600"
          }`}
        >
          {isComplete ? "concluido" : "executando"}
        </span>
      </header>

      <ol className="mb-3 space-y-1 text-xs text-zinc-600 dark:text-zinc-300" aria-label="Subetapas">
        {ragSteps.map((step) => (
          <li key={step} className="flex items-center gap-2">
            <span
              className={`inline-block h-2.5 w-2.5 rounded-full ${
                isComplete ? "bg-emerald-500" : "bg-amber-500"
              }`}
              aria-hidden
            />
            <span>{titleize(step)}</span>
          </li>
        ))}
      </ol>

      {result?.query ? (
        <p className="mb-2 text-xs text-zinc-700 dark:text-zinc-200">
          <strong>Pergunta:</strong> {result.query}
        </p>
      ) : null}

      {typeof totalRetrieved === "number" ? (
        <p className="mb-2 text-xs text-zinc-700 dark:text-zinc-200">
          <strong>Documentos recuperados:</strong> {totalRetrieved}
          {typeof totalAfterRerank === "number"
            ? ` | apos rerank: ${totalAfterRerank}`
            : ""}
        </p>
      ) : null}

      {queriesBuilt.length > 0 ? (
        <details className="mb-3 rounded-md border border-zinc-200 bg-white dark:border-zinc-700 dark:bg-zinc-950">
          <summary className="cursor-pointer list-none px-3 py-2 text-xs font-semibold text-zinc-800 dark:text-zinc-100">
            Subqueries usadas na busca ({queriesBuilt.length})
          </summary>
          <div className="space-y-2 px-3 pb-3">
            {queriesBuilt.map((query, idx) => {
              const count = retrieveCounts?.[query] ?? 0;
              const mode = retrieveModes?.[query] || "vector_only";
              return (
                <div
                  key={`${query}-${idx}`}
                  className="rounded border border-zinc-200 bg-zinc-50 px-2 py-1.5 dark:border-zinc-700 dark:bg-zinc-900"
                >
                  <p className="text-[11px] font-medium text-zinc-800 dark:text-zinc-100">
                    {idx + 1}. {query}
                  </p>
                  <p className="mt-1 text-[11px] text-zinc-500 dark:text-zinc-400">
                    resultados: {count} | modo: {mode}
                  </p>
                </div>
              );
            })}
            {queriesPlanned.length > 0 ? (
              <p className="text-[11px] text-zinc-500 dark:text-zinc-400">
                planejadas: {queriesPlanned.length} | rerank: {rerankStrategy || "n/a"}
              </p>
            ) : null}
          </div>
        </details>
      ) : null}

      {!isComplete ? (
        <p className="text-xs text-zinc-500 dark:text-zinc-400">
          As fontes estruturadas serao exibidas ao final da resposta.
        </p>
      ) : null}

      {shouldShowSources ? (
        <div>
          <details className="rounded-md border border-zinc-200 bg-white dark:border-zinc-700 dark:bg-zinc-950">
            <summary className="cursor-pointer list-none px-3 py-2 text-xs font-semibold text-zinc-800 dark:text-zinc-100">
              {accordionTitle}
            </summary>

            {sources.length > 0 ? (
              <ul className="space-y-2 px-3 pb-3" aria-label={accordionTitle}>
                {sources.map((source, idx) => {
                  const chunkLabel = source.chunk?.label || "chunk nao identificado";
                  const documentName = source.document_name || source.source_label || "Fonte sem nome";
                  const tooltip =
                    source.tooltip || `Documento: ${documentName} | Trecho: ${chunkLabel}`;

                  return (
                    <li
                      key={`${documentName}-${idx}`}
                      className="rounded-md border border-zinc-200 bg-zinc-50 p-2 dark:border-zinc-700 dark:bg-zinc-900"
                      title={tooltip}
                    >
                      <div className="flex items-start gap-2">
                        <span className="text-sm leading-none" aria-hidden>
                          {getDocTypeIcon(source.doc_type)}
                        </span>
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <span className="text-[11px] text-zinc-500 dark:text-zinc-400">
                              {source.rank || idx + 1}.
                            </span>
                            {source.source_url ? (
                              <a
                                href={source.source_url}
                                target="_blank"
                                rel="noreferrer"
                                className="truncate text-xs font-medium text-blue-600 underline underline-offset-2 dark:text-blue-400"
                                title={tooltip}
                              >
                                {documentName}
                              </a>
                            ) : (
                              <span className="truncate text-xs font-medium text-zinc-800 dark:text-zinc-100">
                                {documentName}
                              </span>
                            )}
                          </div>
                          <p className="mt-1 text-[11px] text-zinc-500 dark:text-zinc-400">
                            {chunkLabel}
                            {source.source_label ? ` | fonte: ${source.source_label}` : ""}
                          </p>
                          {source.snippet ? (
                            <p className="mt-1 line-clamp-2 text-[11px] text-zinc-600 dark:text-zinc-300">
                              {source.snippet}
                            </p>
                          ) : null}
                        </div>
                      </div>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p className="px-3 pb-3 text-xs text-zinc-500 dark:text-zinc-400">
                {emptyState}
              </p>
            )}
          </details>
        </div>
      ) : null}
    </section>
  );
}
