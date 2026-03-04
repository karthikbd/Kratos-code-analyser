"""json_controls.py
Loads the enriched FDIC Part 370 IT controls JSON (179 requirements) and
provides keyword-based search and coverage computation utilities.

The JSON is loaded once at import time from:
  regulations/fdic_370_controls.json
(resolved relative to this file: ../../regulations/fdic_370_controls.json)
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Load controls once at import time
# ---------------------------------------------------------------------------
_CONTROLS_PATH = Path(__file__).resolve().parents[2] / "regulations" / "fdic_370_controls.json"

_CONTROLS: List[Dict[str, Any]] = []


def _load_controls() -> List[Dict[str, Any]]:
    """Load requirements from the enriched FDIC 370 controls JSON file."""
    global _CONTROLS  # pylint: disable=global-statement
    if _CONTROLS:
        return _CONTROLS
    if not _CONTROLS_PATH.exists():
        log.warning("FDIC 370 controls JSON not found at %s", _CONTROLS_PATH)
        return []
    with open(_CONTROLS_PATH, encoding="utf-8") as fh:
        data = json.load(fh)
    _CONTROLS = data.get("requirements", [])
    log.info("Loaded %d FDIC 370 controls from %s", len(_CONTROLS), _CONTROLS_PATH.name)
    return _CONTROLS


# Eagerly load on import so callers never need to call _load_controls() themselves.
_load_controls()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _tokenise(text: str) -> List[str]:
    """Lower-case, split on non-alphanumeric, drop short tokens."""
    return [t for t in re.split(r"[^a-z0-9]+", text.lower()) if len(t) > 2]


def _control_text(ctrl: Dict[str, Any]) -> str:
    """Concatenate all searchable text fields of a control record."""
    parts: List[str] = [
        ctrl.get("rule_description", ""),
        ctrl.get("control_objective", ""),
        ctrl.get("rule_type", ""),
        ctrl.get("control_type", ""),
        ctrl.get("automation_level", ""),
        ctrl.get("data_source", ""),
        " ".join(ctrl.get("applicable_fields", []) or []),
        " ".join(ctrl.get("system_mapping", []) or []),
        " ".join(ctrl.get("risk_addressed", []) or []),
        " ".join(ctrl.get("evidence_type", []) or []),
    ]
    return " ".join(filter(None, parts))


def _score(query_tokens: List[str], ctrl: Dict[str, Any]) -> float:
    """
    Simple token-overlap relevance score.
    Weights: rule_description (×3), control_objective (×2), others (×1).
    Also adds a small confidence bonus so higher-quality controls rank slightly higher.
    """
    desc_tokens  = set(_tokenise(ctrl.get("rule_description", "")))
    obj_tokens   = set(_tokenise(ctrl.get("control_objective", "")))
    other_tokens = set(_tokenise(_control_text(ctrl))) - desc_tokens - obj_tokens

    q = set(query_tokens)
    score = (
        len(q & desc_tokens)  * 3.0
        + len(q & obj_tokens) * 2.0
        + len(q & other_tokens) * 1.0
    )
    # Normalise by query length to avoid bias toward long queries
    if query_tokens:
        score /= len(query_tokens)
    # Tiny confidence tiebreaker (0–0.1 range)
    score += ctrl.get("confidence", 0.0) * 0.1
    return score


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def search_controls(query: str, top_k: int = 10) -> List[Dict[str, Any]]:
    """
    Return the *top_k* most relevant FDIC 370 control requirements for *query*.

    Each returned dict is the raw requirement record from the JSON, augmented
    with a ``_relevance_score`` key (float).

    Parameters
    ----------
    query   : Free-text query (typically function names + filename).
    top_k   : Maximum number of results to return.

    Returns
    -------
    List of control dicts sorted by relevance (highest first).
    """
    controls = _load_controls()
    if not controls:
        return []
    if not query or not query.strip():
        return controls[:top_k]

    q_tokens = _tokenise(query)
    scored = [
        {**ctrl, "_relevance_score": _score(q_tokens, ctrl)}
        for ctrl in controls
    ]
    scored.sort(key=lambda c: c["_relevance_score"], reverse=True)
    return scored[:top_k]


def compute_coverage(findings: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compute coverage statistics against the loaded 179 FDIC 370 controls.

    Parameters
    ----------
    findings : Deduplicated list of finding dicts (each may have ``control_id``,
               ``regulation``, ``severity``).

    Returns
    -------
    Dict with keys:
        total_controls      – total requirements in the JSON (179)
        controls_covered    – number of unique control_ids referenced in findings
        coverage_pct        – controls_covered / total_controls × 100
        total_findings      – len(findings)
        by_rule_type        – dict of rule_type → count across *all* loaded controls
        by_severity         – dict of severity → count across findings
        by_automation       – dict of automation_level → count across loaded controls
    """
    controls = _load_controls()
    total = len(controls)

    # Count which control IDs from findings match a loaded requirement_id
    loaded_ids = {c.get("requirement_id", "") for c in controls}
    hit_ids = {
        f.get("control_id", "")
        for f in findings
        if f.get("control_id", "") in loaded_ids
    }

    # Rule-type distribution across the full control library
    by_rule_type: Dict[str, int] = {}
    by_automation: Dict[str, int] = {}
    for ctrl in controls:
        rt = ctrl.get("rule_type", "unknown")
        al = ctrl.get("automation_level", "unknown")
        by_rule_type[rt] = by_rule_type.get(rt, 0) + 1
        by_automation[al] = by_automation.get(al, 0) + 1

    # Severity distribution across findings
    by_severity: Dict[str, int] = {}
    for finding in findings:
        sev = finding.get("severity", "info")
        by_severity[sev] = by_severity.get(sev, 0) + 1

    covered = len(hit_ids)
    coverage_pct = round(covered / total * 100, 1) if total else 0.0

    return {
        "total_controls":   total,
        "controls_covered": covered,
        "coverage_pct":     coverage_pct,
        "total_findings":   len(findings),
        "by_rule_type":     by_rule_type,
        "by_severity":      by_severity,
        "by_automation":    by_automation,
    }
