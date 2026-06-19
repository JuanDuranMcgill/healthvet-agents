"""
Shared LLM factory — provider-agnostic via env vars (OpenAI-compatible APIs).

Defaults to Groq (free, no card, fast Llama 3.3 70B). Swap providers by setting
LLM_BASE_URL / LLM_API_KEY / LLM_MODEL (e.g. OpenRouter, Gemini OpenAI endpoint,
or back to AIML/Featherless) — no code change needed.

ChatOpenAINoStrict drops strict=True from bind_tools: langchain.agents.create_agent
hardcodes strict=True, which 400s on providers whose tool schemas contain anyOf
(optional fields), e.g. the Band SDK tools.
"""
import os
from langchain_openai import ChatOpenAI

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY") or os.getenv("GROQ_API_KEY") or os.getenv("AIML_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
LLM_MODEL_SMALL = os.getenv("LLM_MODEL_SMALL", "llama-3.1-8b-instant")


class ChatOpenAINoStrict(ChatOpenAI):
    def bind_tools(self, tools, *, strict=None, **kwargs):
        return super().bind_tools(tools, **kwargs)


def make_llm(model: str = "gpt-4o") -> ChatOpenAINoStrict:
    # Map the old "mini" tier to the small model; everything else to the main model.
    resolved = LLM_MODEL_SMALL if "mini" in (model or "") else LLM_MODEL
    return ChatOpenAINoStrict(
        base_url=LLM_BASE_URL,
        api_key=LLM_API_KEY,
        model=resolved,
    )


def make_featherless_llm(model: str = None) -> ChatOpenAINoStrict:
    # Kept for the Synthesis agent; now points at the same provider as make_llm.
    return ChatOpenAINoStrict(
        base_url=LLM_BASE_URL,
        api_key=LLM_API_KEY,
        model=LLM_MODEL,
    )
