"""Ollama API client for LLM interactions."""
import json
import logging
from typing import Dict, Any, List, Optional, Generator
import httpx

logger = logging.getLogger(__name__)


class OllamaClient:
    """Client for interacting with Ollama API."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "gpt-oss:20b",
        temperature: float = 0.7,
        num_ctx: int = 4096,
        timeout: int = 120
    ):
        """Initialize Ollama client.

        Args:
            base_url: Base URL of Ollama API
            model: Model name to use
            temperature: Sampling temperature (0-1)
            num_ctx: Context window size
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.temperature = temperature
        self.num_ctx = num_ctx
        self.timeout = timeout
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

    def chat(
        self,
        messages: List[Dict[str, str]],
        stream: bool = False,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Send a chat request to Ollama.

        Args:
            messages: List of message dicts with 'role' and 'content'
            stream: Whether to stream the response
            tools: Optional list of tools for native function calling
            **kwargs: Additional parameters for the model

        Returns:
            Response dictionary with 'message' containing the assistant's reply
        """
        try:
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

        except httpx.HTTPError as e:
            logger.error(f"Chat request failed: {e}")
            raise

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
            response = self.client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            data = response.json()
            return data.get("models", [])
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
            model_names = [m.get("name", "") for m in models]
            return model_name in model_names
        except Exception as e:
            logger.error(f"Failed to check model existence: {e}")
            return False

    def pull_model(self, model_name: Optional[str] = None) -> bool:
        """Pull a model from Ollama.

        Args:
            model_name: Model name to pull (defaults to self.model)

        Returns:
            True if successful, False otherwise
        """
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
