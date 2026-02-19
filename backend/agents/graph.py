from __future__ import annotations

import time
from typing import Dict, Any, List

from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI

from backend.config import settings
from backend.rag.regulation_store import retrieve_regulation_chunks
from backend.agents.state import AgentState
from backend.agents.tools import ast_summary, heuristic_signals
from backend.models.outputs import FileAnalysis, NarrativeSection, InlineControl


def _llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.OPENAI_MODEL,
        temperature=0,
        max_tokens=6000,
        api_key=settings.OPENAI_API_KEY,
    )


def node_retrieve_regulations(state: AgentState) -> AgentState:
    query = state["question"]
    chunks = retrieve_regulation_chunks(query, k=12)
    state["regulation_context"] = chunks
    return state


def node_local_analyzer(state: AgentState) -> AgentState:
    src = state["source_code"]
    lang = state["language"]
    state["ast_summary"] = ast_summary(src, lang)
    state["heuristics"] = heuristic_signals(src)
    return state


JSON_TEMPLATE = """
{
  "summary": "one-paragraph summary of what this file does and why it matters for compliance",
  "narrative_sections": [
    {
      "heading": "Overview of Business Logic",
      "explanation": "2–4 sentences"
    },
    {
      "heading": "Inline Controls Implemented",
      "explanation": "Describe inline controls; reference specific functions or lines."
    },
    {
      "heading": "Data Handling & Security Practices",
      "explanation": "Describe encryption, authentication, logging, and data flows."
    },
    {
      "heading": "Regulatory Alignment Notes",
      "explanation": "Explain how the code aligns with FDIC 370, OWASP, NIST, PCI-DSS, GLBA, using only claims you can directly support."
    }
  ],
  "inline_controls": [
    {
      "regulation": "FDIC-370|OWASP|NIST|PCI-DSS|GLBA",
      "section": "e.g. '12 CFR 330', 'Part 370', 'OWASP A03:2021', 'NIST AC-3'",
      "title": "short label for the inline control",
      "description": "what the control is and how this code implements it, phrased cautiously and tied to specific code and regulation snippets",
      "evidence_snippet": "exact function name, constant, or short code excerpt you relied on",
      "confidence": "HIGH|MEDIUM|LOW"
    }
  ],
  "qualitative_risk": "Very Low|Low|Moderate|Elevated|Severe",
  "reasoning_trace": [
    "Step 1: ...",
    "Step 2: ...",
    "Step 3: ..."
  ]
}
""".strip()


def node_llm_analyst(state: AgentState) -> AgentState:
    llm = _llm()

    filename = state["filename"]
    language = state["language"]
    code = state["source_code"]
    regs = state["regulation_context"]
    ast_info = state["ast_summary"]
    hints = state["heuristics"]

    reg_block = "\n\n".join(
        f"[REG-{i+1}] {chunk}" for i, chunk in enumerate(regs)
    )

    prompt = (
        "You are a senior financial-technology code reviewer and compliance analyst.\n\n"
        "You are given:\n"
        "- The full source of ONE file.\n"
        "- Regulation context snippets for FDIC, OWASP, NIST, PCI-DSS, and GLBA.\n\n"
        "Your task is DESCRIPTIVE and EVIDENCE-BASED only:\n"
        "- Do NOT mark controls as PASS or FAIL.\n"
        "- Do NOT propose fixes or remediation.\n"
        "- Do NOT assign numeric risk scores.\n"
        "- Do NOT invent precise counts or subsection numbers that are not clearly present in the code or the regulation context.\n\n"
        "Evidence discipline:\n"
        "- Only state a claim if you can tie it to BOTH (a) specific code and (b) at least one regulation snippet in the context.\n"
        "- If you cannot see a full list of FDIC ownership categories, do NOT say things like '2 of 9 categories'; instead say ownership support appears incomplete.\n"
        "- Do NOT mention 'beneficial owner tracking' or similar concepts unless those exact ideas appear in the code or the provided snippets.\n"
        "- For missing/invalid depositor data, you MAY say that such data is not routed to an exception or control workflow IF the code clearly shows silent drop or ignore behavior.\n\n"
        "FDIC-specific guidance:\n"
        "- The FDIC Standard Maximum Deposit Insurance Amount (SMDIA) is $250,000 per depositor, per insured bank, per ownership category.\n"
        "- If the code hardcodes a different insurance limit (e.g. 100000), you MAY state that this conflicts with SMDIA and therefore with alignment to FDIC Part 330 / Part 370.\n"
        "- For ownership categories, use cautious phrasing such as:\n"
        "  'Ownership category handling appears incomplete relative to FDIC Part 330 categories and Part 370 right-and-capacity reporting.'\n"
        "  Do NOT assert exact counts (e.g. '2 of 9') unless they are explicitly shown.\n\n"
        "OWASP / Injection:\n"
        "- If you see SQL or other commands built by raw string concatenation/interpolation with untrusted data, you MAY map this to OWASP Top 10 A03:2021 Injection.\n"
        "- Only do this when you can point to specific lines or functions that build such queries.\n\n"
        "NIST / PCI-DSS / GLBA:\n"
        "- You MAY use NIST SP 800-53 family IDs (e.g., AC-*, AU-*, SC-*) as a control lens.\n"
        "- Treat PCI-DSS and GLBA as conditional: use language like 'If this system is in PCI-DSS scope, controls X/Y would be expected but are not visible in this code.'\n"
        "- Do NOT assert that PCI-DSS or GLBA are legally required unless that is stated explicitly in the regulation snippets you see.\n\n"
        "Your output:\n"
        "1) Explain what the code DOES in clear language for a CRO / CTO.\n"
        "2) Identify INLINE CONTROLS that are present in the code, each mapped to one of:\n"
        "   - FDIC Part 330 / Part 370\n"
        "   - OWASP secure coding / OWASP Top 10\n"
        "   - NIST SP 800-53 (families AC, AU, SC, SI, etc.)\n"
        "   - PCI-DSS v4.0 (conditionally, if in scope)\n"
        "   - GLBA Safeguards (conditionally, if in scope)\n"
        "   For each control, include:\n"
        "   - regulation (one of FDIC-370, OWASP, NIST, PCI-DSS, GLBA)\n"
        "   - section (e.g. '12 CFR 330', 'Part 370', 'OWASP A03:2021', 'NIST AC-3')\n"
        "   - title, description, evidence_snippet, confidence.\n"
        "3) Provide a QUALITATIVE risk level only: Very Low / Low / Moderate / Elevated / Severe.\n"
        "   Qualify your language when needed (e.g. 'If this module is used in production for deposit insurance calculations, this would be Elevated risk.').\n"
        "4) Provide a short reasoning trace listing your steps.\n\n"
        "Use the regulation excerpts below as your primary source of truth.\n\n"
        "=== REGULATION CONTEXT START ===\n"
        f"{reg_block}\n"
        "=== REGULATION CONTEXT END ===\n\n"
        "CONTEXT ABOUT THE FILE:\n"
        f"- Filename: {filename}\n"
        f"- Language: {language}\n"
        f"- AST summary: {ast_info}\n"
        f"- Heuristic signals (lines with potential interest): {hints}\n\n"
        "SOURCE CODE:\n"
        f"```{language}\n{code[:12000]}\n```\n\n"
        "OUTPUT STRICTLY AS JSON with this structure:\n\n"
        f"{JSON_TEMPLATE}\n\n"
        "Return ONLY JSON. No markdown, no extra text."
    )

    resp = llm.invoke([{"role": "user", "content": prompt}])
    raw = getattr(resp, "content", str(resp))

    import json
    try:
        data = json.loads(raw)
    except Exception:
        data = {
            "summary": "LLM response could not be parsed as JSON.",
            "narrative_sections": [],
            "inline_controls": [],
            "qualitative_risk": "Moderate",
            "reasoning_trace": [raw[:500]],
        }

    state["narrative"] = data.get("summary", "")
    state["inline_controls"] = data.get("inline_controls", [])
    state["reasoning_trace"] = data.get("reasoning_trace", [])
    state["narrative_sections"] = data.get("narrative_sections", [])
    state["qualitative_risk"] = data.get("qualitative_risk", "Moderate")
    return state


