"""OpenRouter AI client adapter providing chat completions and function/tool calling."""
import json
import logging
from typing import List, Dict, Any, AsyncGenerator, Optional
import httpx
from backend.app.core.config import settings

logger = logging.getLogger(__name__)

class LLMError(Exception):
    """Base error for LLM provider failures."""
    pass

class LLMConnectionError(LLMError):
    """Raised when the LLM service endpoint is unreachable."""
    pass

class OpenRouterProvider:
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 30
    ):
        self.api_key = api_key or settings.OPENROUTER_API_KEY
        self.model = model or settings.OPENROUTER_MODEL
        self.base_url = (base_url or settings.OPENROUTER_BASE_URL).rstrip("/")
        self.timeout = timeout
        self._last_check_time: Optional[float] = None
        self._cached_availability: Dict[str, Any] = {}

    @property
    def headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "Genius AI Assistant",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key.strip()}"
        return headers

    @property
    def is_configured(self) -> bool:
        """Returns True if an API key is present."""
        return bool(self.api_key and self.api_key.strip())

    async def check_availability(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Validates real connectivity and authentication with OpenRouter, cached with 60s TTL to avoid API spam."""
        import time

        now = time.time()
        if not force_refresh and self._last_check_time and (now - self._last_check_time < 60.0):
            return self._cached_availability

        status: Dict[str, Any] = {
            "configured": self.is_configured,
            "reachable": False,
            "authenticated": False,
            "model": self.model,
            "detail": None
        }

        if not self.is_configured:
            status["detail"] = "OPENROUTER_API_KEY is not configured."
            self._cached_availability = status
            self._last_check_time = now
            return status

        endpoint = f"{self.base_url}/auth/key"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(endpoint, headers=self.headers)
                status["reachable"] = True
                if resp.status_code == 200:
                    status["authenticated"] = True
                    status["detail"] = "OpenRouter authenticated and available."
                elif resp.status_code == 401:
                    status["detail"] = "Invalid or expired OpenRouter API key."
                else:
                    status["detail"] = f"OpenRouter returned HTTP {resp.status_code}."
        except httpx.ConnectError:
            status["detail"] = "Cannot reach OpenRouter endpoint. Check network connectivity."
        except httpx.TimeoutException:
            status["detail"] = "Connection to OpenRouter timed out."
        except Exception as e:
            logger.error(f"Error querying OpenRouter availability: {type(e).__name__}")
            status["detail"] = f"OpenRouter availability probe failed: {type(e).__name__}."

        self._cached_availability = status
        self._last_check_time = now
        return status

    async def check_health(self) -> bool:
        """Readiness check: validates configuration and availability."""
        if not self.is_configured:
            return False
        avail = await self.check_availability()
        return avail.get("authenticated", False)

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        stream: bool = False
    ) -> Dict[str, Any]:
        """Sends chat request to OpenRouter with optional tool definitions."""
        if not self.api_key or not self.api_key.strip():
            raise LLMConnectionError(
                "OPENROUTER_API_KEY is not configured in .env. "
                "Please configure a valid OpenRouter API key to enable AI chat."
            )

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "temperature": 0.3,
        }
        if tools:
            payload["tools"] = tools

        endpoint = f"{self.base_url}/chat/completions"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(endpoint, json=payload, headers=self.headers)
                
                if response.status_code == 401:
                    logger.error("OpenRouter authentication failed: HTTP 401.")
                    raise LLMError("OpenRouter authentication failed: Invalid or expired API key.")
                elif response.status_code in (402, 403):
                    logger.error(f"OpenRouter access denied (HTTP {response.status_code}).")
                    raise LLMError("OpenRouter access denied or quota exceeded for the configured model.")
                elif response.status_code == 429:
                    logger.warning("OpenRouter rate limit exceeded (HTTP 429).")
                    raise LLMError("OpenRouter rate limit exceeded. Please wait a moment before trying again.")
                elif response.status_code != 200:
                    logger.error(f"OpenRouter returned error status (HTTP {response.status_code}).")
                    raise LLMError(f"OpenRouter service error (HTTP {response.status_code}). Please retry later.")

                data = response.json()
                choices = data.get("choices", [])
                if not choices:
                    raise LLMError("OpenRouter returned an empty choice set.")

                message = choices[0].get("message", {})
                return {"message": message}

        except httpx.ConnectError as e:
            logger.error(f"Cannot connect to OpenRouter endpoint {self.base_url}: {type(e).__name__}")
            raise LLMConnectionError("Failed to connect to OpenRouter endpoint. Check network connectivity.")
        except httpx.TimeoutException:
            logger.error(f"OpenRouter request timed out after {self.timeout}s")
            raise LLMError(f"OpenRouter inference timed out after {self.timeout} seconds.")
        except LLMError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error calling OpenRouter: {type(e).__name__}")
            raise LLMError("An unexpected error occurred while communicating with the AI service.")

openrouter_provider = OpenRouterProvider()
