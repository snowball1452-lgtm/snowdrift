import os
import asyncio
from typing import Optional
import litellm

litellm.set_verbose = False

PROVIDER_MODEL_MAP = {
    "openai": lambda model: model,
    "anthropic": lambda model: f"anthropic/{model}",
    "gemini": lambda model: f"gemini/{model}",
    "google": lambda model: f"gemini/{model}",
    "ollama": lambda model: f"ollama/{model}",
    "groq": lambda model: f"groq/{model}",
}

class UserMessage:
    def __init__(self, text: str):
        self.text = text

class LlmResponse:
    def __init__(self, text: str):
        self.text = text
    
    def __str__(self):
        return self.text
    
    def strip(self):
        return self.text.strip()

class LlmChat:
    def __init__(self, api_key: str = "", session_id: str = "", system_message: str = ""):
        self.api_key = api_key
        self.session_id = session_id
        self.system_message = system_message
        self.provider = "openai"
        self.model = "gpt-4o-mini"
        self.history = []
        self.api_base: Optional[str] = None

    def with_model(self, provider: str, model: str):
        self.provider = provider.lower()
        self.model = model
        return self

    def with_api_base(self, base_url: str):
        """Set a custom API base URL (used for Ollama and OpenAI-compatible servers)."""
        self.api_base = base_url
        return self

    def with_api_key(self, key: str):
        """Override the API key (used to pass provider-specific keys from settings)."""
        if key:
            self.api_key = key
        return self

    def _get_litellm_model(self):
        mapper = PROVIDER_MODEL_MAP.get(self.provider, lambda m: m)
        return mapper(self.model)

    def _get_api_key_for_provider(self):
        provider = self.provider
        if provider == "openai":
            return (self.api_key or
                    os.environ.get("OPENAI_API_KEY") or
                    os.environ.get("EMERGENT_LLM_KEY", ""))
        elif provider == "anthropic":
            return (self.api_key or
                    os.environ.get("ANTHROPIC_API_KEY") or
                    os.environ.get("EMERGENT_LLM_KEY", ""))
        elif provider in ("gemini", "google"):
            return (self.api_key or
                    os.environ.get("GEMINI_API_KEY") or
                    os.environ.get("GOOGLE_API_KEY") or
                    os.environ.get("EMERGENT_LLM_KEY", ""))
        elif provider == "ollama":
            # Ollama runs locally — no API key required
            # But still allow an override if someone secures their Ollama instance
            return self.api_key or os.environ.get("OLLAMA_API_KEY", "ollama")
        elif provider == "groq":
            return (self.api_key or
                    os.environ.get("GROQ_API_KEY") or
                    os.environ.get("EMERGENT_LLM_KEY", ""))
        else:
            return self.api_key or os.environ.get("EMERGENT_LLM_KEY", "")

    def _get_api_base_for_provider(self) -> Optional[str]:
        """Get the base URL for the provider (primarily for Ollama)."""
        if self.api_base:
            return self.api_base
        if self.provider == "ollama":
            return os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        return None

    async def send_message(self, message: UserMessage) -> LlmResponse:
        messages = []
        
        if self.system_message:
            messages.append({"role": "system", "content": self.system_message})
        
        for h in self.history:
            messages.append(h)
        
        messages.append({"role": "user", "content": message.text})
        
        litellm_model = self._get_litellm_model()
        api_key = self._get_api_key_for_provider()
        api_base = self._get_api_base_for_provider()

        kwargs = dict(
            model=litellm_model,
            messages=messages,
            api_key=api_key if api_key else None,
            temperature=0.7,
            max_tokens=4096,
        )
        if api_base:
            kwargs["api_base"] = api_base

        try:
            response = await litellm.acompletion(**kwargs)
            
            text = response.choices[0].message.content or ""
            
            self.history.append({"role": "user", "content": message.text})
            self.history.append({"role": "assistant", "content": text})
            
            return LlmResponse(text=text)
        
        except Exception as e:
            error_msg = f"[LLM Error: {str(e)}]"
            return LlmResponse(text=error_msg)
