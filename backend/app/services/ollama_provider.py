"""Local Ollama client adapter providing chat completions and native tool calling."""
import json
import logging
from typing import List, Dict, Any, AsyncGenerator, Optional
import httpx
from backend.app.core.config import settings

from backend.app.services.openrouter_provider import LLMError, LLMConnectionError

logger = logging.getLogger(__name__)

class OllamaError(LLMError):
    pass

class OllamaConnectionError(LLMConnectionError):
    pass

class OllamaProvider:
    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model = model or settings.OLLAMA_CHAT_MODEL
        self.timeout = settings.OLLAMA_TIMEOUT_SECONDS

    async def check_health(self) -> bool:
        """Checks if local Ollama daemon is reachable and responding."""
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        stream: bool = False
    ) -> Dict[str, Any]:
        """Sends chat request to local Ollama with optional tool definitions."""
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "options": {
                "temperature": 0.4
            }
        }
        if tools:
            payload["tools"] = tools

        endpoint = f"{self.base_url}/api/chat"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(endpoint, json=payload)
                if response.status_code != 200:
                    raise OllamaError(f"Ollama server returned HTTP {response.status_code}: {response.text}")
                return response.json()
        except httpx.ConnectError as e:
            logger.error(f"Cannot connect to local Ollama at {self.base_url}: {e}")
            raise OllamaConnectionError(
                f"Local Ollama service unreachable at {self.base_url}. "
                "Ensure Ollama is running locally ('ollama serve')."
            )
        except httpx.TimeoutException:
            logger.error(f"Ollama inference timed out after {self.timeout}s")
            raise OllamaError(f"Local AI inference timed out after {self.timeout} seconds.")
        except Exception as e:
            logger.error(f"Ollama chat error: {e}")
            raise OllamaError(f"Ollama chat failure: {str(e)}")

    async def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Streams chat tokens and events from local Ollama via chunked NDJSON."""
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": 0.4
            }
        }
        if tools:
            payload["tools"] = tools

        endpoint = f"{self.base_url}/api/chat"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream("POST", endpoint, json=payload) as response:
                    if response.status_code != 200:
                        err_text = await response.aread()
                        raise OllamaError(f"Ollama returned HTTP {response.status_code}: {err_text.decode('utf-8', errors='ignore')}")

                    async for line in response.aiter_lines():
                        line = line.strip()
                        if line:
                            try:
                                chunk = json.loads(line)
                                yield chunk
                            except json.JSONDecodeError:
                                continue
        except httpx.ConnectError:
            raise OllamaConnectionError(f"Cannot reach local Ollama daemon at {self.base_url}.")
        except httpx.TimeoutException:
            raise OllamaError("Ollama inference stream timed out.")

ollama_provider = OllamaProvider()
