"""MCP Client for connecting to MCP SQLite Server."""
import httpx
import logging
import uuid
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MCPTool:
    """Represents an MCP tool."""
    name: str
    description: str
    input_schema: Dict[str, Any]


class MCPClient:
    """Client for interacting with MCP server."""

    def __init__(self, base_url: str, timeout: int = 30):
        """Initialize MCP client.

        Args:
            base_url: Base URL of the MCP server
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.tools: Dict[str, MCPTool] = {}
        self.session_id = str(uuid.uuid4())
        self.initialized = False

        # Create client with proper headers (session ID will be added per request)
        self.base_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        }
        self.client = httpx.Client(timeout=timeout)

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    def close(self):
        """Close the HTTP client."""
        self.client.close()

    def initialize(self) -> bool:
        """Initialize the MCP session.

        Returns:
            True if initialization successful
        """
        if self.initialized:
            return True

        try:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "py-mcp-client",
                        "version": "1.0.0"
                    }
                }
            }

            # First request: no session ID in header
            response = self.client.post(self.base_url, json=payload, headers=self.base_headers)
            response.raise_for_status()

            # Extract session ID from response header
            server_session_id = response.headers.get('mcp-session-id')
            if server_session_id:
                self.session_id = server_session_id
                logger.info(f"Received session ID from server: {self.session_id}")

            # Response may be server-sent event format
            response_text = response.text
            if response_text.startswith("event: message"):
                # Extract JSON from SSE format
                lines = response_text.split('\n')
                for line in lines:
                    if line.startswith('data: '):
                        data = line[6:]  # Remove 'data: ' prefix
                        import json
                        result = json.loads(data)
                        if "error" not in result:
                            self.initialized = True
                            logger.info("MCP session initialized successfully")
                            return True
            else:
                data = response.json()
                if "error" not in data:
                    self.initialized = True
                    logger.info("MCP session initialized successfully")
                    return True

            logger.error("Failed to initialize MCP session")
            return False

        except Exception as e:
            logger.error(f"Failed to initialize MCP session: {e}")
            return False

    def list_tools(self) -> List[MCPTool]:
        """List all available tools from the MCP server.

        Returns:
            List of MCPTool objects
        """
        # Ensure session is initialized
        if not self.initialized:
            if not self.initialize():
                raise Exception("Failed to initialize MCP session")

        try:
            # Use JSON-RPC 2.0 format
            payload = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {}
            }

            # Add session ID to headers
            headers = {
                **self.base_headers,
                "mcp-session-id": self.session_id
            }
            response = self.client.post(self.base_url, json=payload, headers=headers)
            response.raise_for_status()

            # Parse response (may be SSE format)
            response_text = response.text
            if response_text.startswith("event: message"):
                # Extract JSON from SSE format
                import json
                for line in response_text.split('\n'):
                    if line.startswith('data: '):
                        data = json.loads(line[6:])
                        break
            else:
                data = response.json()

            # Handle JSON-RPC response format
            if "error" in data:
                error_msg = data["error"].get("message", "Unknown error")
                logger.error(f"JSON-RPC error: {error_msg}")
                raise Exception(error_msg)

            result = data.get("result", {})
            tools = []
            for tool_data in result.get("tools", []):
                tool = MCPTool(
                    name=tool_data["name"],
                    description=tool_data["description"],
                    input_schema=tool_data["inputSchema"]
                )
                tools.append(tool)
                self.tools[tool.name] = tool

            logger.info(f"Loaded {len(tools)} tools from MCP server")
            return tools

        except httpx.HTTPError as e:
            logger.error(f"Failed to list tools: {e}")
            raise

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool on the MCP server.

        Args:
            tool_name: Name of the tool to call
            arguments: Arguments to pass to the tool

        Returns:
            Tool execution result
        """
        # Ensure session is initialized
        if not self.initialized:
            if not self.initialize():
                return {
                    "success": False,
                    "error": "Failed to initialize MCP session"
                }

        try:
            # Use JSON-RPC 2.0 format
            payload = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                }
            }

            # Add session ID to headers
            headers = {
                **self.base_headers,
                "mcp-session-id": self.session_id
            }
            response = self.client.post(self.base_url, json=payload, headers=headers)
            response.raise_for_status()

            # Parse response (may be SSE format)
            response_text = response.text
            if response_text.startswith("event: message"):
                # Extract JSON from SSE format
                import json
                for line in response_text.split('\n'):
                    if line.startswith('data: '):
                        data = json.loads(line[6:])
                        break
            else:
                data = response.json()

            # Handle JSON-RPC error response
            if "error" in data:
                error_msg = data["error"].get("message", "Unknown error")
                logger.error(f"JSON-RPC error: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg
                }

            result = data.get("result", {})

            if result.get("isError", False):
                error_msg = result.get("content", [{}])[0].get("text", "Unknown error")
                logger.error(f"Tool execution error: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg
                }

            # Extract result text
            content = result.get("content", [])
            if content:
                result_text = content[0].get("text", "")
                logger.info(f"Tool {tool_name} executed successfully")
                return {
                    "success": True,
                    "result": result_text
                }

            return {
                "success": True,
                "result": "Tool executed successfully (no output)"
            }

        except httpx.HTTPError as e:
            logger.error(f"Failed to call tool {tool_name}: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def get_tool_descriptions(self) -> List[Dict[str, str]]:
        """Get formatted tool descriptions for the LLM.

        Returns:
            List of tool descriptions with name, description, and parameters
        """
        descriptions = []
        for tool in self.tools.values():
            properties = tool.input_schema.get("properties", {})
            required = tool.input_schema.get("required", [])

            params = []
            for param_name, param_info in properties.items():
                param_type = param_info.get("type", "string")
                param_desc = param_info.get("description", "")
                is_required = param_name in required
                params.append(
                    f"  - {param_name} ({param_type}){' [required]' if is_required else ''}: {param_desc}"
                )

            desc = {
                "name": tool.name,
                "description": tool.description,
                "parameters": "\n".join(params) if params else "  No parameters"
            }
            descriptions.append(desc)

        return descriptions

    def format_tools_for_prompt(self) -> str:
        """Format tools information for inclusion in LLM prompt.

        Returns:
            Formatted string describing all available tools
        """
        if not self.tools:
            self.list_tools()

        tool_descriptions = self.get_tool_descriptions()

        formatted = "Available MCP Tools:\n\n"
        for tool_desc in tool_descriptions:
            formatted += f"Tool: {tool_desc['name']}\n"
            formatted += f"Description: {tool_desc['description']}\n"
            formatted += f"Parameters:\n{tool_desc['parameters']}\n\n"

        formatted += (
            "To use a tool, respond with a JSON object in the following format:\n"
            '{"tool": "tool_name", "arguments": {"param1": "value1", "param2": "value2"}}\n\n'
            "After using a tool, I will show you the result and you can continue the conversation."
        )

        return formatted

    def format_tools_for_ollama(self) -> List[Dict[str, Any]]:
        """Format tools for Ollama's native function calling format.

        Returns:
            List of tools in Ollama format
        """
        if not self.tools:
            self.list_tools()

        ollama_tools = []
        for tool in self.tools.values():
            ollama_tool = {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.input_schema
                }
            }
            ollama_tools.append(ollama_tool)

        return ollama_tools

    def health_check(self) -> bool:
        """Check if the MCP server is healthy.

        Returns:
            True if server is healthy, False otherwise
        """
        try:
            # Extract base URL without /mcp endpoint for health check
            health_url = self.base_url.replace('/mcp', '') + '/healthz'
            response = self.client.get(health_url)
            response.raise_for_status()
            # Health endpoint may return text or JSON
            try:
                data = response.json()
                return data.get("status") == "healthy" or data.get("status") == "ok"
            except:
                # If not JSON, check for 200 status code
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
