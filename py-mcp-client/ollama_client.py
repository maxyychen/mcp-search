"""Ollama API client for LLM interactions."""
import json
import logging
import re
from typing import Dict, Any, List, Optional, Generator
import httpx

logger = logging.getLogger(__name__)


class OllamaClient:
    """Client for interacting with Ollama API and vLLM (OpenAI-compatible) API."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "gpt-oss:20b",
        temperature: float = 0.7,
        num_ctx: int = 4096,
        timeout: int = 120,
        backend: str = "ollama"
    ):
        """Initialize LLM client.

        Args:
            base_url: Base URL of the API
            model: Model name to use
            temperature: Sampling temperature (0-1)
            num_ctx: Context window size
            timeout: Request timeout in seconds
            backend: Backend type - "ollama" or "vllm"
        """
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.temperature = temperature
        self.num_ctx = num_ctx
        self.timeout = timeout
        self.backend = backend.lower()
        self.client = httpx.Client(timeout=timeout)

        # Validate backend
        if self.backend not in ["ollama", "vllm"]:
            raise ValueError(f"Unsupported backend: {backend}. Use 'ollama' or 'vllm'.")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    def close(self):
        """Close the HTTP client."""
        self.client.close()

    def _parse_json_tool_call_from_content(
        self,
        content: str,
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[Dict[str, Any]]:
        """Parse tool call from JSON in content field (for vLLM models that don't use proper tool_calls).

        Args:
            content: The content string that might contain JSON
            tools: List of available tools to match against

        Returns:
            Parsed tool call in OpenAI format, or None if no valid tool call found
        """
        if not content or not tools:
            return None

        # Try to extract JSON from the content
        content = content.strip()

        # Check if content looks like JSON
        if not (content.startswith('{') and content.endswith('}')):
            return None

        try:
            # Parse the JSON
            parsed = json.loads(content)

            # If it's a dict, try to match it to a tool
            if isinstance(parsed, dict):
                # Strategy 1: Check if there's a "tool" or "name" or "function" key
                tool_name = parsed.get("tool") or parsed.get("name") or parsed.get("function")
                arguments = parsed.get("arguments") or parsed.get("params")

                if tool_name and arguments:
                    # Format: {"tool": "tool_name", "arguments": {...}}
                    return {
                        "id": "call_" + str(hash(json.dumps(parsed)))[:16],
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "arguments": arguments if isinstance(arguments, str) else json.dumps(arguments)
                        }
                    }

                # Strategy 2: The entire JSON is the arguments, try to match to a tool
                # Find which tool this could be based on parameter names
                best_match = None
                best_match_score = 0

                for tool in tools:
                    tool_params = tool.get("function", {}).get("parameters", {}).get("properties", {})

                    # Count how many of the JSON keys match the tool's parameters
                    matching_keys = set(parsed.keys()) & set(tool_params.keys())
                    score = len(matching_keys)

                    if score > best_match_score:
                        best_match_score = score
                        best_match = tool.get("function", {}).get("name")

                if best_match and best_match_score > 0:
                    return {
                        "id": "call_" + str(hash(json.dumps(parsed)))[:16],
                        "type": "function",
                        "function": {
                            "name": best_match,
                            "arguments": json.dumps(parsed)
                        }
                    }

        except (json.JSONDecodeError, ValueError) as e:
            logger.debug(f"Failed to parse JSON from content: {e}")
            return None

        return None

    def chat(
        self,
        messages: List[Dict[str, str]],
        stream: bool = False,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Send a chat request to the LLM backend.

        Args:
            messages: List of message dicts with 'role' and 'content'
            stream: Whether to stream the response
            tools: Optional list of tools for native function calling
            **kwargs: Additional parameters for the model

        Returns:
            Response dictionary with 'message' containing the assistant's reply
        """
        try:
            if self.backend == "ollama":
                return self._chat_ollama(messages, stream, tools, **kwargs)
            else:  # vllm
                return self._chat_vllm(messages, stream, tools, **kwargs)

        except httpx.HTTPError as e:
            logger.error(f"Chat request failed: {e}")
            raise

    def _chat_ollama(
        self,
        messages: List[Dict[str, str]],
        stream: bool = False,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Send a chat request to Ollama API."""
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "options": {
                "temperature": kwargs.get("temperature", self.temperature),
                "num_ctx": kwargs.get("num_ctx", self.num_ctx),
                "top_p": kwargs.get("top_p", 0.9),
            }
        }

        # Add tools if provided for native function calling
        if tools:
            payload["tools"] = tools

        if stream:
            return self._stream_chat(payload)

        response = self.client.post(
            f"{self.base_url}/api/chat",
            json=payload
        )
        response.raise_for_status()
        return response.json()

    def _chat_vllm(
        self,
        messages: List[Dict[str, str]],
        stream: bool = False,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Send a chat request to vLLM (OpenAI-compatible) API."""
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", self.temperature),
            "max_tokens": kwargs.get("num_ctx", self.num_ctx),
            "top_p": kwargs.get("top_p", 0.9),
            "stream": stream
        }

        # Add tools if provided for native function calling
        if tools:
            payload["tools"] = tools

        if stream:
            return self._stream_chat(payload)

        response = self.client.post(
            f"{self.base_url}/v1/chat/completions",
            json=payload
        )
        response.raise_for_status()

        # Convert OpenAI format to Ollama format for compatibility
        openai_response = response.json()
        message = openai_response["choices"][0]["message"]
        content = message.get("content", "")
        tool_calls = message.get("tool_calls")

        # If no tool_calls but content looks like JSON, try to parse it as a tool call
        if tools and (not tool_calls or len(tool_calls) == 0) and content:
            parsed_tool_call = self._parse_json_tool_call_from_content(content, tools)
            if parsed_tool_call:
                logger.info(f"Detected JSON tool call in content: {parsed_tool_call['function']['name']}")
                tool_calls = [parsed_tool_call]
                # Clear content since it was actually a tool call
                content = ""

        return {
            "message": {
                "role": "assistant",
                "content": content,
                "tool_calls": tool_calls
            },
            "done": True
        }

    def _stream_chat(self, payload: Dict[str, Any]) -> Generator[Dict[str, Any], None, None]:
        """Stream chat response from Ollama.

        Args:
            payload: Request payload

        Yields:
            Chunks of the response
        """
        with self.client.stream("POST", f"{self.base_url}/api/chat", json=payload) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line:
                    try:
                        chunk = json.loads(line)
                        yield chunk
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse chunk: {line}")
                        continue

    def generate(
        self,
        prompt: str,
        stream: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate a completion from a prompt.

        Args:
            prompt: The prompt to generate from
            stream: Whether to stream the response
            **kwargs: Additional parameters for the model

        Returns:
            Response dictionary with 'response' containing the generated text
        """
        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": stream,
                "options": {
                    "temperature": kwargs.get("temperature", self.temperature),
                    "num_ctx": kwargs.get("num_ctx", self.num_ctx),
                    "top_p": kwargs.get("top_p", 0.9),
                }
            }

            if stream:
                return self._stream_generate(payload)

            response = self.client.post(
                f"{self.base_url}/api/generate",
                json=payload
            )
            response.raise_for_status()
            return response.json()

        except httpx.HTTPError as e:
            logger.error(f"Generate request failed: {e}")
            raise

    def _stream_generate(self, payload: Dict[str, Any]) -> Generator[Dict[str, Any], None, None]:
        """Stream generate response from Ollama.

        Args:
            payload: Request payload

        Yields:
            Chunks of the response
        """
        with self.client.stream("POST", f"{self.base_url}/api/generate", json=payload) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line:
                    try:
                        chunk = json.loads(line)
                        yield chunk
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse chunk: {line}")
                        continue

    def list_models(self) -> List[Dict[str, Any]]:
        """List available models.

        Returns:
            List of available models
        """
        try:
            if self.backend == "ollama":
                response = self.client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                data = response.json()
                return data.get("models", [])
            else:  # vllm
                response = self.client.get(f"{self.base_url}/v1/models")
                response.raise_for_status()
                data = response.json()
                return data.get("data", [])
        except httpx.HTTPError as e:
            logger.error(f"Failed to list models: {e}")
            raise

    def check_model_exists(self, model_name: Optional[str] = None) -> bool:
        """Check if a model exists.

        Args:
            model_name: Model name to check (defaults to self.model)

        Returns:
            True if model exists, False otherwise
        """
        model_name = model_name or self.model
        try:
            models = self.list_models()
            if self.backend == "ollama":
                model_names = [m.get("name", "") for m in models]
            else:  # vllm - OpenAI format uses "id" field
                model_names = [m.get("id", "") for m in models]
            return model_name in model_names
        except Exception as e:
            logger.error(f"Failed to check model existence: {e}")
            return False

    def pull_model(self, model_name: Optional[str] = None) -> bool:
        """Pull a model from Ollama.

        Note: This only works with Ollama backend. vLLM loads models at startup.

        Args:
            model_name: Model name to pull (defaults to self.model)

        Returns:
            True if successful, False otherwise
        """
        if self.backend != "ollama":
            logger.warning("pull_model is only supported for Ollama backend")
            return False

        model_name = model_name or self.model
        try:
            logger.info(f"Pulling model {model_name}...")
            response = self.client.post(
                f"{self.base_url}/api/pull",
                json={"name": model_name}
            )
            response.raise_for_status()
            logger.info(f"Model {model_name} pulled successfully")
            return True
        except httpx.HTTPError as e:
            logger.error(f"Failed to pull model: {e}")
            return False
