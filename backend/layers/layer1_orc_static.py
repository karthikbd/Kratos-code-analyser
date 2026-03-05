"""
Layer 1 -- ORC Assignment Logic Static Analysis
=================================================
Regulatory Source: 12 CFR Part 330 + IT Guide Section 4

This layer performs semantic AST-level analysis of the institution's
ORC assignment code.  Three sub-checks:

1. **ORC Rule Completeness Check** -- every branch of the ORC assignment
   code is mapped against the 11 regulatory ORC types.  Missing branches
   are flagged as compliance gaps.

2. **Default / Fallback Logic Audit** -- 12 CFR Part 330 requires that
   any account failing ORC qualification reverts to SGL with funds
   apportioned evenly among named owners.  The analyzer verifies the
   fallback path exists and is tested.

3. **Pending File Routing Logic** -- accounts with insufficient data
   must be routed to the Pending File with correct reason codes
   (e.g. RAC for JNT awaiting signature card).  The analyzer checks
   exhaustiveness of routing conditions.
"""
from __future__ import annotations

import ast
import re
import textwrap
from typing import Any

from backend.core.models import (
    AnalyzerLayer,
    ComplianceFinding,
    LayerScanResult,
    ORCType,
    ORC_RULES,
    PendingReasonCode,
    Severity,
)


# Expected ORC string literals that must appear in assignment code
_EXPECTED_ORC_LITERALS = {orc.value for orc in ORCType}

# Expected pending reason codes
_EXPECTED_PENDING_CODES = {p.value for p in PendingReasonCode}

# Mapping of ORC -> conditions the code MUST check
_ORC_REQUIRED_CHECKS: dict[str, list[str]] = {
    "JNT": ["natural_person", "signature_card", "withdrawal_rights"],
    "REV": ["beneficiary", "trust_document"],
    "IRR": ["irrevocable", "beneficiary", "interest_allocation"],
    "GOV1": ["government", "federal", "collateral"],
    "GOV2": ["government", "state", "municipal", "collateral", "custodian"],
    "GOV3": ["government", "tribal", "collateral"],
    "EBP": ["employee_benefit", "plan", "participant"],
    "ANC": ["annuity", "contract", "insurance_company"],
    "CRA": ["retirement", "ira", "keogh"],
    "BUS": ["entity_type", "corporation", "llc", "partnership", "tax_id"],
    "SGL": [],  # default -- no special checks required
}

# Pending routing conditions that must be exhaustive
_REQUIRED_PENDING_ROUTES: dict[str, str] = {
    "RAC": "JNT accounts without signature card evidence",
    "BEN": "REV/IRR accounts without beneficiary data",
    "GOV": "GOV accounts without collateral documentation",
    "ORC": "Accounts where ORC cannot be determined",
    "LNK": "Accounts that cannot be linked to a unique depositor ID",
    "MRG": "Merger boundary accounts requiring dual calculation",
}


