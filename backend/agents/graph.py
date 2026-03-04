# from __future__ import annotations

# import time
# from typing import Dict, Any, List

# from langgraph.graph import StateGraph, END
# from langchain_openai import ChatOpenAI

# from backend.config import settings
# from backend.rag.regulation_store import retrieve_regulation_chunks
# from backend.agents.state import AgentState
# from backend.agents.tools import ast_summary, heuristic_signals
# from backend.models.outputs import FileAnalysis, NarrativeSection, InlineControl


# def _llm() -> ChatOpenAI:
#     return ChatOpenAI(
#         model=settings.OPENAI_MODEL,
#         temperature=0,
#         max_tokens=6000,
#         api_key=settings.OPENAI_API_KEY,
#     )


# def node_retrieve_regulations(state: AgentState) -> AgentState:
#     query = state["question"]
#     chunks = retrieve_regulation_chunks(query, k=12)
#     state["regulation_context"] = chunks
#     return state


# def node_local_analyzer(state: AgentState) -> AgentState:
#     src = state["source_code"]
#     lang = state["language"]
#     state["ast_summary"] = ast_summary(src, lang)
#     state["heuristics"] = heuristic_signals(src)
#     return state


# JSON_TEMPLATE = """
# {
#   "summary": "one-paragraph summary of what this file does and why it matters for compliance",
#   "narrative_sections": [
#     {
#       "heading": "Overview of Business Logic",
#       "explanation": "2–4 sentences"
#     },
#     {
#       "heading": "Inline Controls Implemented",
#       "explanation": "Describe inline controls; reference specific functions or lines."
#     },
#     {
#       "heading": "Data Handling & Security Practices",
#       "explanation": "Describe encryption, authentication, logging, and data flows."
#     },
#     {
#       "heading": "Regulatory Alignment Notes",
#       "explanation": "Explain how the code aligns with FDIC 370, OWASP, NIST, PCI-DSS, GLBA, using only claims you can directly support."
#     }
#   ],
#   "inline_controls": [
#     {
#       "regulation": "FDIC-370|OWASP|NIST|PCI-DSS|GLBA",
#       "section": "e.g. '12 CFR 330', 'Part 370', 'OWASP A03:2021', 'NIST AC-3'",
#       "title": "short label for the inline control",
#       "description": "what the control is and how this code implements it, phrased cautiously and tied to specific code and regulation snippets",
#       "evidence_snippet": "exact function name, constant, or short code excerpt you relied on",
#       "confidence": "HIGH|MEDIUM|LOW"
#     }
#   ],
#   "qualitative_risk": "Very Low|Low|Moderate|Elevated|Severe",
#   "reasoning_trace": [
#     "Step 1: ...",
#     "Step 2: ...",
#     "Step 3: ..."
#   ]
# }
# """.strip()


# def node_llm_analyst(state: AgentState) -> AgentState:
#     llm = _llm()

#     filename = state["filename"]
#     language = state["language"]
#     code = state["source_code"]
#     regs = state["regulation_context"]
#     ast_info = state["ast_summary"]
#     hints = state["heuristics"]

#     reg_block = "\n\n".join(
#         f"[REG-{i+1}] {chunk}" for i, chunk in enumerate(regs)
#     )

#     prompt = (
#         "You are a senior financial-technology code reviewer and compliance analyst.\n\n"
#         "You are given:\n"
#         "- The full source of ONE file.\n"
#         "- Regulation context snippets for FDIC, OWASP, NIST, PCI-DSS, and GLBA.\n\n"
#         "Your task is DESCRIPTIVE and EVIDENCE-BASED only:\n"
#         "- Do NOT mark controls as PASS or FAIL.\n"
#         "- Do NOT propose fixes or remediation.\n"
#         "- Do NOT assign numeric risk scores.\n"
#         "- Do NOT invent precise counts or subsection numbers that are not clearly present in the code or the regulation context.\n\n"
#         "Evidence discipline:\n"
#         "- Only state a claim if you can tie it to BOTH (a) specific code and (b) at least one regulation snippet in the context.\n"
#         "- If you cannot see a full list of FDIC ownership categories, do NOT say things like '2 of 9 categories'; instead say ownership support appears incomplete.\n"
#         "- Do NOT mention 'beneficial owner tracking' or similar concepts unless those exact ideas appear in the code or the provided snippets.\n"
#         "- For missing/invalid depositor data, you MAY say that such data is not routed to an exception or control workflow IF the code clearly shows silent drop or ignore behavior.\n\n"
#         "FDIC-specific guidance:\n"
#         "- The FDIC Standard Maximum Deposit Insurance Amount (SMDIA) is $250,000 per depositor, per insured bank, per ownership category.\n"
#         "- If the code hardcodes a different insurance limit (e.g. 100000), you MAY state that this conflicts with SMDIA and therefore with alignment to FDIC Part 330 / Part 370.\n"
#         "- For ownership categories, use cautious phrasing such as:\n"
#         "  'Ownership category handling appears incomplete relative to FDIC Part 330 categories and Part 370 right-and-capacity reporting.'\n"
#         "  Do NOT assert exact counts (e.g. '2 of 9') unless they are explicitly shown.\n\n"
#         "OWASP / Injection:\n"
#         "- If you see SQL or other commands built by raw string concatenation/interpolation with untrusted data, you MAY map this to OWASP Top 10 A03:2021 Injection.\n"
#         "- Only do this when you can point to specific lines or functions that build such queries.\n\n"
#         "NIST / PCI-DSS / GLBA:\n"
#         "- You MAY use NIST SP 800-53 family IDs (e.g., AC-*, AU-*, SC-*) as a control lens.\n"
#         "- Treat PCI-DSS and GLBA as conditional: use language like 'If this system is in PCI-DSS scope, controls X/Y would be expected but are not visible in this code.'\n"
#         "- Do NOT assert that PCI-DSS or GLBA are legally required unless that is stated explicitly in the regulation snippets you see.\n\n"
#         "Your output:\n"
#         "1) Explain what the code DOES in clear language for a CRO / CTO.\n"
#         "2) Identify INLINE CONTROLS that are present in the code, each mapped to one of:\n"
#         "   - FDIC Part 330 / Part 370\n"
#         "   - OWASP secure coding / OWASP Top 10\n"
#         "   - NIST SP 800-53 (families AC, AU, SC, SI, etc.)\n"
#         "   - PCI-DSS v4.0 (conditionally, if in scope)\n"
#         "   - GLBA Safeguards (conditionally, if in scope)\n"
#         "   For each control, include:\n"
#         "   - regulation (one of FDIC-370, OWASP, NIST, PCI-DSS, GLBA)\n"
#         "   - section (e.g. '12 CFR 330', 'Part 370', 'OWASP A03:2021', 'NIST AC-3')\n"
#         "   - title, description, evidence_snippet, confidence.\n"
#         "3) Provide a QUALITATIVE risk level only: Very Low / Low / Moderate / Elevated / Severe.\n"
#         "   Qualify your language when needed (e.g. 'If this module is used in production for deposit insurance calculations, this would be Elevated risk.').\n"
#         "4) Provide a short reasoning trace listing your steps.\n\n"
#         "Use the regulation excerpts below as your primary source of truth.\n\n"
#         "=== REGULATION CONTEXT START ===\n"
#         f"{reg_block}\n"
#         "=== REGULATION CONTEXT END ===\n\n"
#         "CONTEXT ABOUT THE FILE:\n"
#         f"- Filename: {filename}\n"
#         f"- Language: {language}\n"
#         f"- AST summary: {ast_info}\n"
#         f"- Heuristic signals (lines with potential interest): {hints}\n\n"
#         "SOURCE CODE:\n"
#         f"```{language}\n{code[:12000]}\n```\n\n"
#         "OUTPUT STRICTLY AS JSON with this structure:\n\n"
#         f"{JSON_TEMPLATE}\n\n"
#         "Return ONLY JSON. No markdown, no extra text."
#     )

