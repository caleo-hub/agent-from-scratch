# MCP Multi-Server Client Setup

Este documento explica como o agent se conecta a múltiplos servidores MCP hospedados na internet.

## Arquitetura

```
┌─────────────────────┐
│   Agent (Python)    │
│  (MCP Client)       │
└──────────┬──────────┘
           │ HTTP Requests
           ├─────────────────────────────────────┬──────────────────┬──────────────┐
           ↓                                     ↓                  ↓              ↓
     ┌──────────────┐                   ┌──────────────┐    ┌────────────┐ ┌────────────┐
     │  Exa AI      │                   │ Brave Search │    │ Perplexity │ │  Tavily    │
     │ MCP Server   │                   │ MCP Server   │    │ MCP Server │ │ MCP Server │
     └──────────────┘                   └──────────────┘    └────────────┘ └────────────┘
  https://mcp.exa.ai                https://brave.com    https://perp.ai  https://tavily
```

## Servidores Pré-Configurados

| Servidor | URL | Variável de Ambiente | Status |
|----------|-----|----------------------|--------|
| **Exa AI** | `https://mcp.exa.ai/mcp` | `EXA_API_KEY` | ✅ Ativo |
| **Brave Search** | `https://api.search.brave.com/mcp` | `BRAVE_API_KEY` | ⏸️ Inativo |
| **Perplexity** | `https://api.perplexity.ai/mcp` | `PERPLEXITY_API_KEY` | ⏸️ Inativo |
| **Tavily** | `https://api.tavily.com/mcp` | `TAVILY_API_KEY` | ⏸️ Inativo |

## Como Usar

### 1. Configurar API Keys (`.env`)

```env
# Servidores MCP
EXA_API_KEY="sua-chave-exa"
BRAVE_API_KEY="sua-chave-brave"
PERPLEXITY_API_KEY="sua-chave-perplexity"
TAVILY_API_KEY="sua-chave-tavily"
```

### 2. Iniciar o Agent

```bash
pnpm dev
```

O agent detectará automaticamente quais servidores têm API keys válidas e se conectará a eles.

### 3. Usar as Ferramentas

```
User: "Pesquise sobre o React 19 na web"

Agent:
1. Identifica a necessidade de busca web
2. Usa `exa__web_search_advanced_exa` ou `brave__brave_web_search`
3. Retorna resultados frescos do Exa AI / Brave Search
```

## Como Adicionar Novo Servidor MCP

### Opção 1: Servidor Pré-Configurado

Se o servidor já está na lista em `MCPServerConfig.SERVERS`, basta adicionar a API key:

```env
# .env
MEU_NOVO_SERVIDOR_API_KEY="sua-chave"
```

### Opção 2: Servidor Customizado (Runtime)

```python
# No seu código ou script
from src.mcp_client import mcp_client

mcp_client.add_custom_server(
    server_name="meu_servidor",
    url="https://api.meu-servidor.com/mcp",
    tools=["ferramenta1", "ferramenta2", "ferramenta3"],
    api_key="sua-chave-api",
    description="Seu servidor MCP customizado"
)
```

### Opção 3: Adicionar Novo Servidor Pré-Configurado

Em `src/mcp_client.py`, adicione à classe `MCPServerConfig`:

```python
class MCPServerConfig:
    SERVERS = {
        # ... existentes ...
        "novo_servidor": {
            "url": "https://api.novo-servidor.com/mcp",
            "api_key_env": "NOVO_SERVIDOR_API_KEY",
            "description": "Descricao do novo servidor",
            "tools": ["tool1", "tool2", "tool3"]
        }
    }
```

Depois adicione no `.env`:

```env
NOVO_SERVIDOR_API_KEY="sua-chave"
```

## Listar Servidores e Ferramentas Conectados

```python
from src.mcp_client import mcp_client

# Ver servidores conectados
print(mcp_client.list_servers())
# ['exa', 'brave']

# Ver ferramentas disponíveis
print(mcp_client.list_tools())
# {
#   'exa': ['web_search_advanced_exa', 'get_code_context_exa'],
#   'brave': ['brave_web_search', 'brave_local_search']
# }
```

## Nomes das Ferramentas Dinâmicas

Ferramentas MCP são registradas com o padrão: `{servidor}__{ferramenta}`

**Exemplos:**
- `exa__web_search_advanced_exa` - Busca web Exa AI
- `exa__get_code_context_exa` - Contexto de código Exa AI
- `brave__brave_web_search` - Busca web Brave
- `tavily__tavily_search` - Busca Tavily

## Estrutura de Código

```python
# src/mcp_client.py

class MCPClient:
    """Cliente HTTP para chamar servidores MCP"""
    
    def _register_server(server_name, config):
        """Registra um servidor MCP"""
        
    def _create_server_tools(server_name, config):
        """Cria ferramentas LangChain dinamicamente"""
        
    def add_custom_server(server_name, url, tools, api_key):
        """Adiciona servidor customizado em runtime"""
        
    def list_servers():
        """Retorna lista de servidores conectados"""
        
    def list_tools():
        """Retorna todas as ferramentas por servidor"""
```

## Tratamento de Erros

Se uma ferramenta falhar:

```
Erro esperado:
{
  "error": "Failed to call tool",
  "server": "exa",
  "tool": "web_search_advanced_exa"
}
```

**Causas comuns:**
- API key inválida ou expirada
- Limite de requisições atingido
- Servidor indisponível
- Parâmetros inválidos

## Performance

- ✅ Requisições HTTP são assíncronas (timeout: 30s)
- ✅ Múltiplos servidores podem ser chamados em paralelo
- ✅ Ferramentas são criadas dinamicamente (baixa overhead)
- ✅ Conexões reutilizadas via httpx.AsyncClient

## Roadmap

- [ ] Cache de resultados
- [ ] Retry automático com backoff
- [ ] Rate limiting por servidor
- [ ] Suporte para websockets
- [ ] Streaming de resultados

## Referências

- [MCP Spec](https://modelcontextprotocol.io/)
- [Exa AI Docs](https://exa.ai/docs)
- [Brave Search API](https://api.search.brave.com/)
- [Perplexity AI](https://www.perplexity.ai/)
- [Tavily Search API](https://tavily.com/)