class Layer1ORCStaticAnalyzer:
    """
    Semantic AST-based analyzer for the institution's ORC assignment code.
    Configured with custom rules from 12 CFR Part 330 definitions.
    """

    def __init__(self) -> None:
        self._findings: list[ComplianceFinding] = []

    def scan(
        self,
        orc_assignment_code: str,
        pending_routing_code: str = "",
    ) -> LayerScanResult:
        """
        Run all three Layer 1 sub-checks.

        Parameters
        ----------
        orc_assignment_code : str
            Source code of the ORC assignment function.
        pending_routing_code : str
            Source code of the pending file routing function.
        """
        self._findings = []

        # Sub-check 1: ORC Rule Completeness
        self._check_orc_completeness(orc_assignment_code)

        # Sub-check 2: Default/Fallback to SGL
        self._check_fallback_logic(orc_assignment_code)

        # Sub-check 3: Pending File Routing
        if pending_routing_code:
            self._check_pending_routing(pending_routing_code)
        else:
            self._findings.append(ComplianceFinding(
                layer=AnalyzerLayer.LAYER1_ORC_STATIC,
                severity=Severity.HIGH,
                title="Pending file routing code not provided for analysis",
                description=(
                    "The institution did not provide the pending file routing "
                    "logic for static analysis.  Per 12 CFR 370.3(b), accounts "
                    "with insufficient data must be routed to the Pending File."
                ),
                cfr_reference="12 CFR 370.3(b)",
                it_guide_reference="IT Guide Section 5.3",
            ))

        passed = all(f.severity not in (Severity.CRITICAL, Severity.HIGH) for f in self._findings)

        return LayerScanResult(
            layer=AnalyzerLayer.LAYER1_ORC_STATIC,
            findings=self._findings,
            passed=passed,
            metrics={
                "orc_types_found": self._count_orc_literals(orc_assignment_code),
                "orc_types_missing": list(
                    _EXPECTED_ORC_LITERALS - self._extract_string_literals(orc_assignment_code)
                ),
                "total_findings": len(self._findings),
            },
            summary=f"Layer 1: {len(self._findings)} findings ({sum(1 for f in self._findings if f.severity == Severity.CRITICAL)} critical)",
        )

    # ------------------------------------------------------------------
    # Sub-check 1: ORC Rule Completeness
    # ------------------------------------------------------------------

    def _check_orc_completeness(self, code: str) -> None:
        """Verify all 11 ORC types have assignment branches."""
        literals = self._extract_string_literals(code)
        code_lower = code.lower()

        for orc in ORCType:
            if orc.value not in literals:
                rule = ORC_RULES.get(orc)
                self._findings.append(ComplianceFinding(
                    layer=AnalyzerLayer.LAYER1_ORC_STATIC,
                    severity=Severity.CRITICAL,
                    title=f"Missing ORC assignment branch: {orc.value} ({orc.name})",
                    description=(
                        f"The ORC assignment code does not contain a branch for "
                        f"{orc.value} ({rule.description if rule else orc.name}).  "
                        f"Per 12 CFR {rule.cfr_section if rule else 'Part 330'}, "
                        f"every deposit must be classifiable into one of 11 ORC types."
                    ),
                    cfr_reference=f"12 CFR {rule.cfr_section}" if rule else "12 CFR Part 330",
                    it_guide_reference="IT Guide Section 4",
                    orc_type=orc,
                    expected_behavior=f"Code branch returning '{orc.value}' with qualification checks",
                    observed_behavior="No branch found for this ORC type",
                    remediation_recommendation=f"Add ORC assignment logic for {orc.value} per {rule.cfr_section if rule else 'Part 330'}",
                ))

            # Check ORC-specific qualification conditions
            required_checks = _ORC_REQUIRED_CHECKS.get(orc.value, [])
            for check_keyword in required_checks:
                if check_keyword.lower() not in code_lower:
                    self._findings.append(ComplianceFinding(
                        layer=AnalyzerLayer.LAYER1_ORC_STATIC,
                        severity=Severity.HIGH,
                        title=f"Missing qualification check for {orc.value}: '{check_keyword}'",
                        description=(
                            f"The ORC assignment code for {orc.value} does not appear to "
                            f"check the '{check_keyword}' condition.  Per 12 CFR "
                            f"{ORC_RULES[orc].cfr_section}, this is a required "
                            f"qualification criterion."
                        ),
                        cfr_reference=f"12 CFR {ORC_RULES[orc].cfr_section}",
                        it_guide_reference="IT Guide Section 4",
                        orc_type=orc,
                        expected_behavior=f"Code checks '{check_keyword}' before assigning {orc.value}",
                        observed_behavior=f"Keyword '{check_keyword}' not found in code",
                    ))

    # ------------------------------------------------------------------
    # Sub-check 2: Default/Fallback Logic Audit
    # ------------------------------------------------------------------

    def _check_fallback_logic(self, code: str) -> None:
        """Verify SGL fallback path exists and handles fund apportioning."""
        code_lower = code.lower()

        # Check for explicit SGL return as default
        has_sgl_default = bool(
            re.search(r'return\s+["\']SGL["\']', code)
            or re.search(r'default.*sgl|fallback.*sgl|else.*sgl', code_lower)
        )

        if not has_sgl_default:
            self._findings.append(ComplianceFinding(
                layer=AnalyzerLayer.LAYER1_ORC_STATIC,
                severity=Severity.CRITICAL,
                title="Missing SGL default/fallback logic",
                description=(
                    "The ORC assignment code does not have an explicit fallback "
                    "path to SGL.  Per 12 CFR Part 330, any account failing to "
                    "qualify for its designated ORC must revert to SGL with funds "
                    "apportioned evenly among named owners."
                ),
                cfr_reference="12 CFR Part 330",
                it_guide_reference="IT Guide Section 4.1",
                expected_behavior="Explicit default return of 'SGL' when no ORC qualifies",
                observed_behavior="No SGL fallback detected",
            ))

        # Check for fund apportioning in fallback
        apportion_keywords = ["apportion", "split", "divide", "equal_share", "per_owner"]
        has_apportion = any(kw in code_lower for kw in apportion_keywords)
        if not has_apportion:
            self._findings.append(ComplianceFinding(
                layer=AnalyzerLayer.LAYER1_ORC_STATIC,
                severity=Severity.HIGH,
                title="SGL fallback does not apportion funds among owners",
                description=(
                    "When an account reverts to SGL from a multi-owner ORC, "
                    "funds must be apportioned evenly among named owners.  "
                    "The code does not appear to implement fund apportioning."
                ),
                cfr_reference="12 CFR Part 330",
                expected_behavior="Fund apportioning logic (equal split among owners)",
                observed_behavior="No apportioning keywords found",
            ))

        # Check that fallback is unit-tested
        test_keywords = ["test_fallback", "test_sgl_default", "test_default_orc"]
        if not any(kw in code_lower for kw in test_keywords):
            self._findings.append(ComplianceFinding(
                layer=AnalyzerLayer.LAYER1_ORC_STATIC,
                severity=Severity.MEDIUM,
                title="SGL fallback logic does not appear to be unit-tested",
                description=(
                    "No evidence of unit tests for the SGL fallback path.  "
                    "The FDIC Compliance Review Manual requires that fallback "
                    "logic is explicitly tested."
                ),
                cfr_reference="12 CFR Part 330",
                it_guide_reference="Compliance Review Manual Section 10",
            ))

    # ------------------------------------------------------------------
    # Sub-check 3: Pending File Routing Logic
    # ------------------------------------------------------------------

    def _check_pending_routing(self, code: str) -> None:
        """Verify exhaustive pending file routing with correct reason codes."""
        code_lower = code.lower()
        literals = self._extract_string_literals(code)

        for reason_code, condition_desc in _REQUIRED_PENDING_ROUTES.items():
            if reason_code not in literals:
                self._findings.append(ComplianceFinding(
                    layer=AnalyzerLayer.LAYER1_ORC_STATIC,
                    severity=Severity.HIGH,
                    title=f"Missing pending reason code: {reason_code}",
                    description=(
                        f"The pending file routing code does not handle "
                        f"reason code '{reason_code}' ({condition_desc}).  "
                        f"Per 12 CFR 370.3(b), no account may be silently dropped."
                    ),
                    cfr_reference="12 CFR 370.3(b)",
                    it_guide_reference="IT Guide Section 5.3",
                    expected_behavior=f"Route to Pending File with reason '{reason_code}' for {condition_desc}",
                    observed_behavior=f"Reason code '{reason_code}' not found in routing logic",
                ))

        # Check for silent drop (account goes nowhere)
        if "drop" in code_lower or "skip" in code_lower or "ignore" in code_lower:
            self._findings.append(ComplianceFinding(
                layer=AnalyzerLayer.LAYER1_ORC_STATIC,
                severity=Severity.CRITICAL,
                title="Potential silent account drop in pending routing",
                description=(
                    "The pending routing code contains keywords suggesting "
                    "accounts may be dropped or skipped.  Per 12 CFR 370.3(b), "
                    "every account must either be calculated or routed to pending."
                ),
                cfr_reference="12 CFR 370.3(b)",
            ))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _extract_string_literals(self, code: str) -> set[str]:
        """Extract all string literals from Python source code."""
        literals: set[str] = set()
        try:
            tree = ast.parse(textwrap.dedent(code))
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    literals.add(node.value)
        except SyntaxError:
            # Fallback: regex extraction
            for match in re.finditer(r'["\']([A-Z0-9_]+)["\']', code):
                literals.add(match.group(1))
        return literals

    def _count_orc_literals(self, code: str) -> int:
        """Count how many of the 11 ORC type literals appear."""
        literals = self._extract_string_literals(code)
        return len(_EXPECTED_ORC_LITERALS & literals)
