"""
Shared LLM factory. Subclasses ChatOpenAI to drop strict=True from bind_tools —
langchain.agents.create_agent hardcodes strict=True, which causes 400 errors on
AI/ML API because Band SDK tool schemas contain anyOf (optional fields).
"""
import os
from langchain_openai import ChatOpenAI


class ChatOpenAINoStrict(ChatOpenAI):
    def bind_tools(self, tools, *, strict=None, **kwargs):
        return super().bind_tools(tools, **kwargs)


def make_llm(model: str = "gpt-4o") -> ChatOpenAINoStrict:
    return ChatOpenAINoStrict(
        base_url="https://api.aimlapi.com/v1",
        api_key=os.getenv("AIML_API_KEY"),
        model=model,
    )


def make_featherless_llm(model: str = "Qwen/Qwen2.5-72B-Instruct") -> ChatOpenAINoStrict:
    return ChatOpenAINoStrict(
        base_url="https://api.featherless.ai/v1",
        api_key=os.getenv("FEATHERLESS_API_KEY"),
        model=model,
    )
