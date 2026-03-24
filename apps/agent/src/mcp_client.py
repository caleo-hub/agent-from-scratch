"""
MCP (Model Context Protocol) client for integrating external tools.
Supports multiple MCP servers via HTTP and SSE connections.
"""

import os
import json
import asyncio
from typing import Optional, Callable, Dict, List
from langchain.tools import tool
import logging
from urllib.parse import urlencode
from mcp.client.streamable_http import streamable_http_client
from mcp.client.session import ClientSession

logger = logging.getLogger(__name__)


class MCPServerConfig:
    """Predefined MCP server configurations"""
    
    SERVERS = {
        "tavily": {
            "url": "https://mcp.tavily.com/mcp/",
            "api_key_env": "TAVILY_API_KEY",
            "api_key_query_param": "tavilyApiKey",
            "description": "Tavily - Web search and research via MCP"
        }
    }


class MCPClient:
    """HTTP/SSE client for calling MCP servers"""
    
    def __init__(self):
        self.servers: Dict[str, dict] = {}
        self.tools_registry: Dict[str, Callable] = {}
        self._initialize_servers()
    
    def _initialize_servers(self):
        """Initialize configured MCP servers"""
        for server_name, config in MCPServerConfig.SERVERS.items():
            if self._is_server_enabled(server_name, config):
                self._register_server(server_name, config)
    
    def _is_server_enabled(self, server_name: str, config: dict) -> bool:
        """Check if server should be enabled"""
        if "api_key_env" in config:
            api_key = os.getenv(config["api_key_env"])
            if not api_key:
                logger.debug(f"Server '{server_name}' disabled: {config['api_key_env']} not set")
                return False
        return True
    
    def _register_server(self, server_name: str, config: dict):
        """Register an MCP server"""
        try:
            api_key = os.getenv(config.get("api_key_env", ""))
            url = self._build_server_url(config["url"], config, api_key)
            discovered_tools = asyncio.run(self._discover_server_tools(url))
            tools = discovered_tools or config.get("tools", [])
            if not tools:
                logger.warning(f"No tools discovered for server '{server_name}'")
            
            # Store server info
            self.servers[server_name] = {
                "url": url,
                "api_key": api_key,
                "config": {**config, "tools": tools},
            }
            
            # Create dynamic tools for this server
            self._create_server_tools(server_name, self.servers[server_name]["config"])
            
            print(f"✓ Registered MCP server: {server_name}")
            logger.info(f"MCP server '{server_name}' registered with {len(tools)} tools")
            
        except Exception as e:
            print(f"✗ Failed to register {server_name}: {str(e)}")
            logger.error(f"Failed to register MCP server '{server_name}': {str(e)}")

    def _build_server_url(self, base_url: str, config: dict, api_key: Optional[str]) -> str:
        """Build server URL including API key query parameter when configured."""
        query_param = config.get("api_key_query_param")
        if not api_key or not query_param:
            return base_url

        separator = "&" if "?" in base_url else "?"
        return f"{base_url}{separator}{urlencode({query_param: api_key})}"

    async def _discover_server_tools(self, url: str) -> List[str]:
        """Discover tools supported by the remote MCP server using tools/list."""
        try:
            async with streamable_http_client(url) as (read_stream, write_stream, _):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    tools_result = await session.list_tools()
                    return [tool.name for tool in tools_result.tools]
        except Exception as e:
            logger.warning(f"Failed to discover MCP tools from {url}: {str(e)}")
            return []
    
    def _create_server_tools(self, server_name: str, config: dict):
        """Dynamically create tools for a server"""
        tools = config.get("tools", [])
        
        for tool_name in tools:
            # Create a closure to capture server_name and tool_name
            def create_tool_func(srv_name, t_name):
                @tool
                def mcp_tool(query: str) -> str:
                    """Call an MCP tool"""
                    return asyncio.run(
                        self._call_mcp_tool(srv_name, t_name, query)
                    )
                mcp_tool.name = f"{srv_name}__{t_name}"
                mcp_tool.description = f"Call {t_name} from {srv_name} MCP server with query"
                return mcp_tool
            
            tool_func = create_tool_func(server_name, tool_name)
            self.tools_registry[f"{server_name}__{tool_name}"] = tool_func
    
    async def _call_mcp_tool(
        self, 
        server_name: str, 
        tool_name: str, 
        query: str
    ) -> str:
        """Call a tool on an MCP server"""
        if server_name not in self.servers:
            return json.dumps({
                "error": f"Server '{server_name}' not found",
                "available_servers": list(self.servers.keys())
            })
        
        server = self.servers[server_name]
        url = server["url"]

        try:
            async with streamable_http_client(url) as (read_stream, write_stream, _):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    result = await session.call_tool(
                        tool_name,
                        arguments={"query": query},
                    )
                    return result.model_dump_json(indent=2)
        except Exception as e:
            return json.dumps({
                "error": str(e),
                "tool": tool_name,
                "server": server_name
            })
    
    def add_custom_server(
        self,
        server_name: str,
        url: str,
        tools: List[str],
        api_key: Optional[str] = None,
        description: str = "Custom MCP Server"
    ):
        """Add a custom MCP server"""
        try:
            config = {
                "url": url,
                "description": description,
                "tools": tools
            }
            
            self.servers[server_name] = {
                "url": url,
                "api_key": api_key,
                "config": config
            }
            
            self._create_server_tools(server_name, config)
            
            print(f"✓ Added custom server: {server_name}")
            logger.info(f"Custom MCP server '{server_name}' added")
            
        except Exception as e:
            print(f"✗ Failed to add custom server {server_name}: {str(e)}")
            logger.error(f"Failed to add custom server '{server_name}': {str(e)}")
    
    def get_all_tools(self) -> List[Callable]:
        """Get all registered tools"""
        return list(self.tools_registry.values())
    
    def list_servers(self) -> List[str]:
        """List all connected servers"""
        return list(self.servers.keys())
    
    def list_tools(self) -> Dict[str, List[str]]:
        """List all tools by server"""
        result = {}
        for server_name, server in self.servers.items():
            result[server_name] = server["config"].get("tools", [])
        return result


# Global MCP client instance
mcp_client = MCPClient()

# Export tools
mcp_tools = mcp_client.get_all_tools()

