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


class ChatOpenAINoStrict(ChatOpenAI):
    def bind_tools(self, tools, *, strict=None, **kwargs):
        return super().bind_tools(tools, **kwargs)


def make_llm(model: str = "gpt-4o") -> ChatOpenAINoStrict:
    # Read env at call time (after load_dotenv) — not at import.
    base_url = os.getenv("AIML_BASE_URL", "https://api.aimlapi.com/v1")
    api_key = os.getenv("AIML_API_KEY")
    main_model = os.getenv("AIML_MODEL", "gpt-4o")
    small_model = os.getenv("AIML_MODEL_SMALL", "gpt-4o-mini")
    resolved = small_model if "mini" in (model or "") else main_model
    return ChatOpenAINoStrict(base_url=base_url, api_key=api_key, model=resolved)


def make_featherless_llm(model: str = None) -> ChatOpenAINoStrict:
    base_url = os.getenv("FEATHERLESS_BASE_URL", "https://api.featherless.ai/v1")
    api_key = os.getenv("FEATHERLESS_API_KEY")
    resolved = model or os.getenv("FEATHERLESS_MODEL", "Qwen/Qwen2.5-72B-Instruct")
    return ChatOpenAINoStrict(base_url=base_url, api_key=api_key, model=resolved)