#     resp = llm.invoke([{"role": "user", "content": prompt}])
#     raw = getattr(resp, "content", str(resp))

#     import json
#     try:
#         data = json.loads(raw)
#     except Exception:
#         data = {
#             "summary": "LLM response could not be parsed as JSON.",
#             "narrative_sections": [],
#             "inline_controls": [],
#             "qualitative_risk": "Moderate",
#             "reasoning_trace": [raw[:500]],
#         }

#     state["narrative"] = data.get("summary", "")
#     state["inline_controls"] = data.get("inline_controls", [])
#     state["reasoning_trace"] = data.get("reasoning_trace", [])
#     state["narrative_sections"] = data.get("narrative_sections", [])
#     state["qualitative_risk"] = data.get("qualitative_risk", "Moderate")
#     return state


# _graph = None


# def _get_graph():
#     global _graph
#     if _graph is not None:
#         return _graph

#     g = StateGraph(AgentState)
#     g.add_node("retrieve_regulations", node_retrieve_regulations)
#     g.add_node("local_analyzer", node_local_analyzer)
#     g.add_node("llm_analyst", node_llm_analyst)

#     g.set_entry_point("retrieve_regulations")
#     g.add_edge("retrieve_regulations", "local_analyzer")
#     g.add_edge("local_analyzer", "llm_analyst")
#     g.add_edge("llm_analyst", END)

#     _graph = g.compile()
#     return _graph


# async def analyze_file_agentic(filename: str, source_code: str, language: str) -> FileAnalysis:
#     start = time.time()
#     graph = _get_graph()

#     state: AgentState = {
#         "filename": filename,
#         "language": language,
#         "source_code": source_code,
#         "question": (
#             f"How does {filename} ({language}) implement inline controls and "
#             "regulatory alignment for FDIC Part 370, OWASP, NIST, PCI-DSS, GLBA?"
#         ),
#         "regulation_context": [],
#         "ast_summary": {},
#         "heuristics": {},
#         "narrative": "",
#         "narrative_sections": [],
#         "inline_controls": [],
#         "qualitative_risk": "Moderate",
#         "reasoning_trace": [],
#     }

#     final_state = graph.invoke(state)

#     ast_info = final_state["ast_summary"]
#     sections_raw: List[Dict[str, Any]] = final_state.get("narrative_sections", [])
#     sections = [
#         NarrativeSection(
#             heading=s.get("heading", ""),
#             explanation=s.get("explanation", ""),
#         )
#         for s in sections_raw
#     ]

#     controls = [
#         InlineControl(
#             regulation=c.get("regulation", ""),
#             section=c.get("section", ""),
#             title=c.get("title", ""),
#             description=c.get("description", ""),
#             evidence_snippet=c.get("evidence_snippet", ""),
#             confidence=c.get("confidence", "MEDIUM"),
#         )
#         for c in final_state.get("inline_controls", [])
#     ]

#     risk = final_state.get("qualitative_risk") or "Moderate"
#     duration_ms = int((time.time() - start) * 1000)

#     return FileAnalysis(
#         filename=filename,
#         language=language,
#         lines_of_code=ast_info.get("lines", len(source_code.splitlines())),
#         regulatory_focus=["FDIC-370", "OWASP", "NIST", "PCI-DSS", "GLBA"],
#         summary=final_state.get("narrative", ""),
#         narrative_sections=sections,
#         inline_controls=controls,
#         qualitative_risk=risk,
#         reasoning_trace=final_state.get("reasoning_trace", []),
#         analysis_duration_ms=duration_ms,
#     )


from __future__ import annotations

import asyncio
import re
import time
import json
import pathlib
from typing import Dict, Any, List

from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI

