"""
emergentintegrations.llm.chat - Stub for on-device Android build.

The real package is a proprietary gateway to OpenAI/Anthropic/Gemini.
On-device we route all inference through Ollama (local or cloud), so this
code path is never hit. The stub exists only so `from emergentintegrations.llm.chat
import LlmChat, UserMessage` succeeds at import time.

If the host app ever *does* hit this path (e.g. user selected Anthropic in
settings), we return a clear error instead of crashing — a visible message
beats a stack trace.
"""
from dataclasses import dataclass
from typing import Optional, Any


@dataclass
class UserMessage:
    """Placeholder for the real UserMessage object."""
    text: str = ""
    role: str = "user"


class LlmChat:
    """Stub LlmChat. Instantiating is fine; sending returns a clear error string."""

    def __init__(self, api_key: str = "", session_id: str = "", system_message: str = "", **kwargs: Any):
        self.api_key = api_key
        self.session_id = session_id
        self.system_message = system_message
        self._provider: Optional[str] = None
        self._model: Optional[str] = None

    def with_model(self, provider: str, model: str) -> "LlmChat":
        self._provider = provider
        self._model = model
        return self

    def with_api_base(self, base_url: str) -> "LlmChat":
        """Used by Ollama-compatible servers. No-op in this stub."""
        self._api_base = base_url
        return self

    def with_api_key(self, key: str) -> "LlmChat":
        if key:
            self.api_key = key
        return self

    def _get_litellm_model(self) -> str:
        return f"{self._provider}/{self._model}" if self._provider else "ollama/llama3"

    async def send_message(self, message: UserMessage) -> str:
        return (
            "[on-device build] The Emergent LLM gateway is unavailable offline. "
            "Switch to Ollama in Settings to keep chatting."
        )

    def send_message_sync(self, message: UserMessage) -> str:
        return (
            "[on-device build] The Emergent LLM gateway is unavailable offline. "
            "Switch to Ollama in Settings to keep chatting."
        )
