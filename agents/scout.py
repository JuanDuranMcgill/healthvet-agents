import asyncio
import logging
import os
from dotenv import load_dotenv
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from band import Agent
from band.adapters.langgraph import LangGraphAdapter
from band.config import load_agent_config
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from agents.llm import make_llm

logging.basicConfig(level=logging.INFO)

SYSTEM_PROMPT = """You are Scout, a healthcare vendor intelligence agent.

You will receive one of two request types:

--- TYPE 1: Fresh research request ---
Run all 4 searches in order:
1. tavily_web_search("[vendor] healthcare customer references case studies")
2. tavily_web_search("[vendor] lawsuit regulatory violation negative news")
3. exa_semantic_search("[vendor] health system implementation")
4. hhs_breach_check("[vendor]")

--- TYPE 2: VETO re-investigation ---
When you receive a message containing "VETO DIRECTIVES:", read each directive carefully and run targeted searches addressing each one. Use tavily_web_search and exa_semantic_search with queries specific to each directive. Run at least one search per directive.

--- After all searches (both types) ---
Call band_send_message ONCE with:
- mentions: ["@handmorin/forensics"]
- content structured as:

**SCOUT RESEARCH REPORT: [Vendor Name]**
[Add "(RE-INVESTIGATION)" to the title if this is a VETO re-investigation]

- Customer References: [findings]
- Legal & Regulatory Issues: [findings]
- Health System Implementations: [findings]
- HIPAA Breach Record: [findings]
[If re-investigation: add "Re-investigation Findings:" section with targeted results per directive]

Forensics, please begin your document and evidence analysis.

Do not call band_send_message more than once."""


@tool
def tavily_web_search(query: str) -> str:
    """General web search optimized for research. Use for customer references, news, lawsuits."""
    from tavily import TavilyClient
    client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    results = client.search(query, search_depth="advanced", max_results=5)
    output = []
    for r in results.get("results", []):
        output.append(f"[{r.get('title', '')}]\n{r.get('url', '')}\n{r.get('content', '')[:400]}")
    return "\n\n---\n\n".join(output) or "No results found."


@tool
def exa_semantic_search(query: str) -> str:
    """Neural/semantic search — finds relevant pages by meaning, not just keywords. Use for finding who uses this vendor."""
    from exa_py import Exa
    from exa_py.api import ContentsOptions
    exa = Exa(api_key=os.environ["EXA_API_KEY"])
    results = exa.search(
        query,
        num_results=5,
        type="neural",
        contents=ContentsOptions(text=True),
    )
    output = []
    for r in results.results:
        text = getattr(r, "text", "") or ""
        output.append(f"[{r.title}]\n{r.url}\n{text[:400]}")
    return "\n\n---\n\n".join(output) or "No results found."


@tool
def hhs_breach_check(vendor_name: str) -> str:
    """Search U.S. HHS HIPAA breach notification records and health security databases for this vendor."""
    from tavily import TavilyClient
    client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    results = client.search(
        f"{vendor_name} HIPAA data breach OCR notification",
        search_depth="advanced",
        max_results=5,
        include_domains=["hhs.gov", "ocrportal.hhs.gov", "hipaajournal.com",
                         "healthitsecurity.com", "databreaches.net"],
    )
    output = []
    for r in results.get("results", []):
        output.append(f"[{r.get('title', '')}]\n{r.get('url', '')}\n{r.get('content', '')[:400]}")
    return "\n\n---\n\n".join(output) or "No breach records found in searched databases."


async def main():
    load_dotenv()

    adapter = LangGraphAdapter(
        llm=make_llm(),
        checkpointer=InMemorySaver(),
        custom_section=SYSTEM_PROMPT,
        additional_tools=[tavily_web_search, exa_semantic_search, hhs_breach_check],
    )

    agent_id, api_key = load_agent_config("scout")
    agent = Agent.create(adapter=adapter, agent_id=agent_id, api_key=api_key)

    print("Scout agent running...")
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