from backend.config import settings
from backend.rag.regulation_store import retrieve_regulation_chunks, retrieve_controls_with_metadata
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
    """Retrieve regulation chunks using code-signal-aware queries.

    This node runs AFTER node_local_analyzer so it can use AST findings and
    heuristic signals to build targeted semantic queries rather than just
    searching on the filename.  Multiple focused queries are issued and
    deduplicated so the LLM receives the most relevant regulation and
    control-description chunks for the specific code being analysed.
    """
    ast_info = state.get("ast_summary", {})
    code = state.get("source_code", "")[:3000]
    code_lower = code.lower()

    # Start with the base question, then add signal-driven queries
    queries: List[str] = [state["question"]]

    if ast_info.get("has_auth"):
        queries.append("FDIC 370 access control authentication authorization deposit records")
    if ast_info.get("has_db"):
        queries.append("FDIC 370 recordkeeping account data storage depositor records")
    if ast_info.get("has_logging"):
        queries.append("FDIC 370 audit trail logging data modification timestamp")
    if ast_info.get("has_encryption"):
        queries.append("FDIC 370 security encryption sensitive depositor data protection")

    if any(kw in code_lower for kw in ("insurance", "smdia", "250000", "250_000")):
        queries.append("FDIC SMDIA insurance limit 250000 aggregation determination ownership")
    if any(kw in code_lower for kw in ("ownership", "category", "ownership_category")):
        queries.append("FDIC ownership category right and capacity depositor aggregation")
    if any(kw in code_lower for kw in ("beneficiar", "pod", "revocable", "trust")):
        queries.append("FDIC POD beneficiary trust revocable ownership designation insurance")
    if "reconcil" in code_lower:
        queries.append("FDIC reconciliation balance data quality discrepancy detection")
    if any(kw in code_lower for kw in ("retent", "purge", "archive")):
        queries.append("FDIC data retention deposit records five year minimum")

    seen: set = set()
    all_chunks: List[str] = []
    for q in queries:
        for chunk in retrieve_regulation_chunks(q, k=6):
            if chunk not in seen:
                seen.add(chunk)
                all_chunks.append(chunk)
        if len(all_chunks) >= 18:
            break

    state["regulation_context"] = all_chunks[:18]
    return state


def node_local_analyzer(state: AgentState) -> AgentState:
    src = state["source_code"]
    lang = state["language"]
    state["ast_summary"] = ast_summary(src, lang)
    state["heuristics"] = heuristic_signals(src)
    return state


