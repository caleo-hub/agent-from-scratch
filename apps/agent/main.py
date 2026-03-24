"""
This is the main entry point for the agent.
It defines the workflow graph, state, tools, nodes and edges.
"""

from copilotkit import CopilotKitMiddleware
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI, AzureChatOpenAI

from src.query import query_data
from src.todos import AgentState, todo_tools
from src.form import generate_form
from src.mcp_client import mcp_client, mcp_tools

llm = AzureChatOpenAI(
    azure_deployment="gpt-4.1",  
    api_version="2024-08-01-preview", 
)

# Build tools list with MCP tools
all_tools = [query_data, *todo_tools, generate_form, *mcp_tools]

# Log connected MCP servers
connected_servers = mcp_client.list_servers()
servers_str = ", ".join(connected_servers) if connected_servers else "none"

agent = create_agent(
    model=llm,
    tools=all_tools,
    middleware=[CopilotKitMiddleware()],
    state_schema=AgentState,
    system_prompt=f"""
        You are a polished, professional demo assistant using CopilotKit and LangGraph. Only mention either when necessary.

        Keep responses brief and polished — 1 to 2 sentences max. No verbose explanations.

        When demonstrating charts, always call the query_data tool to fetch data first.
        When asked to manage todos, enable app mode first, then manage todos.
        
        You have access to the following MCP servers for extended capabilities:
        - Connected servers: {servers_str}
        
        Use the available MCP tools to help with web search, code context, and other advanced queries.
    """,
)

graph = agent
