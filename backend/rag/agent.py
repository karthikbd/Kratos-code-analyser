"""
RAG-Enhanced Agent -- Queries regulatory knowledge base before analysis.

Each analyzer layer can call this to get grounded regulatory context
and GPT-enhanced findings with specific CFR citations.
"""
from __future__ import annotations

from typing import Any

from backend.agents.base import get_llm, SYSTEM_PERSONA
from backend.rag import get_knowledge_base


def get_regulatory_guidance(topic: str) -> str:
    """
    Query the RAG knowledge base for regulatory text relevant to a topic.
    Returns formatted regulatory context string.
    """
    kb = get_knowledge_base()
    if not kb.is_ready:
        try:
            kb.build_index()
        except Exception:
            pass
    return kb.get_regulatory_context(topic)


def enhance_finding_with_rag(
    finding_description: str,
    layer_name: str,
    severity: str = "HIGH",
) -> dict[str, str]:
    """
    Enhance a compliance finding with RAG-grounded regulatory citations
    and GPT-generated remediation advice.

    Returns dict with 'regulation_reference' and 'remediation' keys.
    """
    # Get relevant regulatory context
    context = get_regulatory_guidance(finding_description)

    if not context:
        return {
            "regulation_reference": "",
            "remediation": "",
        }

    try:
        llm = get_llm(temperature=0.0)
        response = llm.invoke([
            {"role": "system", "content": SYSTEM_PERSONA},
            {"role": "user", "content": (
                f"Layer: {layer_name}\n"
                f"Severity: {severity}\n"
                f"Finding: {finding_description}\n\n"
                f"Regulatory Context from FDIC documents:\n{context}\n\n"
                f"Based on the regulatory context above, provide:\n"
                f"1. The exact regulation reference (e.g., '12 CFR 370.3(a)(1)' or 'IT Guide Section 2.3.2')\n"
                f"2. A specific remediation recommendation (2-3 sentences)\n\n"
                f"Format your response as:\n"
                f"REFERENCE: <citation>\n"
                f"REMEDIATION: <recommendation>"
            )},
        ])

        text = response.content
        ref = ""
        rem = ""
        for line in text.split("\n"):
            if line.strip().startswith("REFERENCE:"):
                ref = line.split("REFERENCE:", 1)[1].strip()
            elif line.strip().startswith("REMEDIATION:"):
                rem = line.split("REMEDIATION:", 1)[1].strip()

        return {
            "regulation_reference": ref,
            "remediation": rem,
        }
    except Exception:
        return {
            "regulation_reference": "",
            "remediation": "",
        }


def batch_enhance_findings(
    findings: list[dict[str, Any]],
    layer_name: str,
) -> list[dict[str, Any]]:
    """
    Enhance multiple findings with RAG context.
    Only enhances CRITICAL and HIGH findings to save API calls.
    """
    enhanced = []
    for f in findings:
        if f.get("severity") in ("CRITICAL", "HIGH"):
            enrichment = enhance_finding_with_rag(
                f.get("description", ""),
                layer_name,
                f.get("severity", "HIGH"),
            )
            f["regulation_reference"] = (
                enrichment["regulation_reference"]
                or f.get("regulation_reference", "")
            )
            f["remediation"] = enrichment.get("remediation", "")
        enhanced.append(f)
    return enhanced
