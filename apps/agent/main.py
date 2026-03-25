"""
This is the main entry point for the agent.
It defines the workflow graph, state, tools, nodes and edges.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from root of project
root_dir = Path(__file__).parent.parent.parent
env_file = root_dir / ".env"
if env_file.exists():
    load_dotenv(env_file)

from copilotkit import CopilotKitMiddleware
from langchain.agents import create_agent
from langchain_openai import AzureChatOpenAI

from src.query import query_data
from src.todos import AgentState, todo_tools, upload_tools
from src.form import generate_form
from src.mcp_client import mcp_client, mcp_tools
from src.agentic_rag import agentic_rag

llm = AzureChatOpenAI(
    azure_deployment="gpt-5-chat",  
    api_version="2024-08-01-preview", 
)

# Build tools list with MCP tools
all_tools = [
    query_data,
    agentic_rag,
    *todo_tools,
    *upload_tools,
    generate_form,
    *mcp_tools,
]

# Log connected MCP servers
connected_servers = mcp_client.list_servers()
servers_str = ", ".join(connected_servers) if connected_servers else "none"

agent = create_agent(
    model=llm,
    tools=all_tools,
    middleware=[CopilotKitMiddleware()],
    state_schema=AgentState,
    system_prompt=f"""
        Você é um agente especialista em análise comercial e técnica de documentos de pré-venda.

        Objetivo principal:
        - analisar RFPs, propostas técnicas, propostas econômicas/comerciais e documentos de venda;
        - comparar oportunidades e propostas anteriores;
        - apoiar estratégia de oferta e price-to-win com base em evidências documentais.

        Diretrizes de atuação:
        - para arquivos anexados na conversa atual (PDF/DOCX/TXT), use get_uploaded_documents e analise via state da conversa, sem depender de vector DB;
        - para perguntas que dependem de base histórica já indexada fora da conversa atual, use agentic_rag;
        - quando o usuário mencionar arquivos anexados, PDFs/DOCX/TXT enviados no chat, use get_uploaded_documents para recuperar o conteúdo salvo no state da conversa antes de responder;
        - use o contexto e as fontes retornadas pelo agentic_rag para sustentar conclusões;
        - explicite premissas, riscos, lacunas de informação e impactos comerciais;
        - quando houver dados suficientes, recomende posicionamento de oferta (mais agressivo, neutro, premium) com justificativa;
        - ao comparar propostas, destaque diferenças de escopo, preço, modelo operacional, SLAs e riscos.

        Uso de ferramentas:
        - get_uploaded_documents: use para ler os documentos anexados no state da conversa;
        - query_data: usar antes de gráficos e análises quantitativas no canvas;
        - agentic_rag: ferramenta prioritária para grounding em documentos indexados;
        - ferramentas MCP: use para pesquisa complementar e enriquecimento externo quando necessário.

        Servidores MCP disponíveis:
        - {servers_str}

        Estilo de resposta:
        - responda em português claro e objetivo;
        - seja executivo, mas com profundidade analítica quando necessário;
        - sempre que possível, organize a resposta em: síntese, achados, riscos, recomendação e fontes.

    """,
)

graph = agent
