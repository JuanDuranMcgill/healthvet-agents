"""
Shared LLM factory — provider-agnostic via env vars (OpenAI-compatible APIs).

Architecture (the sponsors' stack):
  - make_llm()            -> AI/ML API  (the 6 agents: gpt-4o / gpt-4o-mini)
  - make_featherless_llm()-> Featherless (Synthesis: Qwen2.5-72B)

Every endpoint/model/key is env-overridable, so you can repoint to any
OpenAI-compatible provider (e.g. free Groq) without code changes:
  AIML_BASE_URL / AIML_API_KEY / AIML_MODEL / AIML_MODEL_SMALL
  FEATHERLESS_BASE_URL / FEATHERLESS_API_KEY / FEATHERLESS_MODEL

ChatOpenAINoStrict drops strict=True from bind_tools: langchain.agents.create_agent
hardcodes strict=True, which 400s on providers whose tool schemas contain anyOf
(optional fields), e.g. the Band SDK tools.
"""
import os
from langchain_openai import ChatOpenAI

# --- Agents: AI/ML API ---
AIML_BASE_URL = os.getenv("AIML_BASE_URL", "https://api.aimlapi.com/v1")
AIML_API_KEY = os.getenv("AIML_API_KEY")
AIML_MODEL = os.getenv("AIML_MODEL", "gpt-4o")
AIML_MODEL_SMALL = os.getenv("AIML_MODEL_SMALL", "gpt-4o-mini")

# --- Synthesis: Featherless ---
FEATHERLESS_BASE_URL = os.getenv("FEATHERLESS_BASE_URL", "https://api.featherless.ai/v1")
FEATHERLESS_API_KEY = os.getenv("FEATHERLESS_API_KEY")
FEATHERLESS_MODEL = os.getenv("FEATHERLESS_MODEL", "Qwen/Qwen2.5-72B-Instruct")


class ChatOpenAINoStrict(ChatOpenAI):
    def bind_tools(self, tools, *, strict=None, **kwargs):
        return super().bind_tools(tools, **kwargs)


def make_llm(model: str = "gpt-4o") -> ChatOpenAINoStrict:
    resolved = AIML_MODEL_SMALL if "mini" in (model or "") else AIML_MODEL
    return ChatOpenAINoStrict(
        base_url=AIML_BASE_URL,
        api_key=AIML_API_KEY,
        model=resolved,
    )


def make_featherless_llm(model: str = None) -> ChatOpenAINoStrict:
    return ChatOpenAINoStrict(
        base_url=FEATHERLESS_BASE_URL,
        api_key=FEATHERLESS_API_KEY,
        model=model or FEATHERLESS_MODEL,
    )
