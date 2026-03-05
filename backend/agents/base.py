"""
Shared LLM client and system persona for the FDIC Part 370 analyzer agents.
"""
from __future__ import annotations

import os

from langchain_openai import ChatOpenAI


SYSTEM_PERSONA = (
    "You are a senior FDIC compliance examiner and IT systems auditor "
    "with deep expertise in 12 CFR Part 370 (Large-Bank Deposit Insurance "
    "Determination Modernization), 12 CFR Part 330 (Deposit Insurance Coverage), "
    "12 CFR 360.8, and the FDIC IT Functional Guide v3.0 (June 2023).  "
    "You analyze code, data schemas, and system architectures to identify "
    "compliance gaps against the regulatory requirements.  You cite specific "
    "CFR sections and IT Guide references for every finding.  You are precise, "
    "conservative, and never dismiss a potential gap without explicit regulatory "
    "justification."
)


def get_llm(temperature: float = 0.0) -> ChatOpenAI:
    """
    Return the shared ChatOpenAI instance configured for FDIC analysis.
    Uses GPT-4.1-mini by default (fast, cost-effective for structured output).
    """
    model = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
    return ChatOpenAI(
        model=model,
        temperature=temperature,
        max_tokens=4096,
    )
