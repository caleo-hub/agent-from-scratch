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

llm = AzureChatOpenAI(
    azure_deployment="gpt-4.1",  
    api_version="2024-08-01-preview", 
)

agent = create_agent(
    model=llm,
    tools=[query_data, *todo_tools, generate_form],
    middleware=[CopilotKitMiddleware()],
    state_schema=AgentState,
    system_prompt="""
        You are a polished, professional demo assistant using CopilotKit and LangGraph. Only mention either when necessary.

        Keep responses brief and polished — 1 to 2 sentences max. No verbose explanations.

        When demonstrating charts, always call the query_data tool to fetch data first.
        When asked to manage todos, enable app mode first, then manage todos.
    """,
)

graph = agent
