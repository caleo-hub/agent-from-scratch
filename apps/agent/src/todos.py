from datetime import datetime, timezone
import logging
from langchain.agents import AgentState as BaseAgentState
from langchain.tools import ToolRuntime, tool
from langchain.messages import ToolMessage
from langgraph.types import Command
from typing import TypedDict, Literal
import uuid

logger = logging.getLogger(__name__)

class Todo(TypedDict):
    id: str
    title: str
    description: str
    emoji: str
    status: Literal["pending", "completed"]


class UploadedDocument(TypedDict):
    id: str
    name: str
    content: str
    page_count: int
    char_count: int
    uploaded_at: str
    mime_type: str

class AgentState(BaseAgentState):
    todos: list[Todo]
    uploaded_documents: list[UploadedDocument]

@tool
def manage_todos(todos: list[Todo], runtime: ToolRuntime) -> Command:
    """
    Manage the current todos.
    """
    # Ensure all todos have IDs that are unique
    for todo in todos:
        if "id" not in todo or not todo["id"]:
            todo["id"] = str(uuid.uuid4())

    # Update the state
    return Command(update={
        "todos": todos,
        "messages": [
            ToolMessage(
                content="Successfully updated todos",
                tool_call_id=runtime.tool_call_id
            )
        ]
    })

@tool
def get_todos(runtime: ToolRuntime):
    """
    Get the current todos.
    """
    return runtime.state.get("todos", [])


@tool
def manage_uploaded_documents(
    uploaded_documents: list[UploadedDocument],
    runtime: ToolRuntime,
) -> Command:
    """
    Store uploaded PDF documents in agent state.
    """
    normalized: list[UploadedDocument] = []

    for item in uploaded_documents:
        doc_id = item.get("id") or str(uuid.uuid4())
        name = (item.get("name") or "documento.pdf").strip()
        content = (item.get("content") or "").strip()
        page_count = int(item.get("page_count") or 0)
        char_count = int(item.get("char_count") or len(content))
        uploaded_at = item.get("uploaded_at") or datetime.now(timezone.utc).isoformat()
        mime_type = (item.get("mime_type") or "application/octet-stream").strip()

        normalized.append(
            {
                "id": doc_id,
                "name": name,
                "content": content,
                "page_count": page_count,
                "char_count": char_count,
                "uploaded_at": uploaded_at,
                "mime_type": mime_type,
            }
        )

    return Command(
        update={
            "uploaded_documents": normalized,
            "messages": [
                ToolMessage(
                    content=f"Successfully stored {len(normalized)} uploaded documents",
                    tool_call_id=runtime.tool_call_id,
                )
            ],
        }
    )


@tool
def get_uploaded_documents(runtime: ToolRuntime) -> dict:
    """
    Get uploaded documents currently stored in conversation state.
    """
    state = runtime.state or {}
    documents = state.get("uploaded_documents", [])

    # Fallbacks for different state envelopes.
    if not documents and isinstance(state.get("state"), dict):
        documents = state.get("state", {}).get("uploaded_documents", [])

    if not documents and isinstance(state.get("copilotkit"), dict):
        cp = state.get("copilotkit", {})
        if isinstance(cp.get("state"), dict):
            documents = cp.get("state", {}).get("uploaded_documents", [])

    if not isinstance(documents, list):
        documents = []

    logger.info(
        "get_uploaded_documents called",
        extra={
            "state_keys": list(state.keys()) if isinstance(state, dict) else [],
            "documents_count": len(documents),
        },
    )

    return {
        "count": len(documents),
        "documents": [
            {
                "id": doc.get("id"),
                "name": doc.get("name"),
                "mime_type": doc.get("mime_type"),
                "page_count": doc.get("page_count", 0),
                "char_count": doc.get("char_count", 0),
                "uploaded_at": doc.get("uploaded_at"),
                "content": doc.get("content") or "",
            }
            for doc in documents
        ],
    }

todo_tools = [
    manage_todos,
    get_todos,
]

upload_tools = [
    manage_uploaded_documents,
    get_uploaded_documents,
]