JSON_TEMPLATE = """
{
  "summary": "One-paragraph description of what this file currently does.",
  "narrative_sections": [
    {
      "heading": "Overview of Business Logic",
      "explanation": "2–4 sentences describing only the current implemented behavior, in present tense, with no recommendations."
    },
    {
      "heading": "Inline Controls Present",
      "explanation": "Describe only inline controls that EXIST in the code (constants, checks, logging, auth, validation), tied to specific functions or lines."
    },
    {
      "heading": "Data Handling & Security Practices",
      "explanation": "Describe how data is handled today: queries, logging, error handling, encryption usage, etc., with no suggestions."
    }
  ],
  "inline_controls": [
    {
      "regulation": "FDIC-370",
      "section": "e.g. '12 CFR 370.4(a)'",
      "title": "short label for the inline control",
      "control_statement": "factual description of what the code actually does as a control, in present tense.",
      "code_excerpt": "short code snippet or constant/function body fragment",
      "line_start": 1,
      "line_end": 1
    }
  ],
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
        "- Regulation context snippets for FDIC Part 370.\n\n"
        "STRICT RULES (VERY IMPORTANT):\n"
        "- Your task is purely DESCRIPTIVE and EVIDENCE-BASED.\n"
        "- Describe ONLY what is present in the code.\n"
        "- Do NOT propose fixes or remediation.\n"
        "- Do NOT say what the code 'should' do or 'must' do.\n"
        "- Do NOT use words like 'should', 'must', 'recommend', 'needs', 'lacks', 'missing', 'fix', 'improve'.\n"
        "- Do NOT label anything as PASS/FAIL and do NOT assign risk levels.\n"
        "- Every sentence must be directly supported by the code and/or a regulation snippet.\n\n"
        "Inline controls:\n"
        "- Only output controls that clearly EXIST in the code (constants, checks, validation, logging, authentication, etc.).\n"
        "- For each control, specify the regulation, section, a short title, a factual control_statement, the exact code_excerpt, and line_start/line_end.\n"
        "- Do NOT output hypothetical or desired controls.\n\n"
        "Reasoning trace:\n"
        "- Provide a short sequence of steps describing what you inspected "
        "(e.g. 'Step 1: Located INSURANCE_LIMIT constant at line 5.').\n"
        "- Each step must reference concrete observations.\n\n"
        "Use the regulation excerpts below as context lenses only.\n\n"
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

    try:
        data = json.loads(raw)
    except Exception:
        data = {
            "summary": "LLM response could not be parsed as JSON.",
            "narrative_sections": [],
            "inline_controls": [],
            "reasoning_trace": [raw[:500]],
        }

    state["narrative"] = data.get("summary", "")
    state["inline_controls"] = data.get("inline_controls", [])
    state["reasoning_trace"] = data.get("reasoning_trace", [])
    state["narrative_sections"] = data.get("narrative_sections", [])
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

    # local_analyzer runs first so retrieve_regulations can use AST signals
    # to build targeted RAG queries instead of just searching on the filename.
    g.set_entry_point("local_analyzer")
    g.add_edge("local_analyzer", "retrieve_regulations")
    g.add_edge("retrieve_regulations", "llm_analyst")
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
            f"Describe what {filename} ({language}) currently does and "
            "which inline controls are present relative to FDIC Part 370."
        ),
        "regulation_context": [],
        "ast_summary": {},
        "heuristics": {},
        "narrative": "",
        "narrative_sections": [],
        "inline_controls": [],
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

    controls: List[InlineControl] = []
    for c in final_state.get("inline_controls", []):
        controls.append(
            InlineControl(
                regulation=c.get("regulation", ""),
                section=c.get("section", ""),
                title=c.get("title", ""),
                control_statement=c.get("control_statement", ""),
                code_excerpt=c.get("code_excerpt", ""),
                line_start=int(c.get("line_start", 1) or 1),
                line_end=int(c.get("line_end", c.get("line_start", 1) or 1)),
            )
        )

    duration_ms = int((time.time() - start) * 1000)
    loc = ast_info.get("lines", len(source_code.splitlines()))
    reasoning = final_state.get("reasoning_trace", [])

    # Heuristically detect missing controls
    missing_controls = []
    if not ast_info.get("has_logging"):
        missing_controls.append("audit_log / logging")
    if not ast_info.get("has_error_handling"):
        missing_controls.append("error_handling")
    if not ast_info.get("has_auth"):
        missing_controls.append("authentication / authorization")
    if not ast_info.get("has_encryption"):
        missing_controls.append("encryption_usage_detected")

    return FileAnalysis(
        filename=filename,
        language=language,
        lines_of_code=loc,
        regulatory_focus=["FDIC-370"],
        technical_findings_count=len(reasoning),
        inline_controls_count=len(controls),
        summary=final_state.get("narrative", ""),
        narrative_sections=sections,
        reasoning_trace=reasoning,
        inline_controls=controls,
        missing_controls=missing_controls,
        qualitative_risk=final_state.get("qualitative_risk", "Moderate"),
        analysis_duration_ms=duration_ms,
    )


# ============================================================
# FDIC 12 CFR Part 370 — Full Compliance Analysis Pipeline
# ============================================================

from backend.models.outputs import (
    FDIC370Analysis, FDICControlFinding, FDICCoverageStats,
    FDICExecutiveSummary, FDICCodeLineageEdge,
    FDICDataLineage, FDICDataLineageNode, FDICDataLineageEdge,
    FDICRemediationPlan, FDICRemediationItem, FDICEvidenceItem,
)

def _load_fdic_controls_from_json() -> list:
    """Load FDIC 370 controls from regulations/fdic_370_controls.json.

    Each entry is normalised to a 4-tuple:
        (requirement_id, source_location, title, rule_description)
    where *title* is the first sentence of rule_description (≤120 chars).
    """
    _HERE = pathlib.Path(__file__).resolve().parent          # backend/agents/
    _JSON = _HERE.parent.parent / "regulations" / "fdic_370_controls.json"
    try:
        with _JSON.open(encoding="utf-8") as fh:
            data = json.load(fh)
        controls = []
        for req in data.get("requirements", []):
            req_id = req.get("requirement_id", "UNKNOWN")
            rule_type = req.get("rule_type", "control_requirement")
            section = rule_type.replace("_", " ").title()   # e.g. "Control Requirement"
            description = req.get("rule_description", "")
            # Derive a short title from the first sentence (cap at 120 chars)
            first_sentence = description.split(".")[0].strip()
            title = first_sentence[:120] if first_sentence else req_id
            control_type = req.get("control_type", "")
            applicable_fields = req.get("applicable_fields", [])
            controls.append((req_id, section, title, description, control_type, applicable_fields))
        return controls
    except Exception as exc:  # pragma: no cover
        import warnings
        warnings.warn(
            f"Could not load fdic_370_controls.json ({exc}); falling back to empty list."
        )
        return []


FDIC_370_CONTROLS = _load_fdic_controls_from_json()

FDIC370_JSON_TEMPLATE = r"""
{
  "executive_summary": {
    "posture": "Severe|High|Medium|Low",
    "top_critical_gaps": ["gap 1 description", "gap 2 description"],
    "immediate_priorities": ["priority 1", "priority 2"]
  },
  "control_findings": [
    {
      "control_id": "R-CTL-ac034e",
      "status": "PASS|PARTIAL|FAIL",
      "severity": "Severe|High|Medium|Low",
      "confidence": 0.85,
      "evidence": [
        {
          "signal": "short signal name",
          "file": "filename.py",
          "start_line": 10,
          "end_line": 15,
          "snippet": "exact code excerpt",
          "explanation": "why this is evidence for or against the control"
        }
      ],
      "gap": "concise description of what is missing or partial (empty string if PASS)",
      "remediation": "concise engineering action to address the gap (empty string if PASS)"
    }
  ],
  "code_lineage": [
    {
      "source": "module:function",
      "target": "module:function",
      "description": "brief relationship description"
    }
  ],
  "data_lineage": {
    "nodes": [
      { "id": "src1",  "label": "Source table or file",   "type": "source",    "details": "Primary data source description" },
      { "id": "t1",    "label": "Processing function",     "type": "transform", "details": "Transformation step description" },
      { "id": "out1",  "label": "Report or API output",   "type": "target",    "details": "Output description" }
    ],
    "edges": [
      { "from": "src1", "to": "t1",   "label": "reads" },
      { "from": "t1",   "to": "out1", "label": "produces" }
    ]
  },
  "remediation_plan": {
    "phase1_critical": [
      {
        "priority": 1,
        "action": "action description",
        "control_ids": ["R-CTL-ac034e"],
        "rationale": "why this is critical"
      }
    ],
    "phase2_structural": [
      {
        "priority": 1,
        "action": "action description",
        "control_ids": ["R-DQ-402c1c"],
        "rationale": "rationale"
      }
    ],
    "phase3_governance": [
      {
        "priority": 1,
        "action": "action description",
        "control_ids": ["R-DOC-7466b2"],
        "rationale": "rationale"
      }
    ]
  }
}
""".strip()


def _build_control_library_text() -> str:
    lines = ["FDIC 12 CFR Part 370 Control Library (Derived from Regulatory Framework)\n"]
    section_map: dict = {}
    for ctrl in FDIC_370_CONTROLS:
        ctrl_id, section, title, intent, *_ = ctrl
        # JSON IDs are like R-CTL-ac034e → prefix is the first two dash-segments
        parts = ctrl_id.split("-")
        prefix = "-".join(parts[:2]) if len(parts) >= 3 else parts[0]
        section_map.setdefault(prefix, []).append(ctrl)

    labels = {
        # JSON-sourced prefixes
        "R-CTL": "Control Requirements",
        "R-DQ":  "Data Quality Thresholds",
        "R-DOC": "Documentation Requirements",
        "R-EC":  "Enumeration Constraints",
        "R-RI":  "Referential Integrity",
        "R-TL":  "Update Timeline Requirements",
        "R-UPD": "Update Requirements",
    }
    for prefix, ctrl_list in section_map.items():
        lines.append(f"\n[{labels.get(prefix, prefix)}]")
        for ctrl_id, section, title, intent in ctrl_list:
            lines.append(f"  {ctrl_id} ({section}): {title} — {intent}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Regulation chunk cache — the FDIC 370 query is always the same fixed string
# so FAISS only runs once per process lifetime.
# ---------------------------------------------------------------------------
_FDIC370_REG_CHUNKS: List[str] = []


def _get_cached_fdic_reg_chunks(k: int = 8) -> List[str]:
    global _FDIC370_REG_CHUNKS  # pylint: disable=global-statement
    if not _FDIC370_REG_CHUNKS:
        _FDIC370_REG_CHUNKS = retrieve_regulation_chunks(
            "FDIC 12 CFR Part 370 recordkeeping insurance determination ownership category", k=k
        )
    return _FDIC370_REG_CHUNKS


# ---------------------------------------------------------------------------
# Per-batch LLM response template (control_findings only)
# ---------------------------------------------------------------------------
_FDIC370_BATCH_TEMPLATE = r"""
{
  "control_findings": [
    {
      "control_id": "R-CTL-ac034e",
      "status": "PASS|PARTIAL|FAIL",
      "severity": "Severe|High|Medium|Low",
      "confidence": 0.85,
      "evidence": [
        {
          "signal": "short signal name",
          "file": "filename.py",
          "start_line": 10,
          "end_line": 15,
          "snippet": "exact code excerpt",
          "explanation": "why this is evidence"
        }
      ],
      "gap": "what is missing (empty string if PASS)",
      "remediation": "engineering action to address gap (empty string if PASS)"
    }
  ]
}
""".strip()

NOTE_EXACT_IDS = (
    "CRITICAL: The 'control_id' in each finding MUST exactly match one of the IDs "
    "listed under CONTROLS TO EVALUATE above (e.g. R-CTL-ac034e, R-DQ-xxxxxx). "
    "Do NOT invent new IDs. Emit findings in the SAME ORDER as the controls list. "
    "Every control in the list must have exactly one finding."
)

# ---------------------------------------------------------------------------
# Synthesis call template (exec summary + lineage + remediation, one call)
# ---------------------------------------------------------------------------
_SYNTHESIS_TEMPLATE = r"""
{
  "code_lineage": [
    {
      "source": "module:function",
      "target": "module:function",
      "description": "brief relationship description"
    }
  ],
  "data_lineage": {
    "nodes": [
      { "id": "src1",  "label": "<actual DB table or file name from the code>",        "type": "source",    "details": "<one-line description of what this source contains>" },
      { "id": "src2",  "label": "<second DB table or input file from the code>",        "type": "source",    "details": "<one-line description>" },
      { "id": "t1",    "label": "<actual function/class name from the code>",           "type": "transform", "details": "<what this function does to the data>" },
      { "id": "t2",    "label": "<second actual function/service from the code>",       "type": "transform", "details": "<what this function does to the data>" },
      { "id": "out1",  "label": "<actual report, API response, or log output>",         "type": "target",    "details": "<one-line description of the output>" },
      { "id": "out2",  "label": "<second output: audit log, file, or API endpoint>",    "type": "target",    "details": "<one-line description of the output>" }
    ],
    "edges": [
      { "from": "src1", "to": "t1",   "label": "reads" },
      { "from": "src2", "to": "t1",   "label": "joins" },
      { "from": "t1",   "to": "t2",   "label": "feeds" },
      { "from": "t2",   "to": "out1", "label": "produces" },
      { "from": "t2",   "to": "out2", "label": "writes" }
    ]
  }
}
""".strip()


_FDIC370_GRAPH = None


def _get_fdic370_graph():
    """Build and cache the LangGraph for FDIC 370 analysis."""
    global _FDIC370_GRAPH
    if _FDIC370_GRAPH is not None:
        return _FDIC370_GRAPH

    g = StateGraph(AgentState)

    def _node_retrieve(state: AgentState) -> AgentState:
        chunks = retrieve_regulation_chunks(
            "FDIC 12 CFR Part 370 recordkeeping insurance determination ownership category", k=10
        )
        state["regulation_context"] = chunks
        return state

    def _node_fdic370(state: AgentState) -> AgentState:
        llm_inst = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            temperature=0,
            max_tokens=12000,
            api_key=settings.OPENAI_API_KEY,
        )

        code_block = state.get("source_code", "")
        reg_block = "\n\n".join(
            f"[REG-{i+1}] {c}" for i, c in enumerate(state.get("regulation_context", []))
        )
        ctrl_lib = _build_control_library_text()

        prompt = (
            "You are a senior banking regulatory compliance analyst specializing in FDIC 12 CFR Part 370.\n\n"
            "Your mission: analyze the provided codebase against the FDIC 370 control library below and "
            "return a COMPLETE, EVIDENCE-BACKED compliance report.\n\n"
            "OPERATING PRINCIPLES:\n"
            "- Evidence-first: ALWAYS emit at least one evidence item per finding regardless of status.\n"
            "- PASS/PARTIAL: quote the actual file, exact line range, and code snippet that demonstrates the control.\n"
            "- FAIL: still emit one evidence item with file='(not in codebase)', snippet='(absent)', "
            "explanation='<specific description of what mechanism is absent and where it would be expected>'.\n"
            "- Use FDIC terminology: recordkeeping, ownership category, right and capacity, insurance determination, "
            "reconciliation, certification, SMDIA, timely determination.\n"
            "- Focus exclusively on FDIC 370 / Part 330 compliance analysis.\n"
            "- No legal advice — provide engineering compliance analysis only.\n\n"
            "SCORING RULES:\n"
            "- PASS: clear, implemented, correct evidence present.\n"
            "- PARTIAL: control partially implemented or has significant gaps.\n"
            "- FAIL: no evidence found, or implementation is fundamentally wrong.\n"
            "- Missing insurance aggregation → Severe severity.\n"
            "- Missing ownership capacity logic → Severe severity.\n"
            "- No audit trail → High severity.\n"
            "- No reconciliation → High severity.\n"
            "- Partial logging → Medium severity.\n"
            "- Minor config gaps → Low severity.\n\n"
            "You MUST emit a finding for EVERY control in the library below.\n\n"
            "=== FDIC 370 CONTROL LIBRARY ===\n"
            f"{ctrl_lib}\n"
            "=== END CONTROL LIBRARY ===\n\n"
            "=== REGULATION CONTEXT ===\n"
            f"{reg_block}\n"
            "=== END REGULATION CONTEXT ===\n\n"
            "=== CODEBASE ===\n"
            f"{code_block[:14000]}\n"
            "=== END CODEBASE ===\n\n"
            "Return ONLY valid JSON matching this exact template. No markdown fences, no extra text.\n\n"
            f"{FDIC370_JSON_TEMPLATE}"
        )

        resp = llm_inst.invoke([{"role": "user", "content": prompt}])
        raw = getattr(resp, "content", str(resp))

        try:
            data = json.loads(raw)
        except Exception:
            # Attempt to extract JSON from response
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group())
                except Exception:
                    data = {}
            else:
                data = {}

        state["fdic370_raw"] = data
        return state

    g.add_node("retrieve_regulations", _node_retrieve)
    g.add_node("fdic370_analyst", _node_fdic370)
    g.set_entry_point("retrieve_regulations")
    g.add_edge("retrieve_regulations", "fdic370_analyst")
    g.add_edge("fdic370_analyst", END)

    _FDIC370_GRAPH = g.compile()
    return _FDIC370_GRAPH


def _parse_fdic370_findings(raw: dict, batch_controls: list = None) -> List[FDICControlFinding]:
    """Parse LLM findings, falling back to positional matching when IDs are wrong."""
    findings = []
    raw_findings = raw.get("control_findings", [])

    # Build a lookup so positional fallback can resolve by index
    _ctrl_by_id = {c[0]: c for c in FDIC_370_CONTROLS}

    for i, item in enumerate(raw_findings):
        ctrl_id = item.get("control_id", "UNKNOWN")

        # Try exact match first
        ctrl = _ctrl_by_id.get(ctrl_id)

        # Positional fallback: if ID doesn't match any known control but a batch
        # was supplied (same index → same control), use that instead
        if ctrl is None and batch_controls and i < len(batch_controls):
            ctrl = batch_controls[i]
            ctrl_id = ctrl[0]   # fix the id to the real one

        if ctrl is not None:
            section       = ctrl[1]
            title         = ctrl[2]
            intent        = ctrl[3]
            ctl_type      = ctrl[4] if len(ctrl) > 4 else ""
            appl_fields   = list(ctrl[5]) if len(ctrl) > 5 and ctrl[5] else []
        else:
            section, title, intent, ctl_type, appl_fields = "", ctrl_id, "", "", []

        evidence = []
        for ev in item.get("evidence", []):
            if isinstance(ev, str):
                evidence.append(FDICEvidenceItem(
                    signal="", file="", start_line=1, end_line=1,
                    snippet="", explanation=ev,
                ))
            elif isinstance(ev, dict):
                evidence.append(FDICEvidenceItem(
                    signal=ev.get("signal", ""),
                    file=ev.get("file", ""),
                    start_line=int(ev.get("start_line", 1) or 1),
                    end_line=int(ev.get("end_line", ev.get("start_line", 1)) or 1),
                    snippet=ev.get("snippet", ""),
                    explanation=ev.get("explanation", ""),
                ))

        try:
            confidence = float(item.get("confidence", 0.5))
        except (TypeError, ValueError):
            confidence = 0.5
        confidence = max(0.0, min(1.0, confidence))

        findings.append(FDICControlFinding(
            control_id=ctrl_id,
            section=section,
            title=title,
            intent=intent,
            control_type=ctl_type,
            applicable_fields=appl_fields,
            status=item.get("status", "FAIL"),
            severity=item.get("severity", "High"),
            confidence=confidence,
            evidence=evidence,
            gap=item.get("gap", ""),
            remediation=item.get("remediation", ""),
        ))
    return findings


async def analyze_fdic370_agentic(
    file_contents: Dict[str, str],
    languages: List[str],
) -> "FDIC370Analysis":
    """Run the FDIC 370 multi-file compliance analysis.

    Performance design
    ------------------
    - Regulation chunks are loaded once and cached at module level so FAISS
      embeddings are computed only on the first request.
    - The 179 controls are split into batches of _BATCH_SIZE.  Each batch is
      analysed by a separate async LLM call (max_tokens=8000).
    - All batch calls PLUS one synthesis call (exec summary / lineage /
      remediation) run concurrently via asyncio.gather, reducing wall-clock
      time from ~60 s down to ~12–18 s.
    """
    _BATCH_SIZE = 10
    start = time.time()

    # Build concatenated code block with per-file headers
    code_parts: List[str] = []
    total_loc = 0
    for fname, src in file_contents.items():
        total_loc += len(src.splitlines())
        code_parts.append(f"### FILE: {fname} ###\n{src[:4000]}")
    combined_code = "\n\n".join(code_parts)

    # Cached regulation context — FAISS runs only once per process
    reg_chunks = _get_cached_fdic_reg_chunks()
    reg_block = "\n\n".join(f"[REG-{i+1}] {c}" for i, c in enumerate(reg_chunks))

    # Split controls into batches of _BATCH_SIZE
    batches = [
        FDIC_370_CONTROLS[i: i + _BATCH_SIZE]
        for i in range(0, len(FDIC_370_CONTROLS), _BATCH_SIZE)
    ]

    llm = ChatOpenAI(
        model=settings.OPENAI_MODEL,
        temperature=0,
        max_tokens=8000,
        api_key=settings.OPENAI_API_KEY,
    )

    # ── Batch worker ──────────────────────────────────────────────────────────
    async def _analyze_batch(batch: list) -> List[Dict]:
        ctrl_text = "\n".join(
            f"  {c[0]} ({c[1]}): {c[2]} — {c[3]}" for c in batch
        )

        # Build a targeted query from control titles/descriptions in this batch
        # so each batch retrieves the most relevant regulation chunks for its
        # specific controls rather than all batches sharing one static snippet.
        batch_keywords = " ".join(
            f"{c[2]} {c[3][:80]}" for c in batch
        )[:400]
        batch_query = f"FDIC 12 CFR Part 370 {batch_keywords}"
        batch_chunks = retrieve_regulation_chunks(batch_query, k=6)
        batch_reg_block = "\n\n".join(
            f"[REG-{i+1}] {c}" for i, c in enumerate(batch_chunks)
        )

        prompt = (
            "You are a banking regulatory compliance analyst for FDIC 12 CFR Part 370.\n\n"
            "Analyse the codebase against the FOLLOWING CONTROLS ONLY and return findings.\n\n"
            "RULES:\n"
            "- ALWAYS emit at least one evidence item per finding, regardless of status.\n"
            "- PASS/PARTIAL: quote the actual file, exact line range, and code snippet that demonstrates the control.\n"
            "- FAIL: still emit one evidence item with "
            "file='(not in codebase)', snippet='(absent)', "
            "explanation='<describe what mechanism is missing and where it would ordinarily appear>'.\n"
            "- Emit exactly one finding object per control listed below.\n\n"
            f"=== CONTROLS TO EVALUATE ===\n{ctrl_text}\n=== END CONTROLS ===\n\n"
            f"=== REGULATION CONTEXT (retrieved for this control batch) ===\n"
            f"{batch_reg_block}\n=== END REGULATION CONTEXT ===\n\n"
            f"=== CODEBASE ===\n{combined_code[:18000]}\n=== END CODEBASE ===\n\n"
            f"{NOTE_EXACT_IDS}\n\n"
            "Return ONLY valid JSON:\n"
            f"{_FDIC370_BATCH_TEMPLATE}"
        )
        resp = await llm.ainvoke([{"role": "user", "content": prompt}])
        raw = getattr(resp, "content", str(resp))
        try:
            data = json.loads(raw)
        except Exception:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group())
                except Exception:
                    data = {}
            else:
                data = {}
        return data.get("control_findings", []), batch

    # ── Synthesis worker (exec summary + lineage + remediation) ───────────────
    async def _synthesize() -> Dict:
        # Build a balanced per-file code block so ALL files are represented
        # regardless of how many files were submitted.
        per_file_budget = max(2000, 16000 // max(len(file_contents), 1))
        synthesis_parts = []
        for fname, src in file_contents.items():
            synthesis_parts.append(f"### FILE: {fname} ###\n{src[:per_file_budget]}")
        synthesis_code = "\n\n".join(synthesis_parts)

        # Build a cross-file structure map: imports + function/class definitions
        file_list = "\n".join(f"  - {fn}" for fn in file_contents)
        structure_hints = []
        for fname, src in file_contents.items():
            lines = src.splitlines()
            for ln in lines:
                stripped = ln.strip()
                if stripped.startswith(("import ", "from ", "class ", "def ", "async def ")):
                    structure_hints.append(f"    {fname}: {stripped}")
        import_block = "\n".join(structure_hints) if structure_hints else "  (none detected)"

        prompt = (
            "You are a banking regulatory compliance analyst specialising in FDIC 12 CFR Part 370.\n\n"
            f"An automated engine has evaluated {len(FDIC_370_CONTROLS)} FDIC 370 controls "
            f"across {len(file_contents)} file(s) ({total_loc} lines of code).\n\n"
            "FILES ANALYSED:\n"
            f"{file_list}\n\n"
            "CROSS-FILE STRUCTURE MAP (imports, classes, and functions — use to trace real lineage edges):\n"
            f"{import_block}\n\n"
            "MANDATORY OUTPUT RULES — YOU MUST FOLLOW EXACTLY:\n"
            "1. code_lineage: YOU MUST produce ≥5 edges tracing actual cross-file function calls "
            "visible in the import map above (e.g. api_endpoints → business_logic → data_layer). "
            "Each edge MUST have fields: source (string 'module:function'), "
            "target (string 'module:function'), description (plain English relationship). "
            "DO NOT use caller/callee/from_function/to_function — only source/target/description. "
            "Use REAL module and function names from the codebase — do NOT copy placeholder text from the schema.\n"
            "2. data_lineage: produce a graph of named data objects with 'nodes' and 'edges'. "
            "   Each node: { id (unique string), label (table/service/report name), type ('source'|'transform'|'target'), details (one-line description) }. "
            "   Each edge: { from (node id), to (node id), label ('reads'|'writes'|'feeds'|'produces'|'queries'|'joins') }. "
            "   YOU MUST produce ≥2 source nodes (DB tables / files from the code), ≥2 transform nodes (functions / services), ≥2 target nodes (reports / API / logs). "
            "   Use ONLY 'nodes' and 'edges' keys — do NOT use 'sources', 'transformations', or 'outputs'. "
            "   CRITICAL: derive ALL node labels and edge relationships from the ACTUAL codebase above — "
            "   do NOT copy placeholder values from the JSON schema. Every label must be a real name from the code.\n"

            "DO NOT emit placeholder text. Fill every section with real codebase observations.\n\n"
            f"=== REGULATION CONTEXT ===\n{reg_block[:2000]}\n=== END ===\n\n"
            f"=== CODEBASE (all {len(file_contents)} file(s)) ===\n{synthesis_code}\n=== END ===\n\n"
            "Return ONLY valid JSON matching this schema exactly:\n"
            f"{_SYNTHESIS_TEMPLATE}"
        )
        resp = await llm.ainvoke([{"role": "user", "content": prompt}])
        raw = getattr(resp, "content", str(resp))
        try:
            data = json.loads(raw)
        except Exception:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group())
                except Exception:
                    data = {}
            else:
                data = {}
        return data

    # ── Run all batches + synthesis concurrently ──────────────────────────────
    batch_tasks = [_analyze_batch(b) for b in batches]
    all_results = await asyncio.gather(*batch_tasks, _synthesize(), return_exceptions=True)

    # Separate batch results from the final synthesis result
    synthesis: Dict = {}
    findings: List[FDICControlFinding] = []
    seen_ids: set = set()
    for idx, result in enumerate(all_results):
        if isinstance(result, Exception):
            continue
        if idx < len(batches):
            if isinstance(result, tuple):
                raw_findings, batch_ctrls = result
                batch_findings = _parse_fdic370_findings(
                    {"control_findings": raw_findings}, batch_controls=list(batch_ctrls)
                )
                for f in batch_findings:
                    if f.control_id not in seen_ids:
                        findings.append(f)
                        seen_ids.add(f.control_id)
        elif isinstance(result, dict):
            synthesis = result

    # Parse control findings from merged batch results
    # (already done per-batch above with positional fallback)

    # Fill in any controls the LLM missed across all batches
    for ctrl in FDIC_370_CONTROLS:
        if ctrl[0] not in seen_ids:
            ctl_type    = ctrl[4] if len(ctrl) > 4 else ""
            appl_fields = list(ctrl[5]) if len(ctrl) > 5 and ctrl[5] else []
            findings.append(FDICControlFinding(
                control_id=ctrl[0],
                section=ctrl[1],
                title=ctrl[2],
                intent=ctrl[3],
                control_type=ctl_type,
                applicable_fields=appl_fields,
                status="FAIL",
                severity="Medium",
                confidence=0.5,
                evidence=[],
                gap="No direct evidence found — control was not evaluated by the LLM.",
                remediation="Review control requirements and implement evidence of compliance.",
            ))
            seen_ids.add(ctrl[0])

    # Coverage stats
    total = len(findings)
    pass_c = sum(1 for f in findings if f.status == "PASS")
    partial_c = sum(1 for f in findings if f.status == "PARTIAL")
    fail_c = sum(1 for f in findings if f.status == "FAIL")
    compliance_pct = round((pass_c + partial_c * 0.5) / total * 100, 1) if total > 0 else 0.0

    coverage = FDICCoverageStats(
        total_controls=total,
        pass_count=pass_c,
        partial_count=partial_c,
        fail_count=fail_c,
        compliance_pct=compliance_pct,
    )

    # --- Derive executive summary from real findings (no LLM hallucination) ---
    _SEV_ORDER = {"Severe": 0, "High": 1, "Medium": 2, "Low": 3}

    # Overall posture = worst severity among all FAIL findings (fallback: PARTIAL, then all)
    fail_sevs   = [f.severity for f in findings if f.status == "FAIL"]
    partial_sevs = [f.severity for f in findings if f.status == "PARTIAL"]
    candidate_sevs = fail_sevs or partial_sevs or [f.severity for f in findings]
    posture = min(candidate_sevs, key=lambda s: _SEV_ORDER.get(s, 99)) if candidate_sevs else "High"

    # Top critical gaps: gap text from top-severity FAIL findings (skip blanks)
    fail_findings_sorted = sorted(
        [f for f in findings if f.status == "FAIL" and f.gap],
        key=lambda f: (_SEV_ORDER.get(f.severity, 99), f.control_id)
    )
    top_critical_gaps = [
        f"{f.gap} ({f.control_id})"
        for f in fail_findings_sorted[:5]
    ]
    if not top_critical_gaps:
        top_critical_gaps = ["No critical gaps identified — review PARTIAL findings for details."]

    # Immediate priorities: remediation from top Severe/High FAIL findings
    priority_findings = [
        f for f in fail_findings_sorted
        if f.severity in ("Severe", "High") and f.remediation
    ][:5]
    immediate_priorities = [
        f"{f.remediation} ({f.control_id})"
        for f in priority_findings
    ]
    if not immediate_priorities:
        # Fall back to top gaps if no remediation text
        immediate_priorities = [
            f"Address gap in {f.control_id}: {f.title[:80]}"
            for f in fail_findings_sorted[:3]
        ]

    exec_summary = FDICExecutiveSummary(
        posture=posture,
        top_critical_gaps=top_critical_gaps,
        immediate_priorities=immediate_priorities,
    )

    # Code lineage from synthesis
    code_lineage = [
        FDICCodeLineageEdge(
            source=e.get("source", ""),
            target=e.get("target", ""),
            description=e.get("description", ""),
        )
        for e in synthesis.get("code_lineage", [])
    ]

    # Data lineage from synthesis — nodes/edges graph format
    dl_raw = synthesis.get("data_lineage", {})
    dl_nodes = [
        FDICDataLineageNode(id=n.get("id", ""), label=n.get("label", ""),
                            type=n.get("type", ""), details=n.get("details", ""))
        for n in dl_raw.get("nodes", [])
    ]
    dl_edges = [
        FDICDataLineageEdge(**{"from": e.get("from", ""), "to": e.get("to", ""),
                               "label": e.get("label", "")})
        for e in dl_raw.get("edges", [])
    ]
    data_lineage = FDICDataLineage(nodes=dl_nodes, edges=dl_edges)

    # Remediation plan — built deterministically from real findings (no LLM hallucination)
    def _make_phase(phase_findings: list) -> List[FDICRemediationItem]:
        items = []
        for pri, f in enumerate(phase_findings, start=1):
            items.append(FDICRemediationItem(
                priority=pri,
                action=f.remediation or f"Implement compliance for: {f.title[:120]}",
                control_ids=[f.control_id],
                rationale=f.gap or f"Control '{f.title[:80]}' is not satisfied in the current codebase.",
            ))
        return items

    all_fail_sorted = sorted(
        [f for f in findings if f.status in ("FAIL", "PARTIAL")],
        key=lambda f: (_SEV_ORDER.get(f.severity, 99), f.control_id)
    )
    phase1 = [f for f in all_fail_sorted if f.severity == "Severe"]
    phase2 = [f for f in all_fail_sorted if f.severity == "High"]
    phase3 = [f for f in all_fail_sorted if f.severity in ("Medium", "Low")]

    remediation_plan = FDICRemediationPlan(
        phase1_critical=_make_phase(phase1),
        phase2_structural=_make_phase(phase2),
        phase3_governance=_make_phase(phase3),
    )

    duration_ms = int((time.time() - start) * 1000)

    return FDIC370Analysis(
        files_analyzed=len(file_contents),
        total_loc=total_loc,
        languages=list(set(languages)),
        executive_summary=exec_summary,
        coverage_stats=coverage,
        control_findings=findings,
        code_lineage=code_lineage,
        data_lineage=data_lineage,
        remediation_plan=remediation_plan,
        analysis_duration_ms=duration_ms,
    )
