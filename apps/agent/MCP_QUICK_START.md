# MCP Multi-Server Integration - Guia Rápido

## O Que Foi Implementado?

Um **cliente MCP (Model Context Protocol)** completamente funcional que permite ao seu agent se conectar a **múltiplos servidores MCP hospedados na internet** para usar suas ferramentas.

```
Agent Python ──HTTP──> Exa AI MCP Server
           ──────────> Brave Search MCP Server
           ──────────> Perplexity MCP Server
           ──────────> Tavily MCP Server
           ──────────> Custom MCP Servers
```

## Arquivos Modificados/Criados

✅ **`src/mcp_client.py`** - Cliente MCP com suporte a múltiplos servidores
✅ **`main.py`** - Integração das ferramentas MCP no agent
✅ **`pyproject.toml`** - Dependências (mcp, httpx)
✅ **`.env`** - API keys para servidores MCP
✅ **`MCP_SETUP.md`** - Documentação completa
✅ **`MCP_QUICK_START.md`** - Este arquivo (guia rápido)

## Começar Rapidamente

### 1. Ativar Servidor Exa (Recomendado)

A chave Exa já está no `.env`:

```env
EXA_API_KEY="2dd83ced-e1c7-4b92-bc5d-727feca770fb"
```

### 2. Iniciar Agent

```bash
pnpm dev

# Saída esperada:
# ✓ Registered MCP server: exa
# ✓ Connected servers: ['exa']
```

### 3. Testar no Chat

```
User: "Pesquise sobre inteligência artificial em 2025"

Agent:
1. Detecta necessidade de busca
2. Chama exa__web_search_advanced_exa
3. Retorna resultados frescos da web
```

## Adicionar Novos Servidores

### Opção Rápida (1 minuto)

**Crie chaves de API em:**
- Brave Search: https://api.search.brave.com/
- Perplexity AI: https://www.perplexity.ai/
- Tavily Search: https://tavily.com/

**Adicione ao `.env`:**

```env
BRAVE_API_KEY="sua-chave-brave"
PERPLEXITY_API_KEY="sua-chave-perplexity"
TAVILY_API_KEY="sua-chave-tavily"
```

**Reinicie:**

```bash
pnpm dev
```

✅ Pronto! Agent automaticamente conecta aos 4 servidores.

### Opção Avançada (Custom Servers)

```python
from src.mcp_client import mcp_client

# Adicionar em runtime
mcp_client.add_custom_server(
    server_name="meu_mcp",
    url="https://meu-servidor.com/mcp",
    tools=["ferramenta1", "ferramenta2"],
    api_key="sua-api-key",
    description="Meu servidor customizado"
)

# Listar ferramentas disponíveis
print(mcp_client.list_tools())
```

## Exemplo de Uso Prático

### Chat

```
User: "Compare React vs Vue usando web search"

Agent:
1. Identifica necessidade de busca
2. Chama: exa__web_search_advanced_exa("React vs Vue")
3. Recebe: [artigos, documentação, comparações]
4. Retorna: Comparação estruturada
```

### Código

```python
# Chamar ferramenta manualmente
from src.mcp_client import mcp_client

# Ver servidores e ferramentas
print("Servidores:", mcp_client.list_servers())
print("Ferramentas:", mcp_client.list_tools())

# Adicionar novo servidor
mcp_client.add_custom_server(
    server_name="anthropic",
    url="https://mcp.anthropic.com/api",
    tools=["knowledge_search", "documentation"],
    api_key="sua-chave"
)
```

## Structura de Ferramentas Disponíveis

Com **Exa AI** conectado, você tem:

| Ferramenta | Descrição | Exemplo |
|-----------|-----------|---------|
| `exa__web_search_advanced_exa` | Busca web | "Node.js 20 features" |
| `exa__get_code_context_exa` | Código + exemplos | "async/await patterns" |

Com **Brave Search**:

| Ferramenta | Descrição |
|-----------|-----------|
| `brave__brave_web_search` | Busca web privada |
| `brave__brave_local_search` | Busca local |

## Monitoramento

### Ver Servidores Conectados

```python
from src.mcp_client import mcp_client

print(mcp_client.list_servers())
# ['exa', 'brave', 'tavily']
```

### Ver Ferramentas por Servidor

```python
print(mcp_client.list_tools())
# {
#   'exa': ['web_search_advanced_exa', 'get_code_context_exa'],
#   'brave': ['brave_web_search', 'brave_local_search'],
#   'tavily': ['tavily_search']
# }
```

## Troubleshooting

### Servidores não conectam?

```bash
# Verificar API keys
cat .env | grep API_KEY

# Testar conexão
cd apps/agent
uv run python -c "from src.mcp_client import mcp_client; print(mcp_client.list_servers())"
```

### Ferramenta retorna erro?

Causas comuns:
- ❌ API key inválida/expirada
- ❌ Limite de requisições atingido
- ❌ Servidor indisponível
- ❌ Parâmetro inválido

**Solução:** Verifique API key e tente novamente.

## Próximas Etapas

1. **[Recomendado]** Ativar Brave Search + outras APIs
2. **[Avançado]** Criar servidor MCP customizado
3. **[Performance]** Implementar cache de resultados
4. **[Produção]** Rate limiting + retry com backoff

## Referências

- 📖 [MCP Protocol Docs](https://modelcontextprotocol.io/)
- 🔍 [Exa AI Docs](https://exa.ai/docs)
- 🔐 [Brave Search API](https://api.search.brave.com/)
- 🧠 [Perplexity AI](https://www.perplexity.ai/)
- 📊 [Tavily Search](https://tavily.com/)

---

**Status:** ✅ Pronto para uso | Exa AI conectado | 4 servidores pré-configurados