_graph = None


def _get_graph():
    global _graph
    if _graph is not None:
        return _graph

    g = StateGraph(AgentState)
    g.add_node("retrieve_regulations", node_retrieve_regulations)
    g.add_node("local_analyzer", node_local_analyzer)
    g.add_node("llm_analyst", node_llm_analyst)

    g.set_entry_point("retrieve_regulations")
    g.add_edge("retrieve_regulations", "local_analyzer")
    g.add_edge("local_analyzer", "llm_analyst")
    g.add_edge("llm_analyst", END)

    _graph = g.compile()
    return _graph


async def analyze_file_agentic(filename: str, source_code: str, language: str) -> FileAnalysis:
    start = time.time()
    graph = _get_graph()

    state: AgentState = {
        "filename": filename,
        "language": language,
        "source_code": source_code,
        "question": (
            f"How does {filename} ({language}) implement inline controls and "
            "regulatory alignment for FDIC Part 370, OWASP, NIST, PCI-DSS, GLBA?"
        ),
        "regulation_context": [],
        "ast_summary": {},
        "heuristics": {},
        "narrative": "",
        "narrative_sections": [],
        "inline_controls": [],
        "qualitative_risk": "Moderate",
        "reasoning_trace": [],
    }

    final_state = graph.invoke(state)

    ast_info = final_state["ast_summary"]
    sections_raw: List[Dict[str, Any]] = final_state.get("narrative_sections", [])
    sections = [
        NarrativeSection(
            heading=s.get("heading", ""),
            explanation=s.get("explanation", ""),
        )
        for s in sections_raw
    ]

    controls = [
        InlineControl(
            regulation=c.get("regulation", ""),
            section=c.get("section", ""),
            title=c.get("title", ""),
            description=c.get("description", ""),
            evidence_snippet=c.get("evidence_snippet", ""),
            confidence=c.get("confidence", "MEDIUM"),
        )
        for c in final_state.get("inline_controls", [])
    ]

    risk = final_state.get("qualitative_risk") or "Moderate"
    duration_ms = int((time.time() - start) * 1000)

    return FileAnalysis(
        filename=filename,
        language=language,
        lines_of_code=ast_info.get("lines", len(source_code.splitlines())),
        regulatory_focus=["FDIC-370", "OWASP", "NIST", "PCI-DSS", "GLBA"],
        summary=final_state.get("narrative", ""),
        narrative_sections=sections,
        inline_controls=controls,
        qualitative_risk=risk,
        reasoning_trace=final_state.get("reasoning_trace", []),
        analysis_duration_ms=duration_ms,
    )
