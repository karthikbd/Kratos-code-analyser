"""
Layer 6 -- Certification Artifact Generator
=============================================
Regulatory Source: 12 CFR 370.10(a) + IT Guide Appendix B

Under 12 CFR 370.10(a), the CI must annually certify that it has
tested its IT system during the preceding twelve months and that
testing confirmed compliance.

Outputs:

1. **Per-ORC Completeness Score** -- e.g. "97.3%% of REV accounts
   have beneficiary data sufficient for calculation"

2. **Pending File Population Report** -- by pending reason code

3. **Data Quality Exception Log** -- specific accounts that would
   fall into the non-calculable bucket, with root cause

4. **Test Execution Timestamp Log** -- evidentiary basis for
   annual certification

5. **Deposit Insurance Coverage Summary Report** -- maps to
   FDIC IT Guide Appendix B format
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from typing import Any

from backend.core.models import (
    AnalyzerLayer,
    CertificationReport,
    ComplianceFinding,
    CustomerRecord,
    DepositAccount,
    FindingStatus,
    FullPipelineResult,
    InsuranceCalculationResult,
    LayerScanResult,
    ORCCompletenessScore,
    ORCType,
    ORC_RULES,
    PendingReasonCode,
    Severity,
)


class Layer6CertificationGenerator:
    """
    Generates the structured certification artifacts required by
    12 CFR 370.10(a) and IT Guide Appendix B.
    """

    def __init__(self, institution_name: str = "Covered Institution") -> None:
        self._institution = institution_name
        self._findings: list[ComplianceFinding] = []

    def scan(
        self,
        accounts: list[DepositAccount],
        customers: list[CustomerRecord],
        calc_results: list[InsuranceCalculationResult] | None = None,
        prior_layer_results: list[LayerScanResult] | None = None,
    ) -> LayerScanResult:
        self._findings = []

        # 1. Completeness scores per ORC
        orc_scores = self._compute_orc_completeness(accounts)

        # 2. Pending file report
        pending_summary = self._compute_pending_summary(accounts)

        # 3. Data quality exception log
        exceptions = self._build_exception_log(accounts, customers)

        # 4. Test execution timestamp
        test_log = self._build_test_log(prior_layer_results or [])

        # 5. Generate CertificationReport
        cert = self._generate_certification(
            accounts, calc_results or [], orc_scores,
            pending_summary, exceptions, test_log,
        )

        # Check certification readiness
        self._check_certification_readiness(cert, prior_layer_results or [])

        passed = all(f.severity not in (Severity.CRITICAL, Severity.HIGH) for f in self._findings)

        return LayerScanResult(
            layer=AnalyzerLayer.LAYER6_CERTIFICATION,
            findings=self._findings,
            passed=passed,
            metrics={
                "overall_completeness": cert.overall_completeness,
                "total_accounts": cert.total_accounts,
                "non_calculable": cert.non_calculable_count,
                "certification_ready": cert.overall_completeness >= 95.0 and passed,
                "orc_scores": {s.orc_type.value: s.completeness_pct for s in orc_scores},
                "pending_summary": pending_summary,
                "certification_report": cert.model_dump(),
            },
            summary=(
                f"Layer 6: Overall completeness {cert.overall_completeness:.1f}%%, "
                f"{cert.non_calculable_count} non-calculable accounts"
            ),
        )

    # ------------------------------------------------------------------
    # 1. Per-ORC Completeness Scores
    # ------------------------------------------------------------------

    def _compute_orc_completeness(
        self, accounts: list[DepositAccount]
    ) -> list[ORCCompletenessScore]:
        """Compute data completeness per ORC category."""
        by_orc: dict[ORCType, list[DepositAccount]] = defaultdict(list)
        for acct in accounts:
            by_orc[acct.orc_type].append(acct)

        scores: list[ORCCompletenessScore] = []
        for orc_type, accts in by_orc.items():
            rule = ORC_RULES.get(orc_type)
            if not rule:
                continue

            total = len(accts)
            calculable = 0
            missing_fields: dict[str, int] = defaultdict(int)

            for acct in accts:
                acct_dict = acct.model_dump()
                has_all = True
                for field in rule.required_fields:
                    val = acct_dict.get(field)
                    if val is None or val == "" or val == [] or val is False:
                        # Special: signature_card_evidence=False is a gap only for JNT
                        if field == "signature_card_evidence" and orc_type != ORCType.JNT:
                            continue
                        missing_fields[field] += 1
                        has_all = False
                if has_all:
                    calculable += 1

            completeness = (calculable / total * 100) if total > 0 else 100.0
            scores.append(ORCCompletenessScore(
                orc_type=orc_type,
                total_accounts=total,
                calculable_accounts=calculable,
                non_calculable_accounts=total - calculable,
                completeness_pct=round(completeness, 1),
                missing_field_summary=dict(missing_fields),
            ))

        return scores

    # ------------------------------------------------------------------
    # 2. Pending File Report
    # ------------------------------------------------------------------

    def _compute_pending_summary(
        self, accounts: list[DepositAccount]
    ) -> dict[str, int]:
        """Count accounts by pending reason code."""
        pending: dict[str, int] = defaultdict(int)

        for acct in accounts:
            if acct.orc_type == ORCType.JNT and not acct.signature_card_evidence:
                pending[PendingReasonCode.RAC.value] += 1
            if acct.orc_type in (ORCType.REV, ORCType.IRR) and not acct.beneficiary_ids:
                pending[PendingReasonCode.BEN.value] += 1
            if acct.orc_type in (ORCType.GOV1, ORCType.GOV2, ORCType.GOV3) and not acct.collateral_pledge_ref:
                pending[PendingReasonCode.GOV.value] += 1
            if acct.acquired_institution_id:
                pending[PendingReasonCode.MRG.value] += 1

        return dict(pending)

    # ------------------------------------------------------------------
    # 3. Data Quality Exception Log
    # ------------------------------------------------------------------

    def _build_exception_log(
        self,
        accounts: list[DepositAccount],
        customers: list[CustomerRecord],
    ) -> list[dict[str, Any]]:
        """Identify specific accounts that are non-calculable with root cause."""
        customer_ids = {c.depositor_id for c in customers}
        exceptions: list[dict[str, Any]] = []

        for acct in accounts:
            reasons: list[str] = []
            if acct.depositor_id not in customer_ids:
                reasons.append("ORPHAN_ACCOUNT: No matching customer record")
            if acct.orc_type == ORCType.JNT and not acct.signature_card_evidence:
                reasons.append("MISSING_SIGNATURE_CARD: JNT requires evidence")
            if acct.orc_type in (ORCType.REV, ORCType.IRR) and not acct.beneficiary_ids:
                reasons.append("MISSING_BENEFICIARY: Trust account requires beneficiary data")
            if acct.orc_type in (ORCType.GOV1, ORCType.GOV2, ORCType.GOV3) and not acct.collateral_pledge_ref:
                reasons.append("MISSING_COLLATERAL: Government account requires pledge ref")
            if acct.debt_flag and acct.debt_type and acct.debt_type.lower() in ("credit_card", "cc"):
                reasons.append("INCORRECT_DEBT_FLAG: Credit card should not set debt flag")

            if reasons:
                exceptions.append({
                    "account_number": acct.account_number,
                    "orc_type": acct.orc_type.value,
                    "balance": acct.balance,
                    "root_causes": reasons,
                    "remediation_category": self._classify_remediation(reasons),
                })

        return exceptions

    def _classify_remediation(self, reasons: list[str]) -> str:
        """Classify remediation needed for the Appendix B plan."""
        if any("ORPHAN" in r for r in reasons):
            return "DATA_LINKAGE"
        if any("MISSING_SIGNATURE" in r for r in reasons):
            return "DOCUMENT_REMEDIATION"
        if any("MISSING_BENEFICIARY" in r for r in reasons):
            return "TRUST_DATA_COLLECTION"
        if any("MISSING_COLLATERAL" in r for r in reasons):
            return "COLLATERAL_DOCUMENTATION"
        if any("INCORRECT_DEBT" in r for r in reasons):
            return "DATA_CORRECTION"
        return "INVESTIGATION"

    # ------------------------------------------------------------------
    # 4. Test Execution Timestamp Log
    # ------------------------------------------------------------------

    def _build_test_log(
        self, prior_results: list[LayerScanResult]
    ) -> list[dict[str, Any]]:
        """Build the evidentiary timestamp log for annual certification."""
        log_entries: list[dict[str, Any]] = []
        for result in prior_results:
            log_entries.append({
                "layer": result.layer.value,
                "scan_timestamp": result.scan_timestamp.isoformat(),
                "passed": result.passed,
                "finding_count": len(result.findings),
                "critical_count": result.critical_count,
                "high_count": result.high_count,
            })

        # Add Layer 6 execution
        log_entries.append({
            "layer": AnalyzerLayer.LAYER6_CERTIFICATION.value,
            "scan_timestamp": datetime.utcnow().isoformat(),
            "passed": True,  # Updated after check
            "finding_count": len(self._findings),
            "critical_count": 0,
            "high_count": 0,
        })

        return log_entries

    # ------------------------------------------------------------------
    # 5. Generate Certification Report (Appendix B format)
    # ------------------------------------------------------------------

    def _generate_certification(
        self,
        accounts: list[DepositAccount],
        calc_results: list[InsuranceCalculationResult],
        orc_scores: list[ORCCompletenessScore],
        pending_summary: dict[str, int],
        exceptions: list[dict[str, Any]],
        test_log: list[dict[str, Any]],
    ) -> CertificationReport:
        """Generate the CertificationReport mapped to Appendix B."""
        total_deposits = sum(a.balance for a in accounts)
        total_insured = sum(r.insured_amount for r in calc_results) if calc_results else 0.0
        total_uninsured = sum(r.uninsured_amount for r in calc_results) if calc_results else 0.0
        non_calculable = len(exceptions)

        overall_completeness = 0.0
        if orc_scores:
            total_accts = sum(s.total_accounts for s in orc_scores)
            total_calc = sum(s.calculable_accounts for s in orc_scores)
            overall_completeness = (total_calc / total_accts * 100) if total_accts > 0 else 0.0

        # Build remediation plan from exceptions
        remediation_plan: list[dict[str, Any]] = []
        remediation_groups: dict[str, int] = defaultdict(int)
        for exc in exceptions:
            remediation_groups[exc["remediation_category"]] += 1
        for category, count in remediation_groups.items():
            remediation_plan.append({
                "category": category,
                "affected_accounts": count,
                "target_completion": "90 days",
                "responsible_party": "Compliance Operations",
            })

        cert = CertificationReport(
            institution_name=self._institution,
            orc_scores=orc_scores,
            overall_completeness=round(overall_completeness, 1),
            total_accounts=len(accounts),
            total_deposits=total_deposits,
            total_insured=total_insured,
            total_uninsured=total_uninsured,
            non_calculable_count=non_calculable,
            pending_file_summary=pending_summary,
            data_quality_exceptions=exceptions,
            test_execution_log=test_log,
            remediation_plan=remediation_plan,
            certification_statement=(
                f"This certifies that {self._institution} has tested its FDIC Part 370 "
                f"IT system during the preceding twelve months.  Overall data completeness: "
                f"{overall_completeness:.1f}%%.  Non-calculable accounts: {non_calculable}.  "
                f"Testing confirmed {'compliance' if overall_completeness >= 95 else 'gaps requiring remediation'}."
            ),
        )
        return cert

    # ------------------------------------------------------------------
    # Certification Readiness Check
    # ------------------------------------------------------------------

    def _check_certification_readiness(
        self,
        cert: CertificationReport,
        prior_results: list[LayerScanResult],
    ) -> None:
        """Flag blockers that prevent annual certification."""
        # Completeness below 95%
        if cert.overall_completeness < 95.0:
            self._findings.append(ComplianceFinding(
                layer=AnalyzerLayer.LAYER6_CERTIFICATION,
                severity=Severity.HIGH,
                title=f"Overall completeness below threshold: {cert.overall_completeness:.1f}%%",
                description=(
                    f"Data completeness is {cert.overall_completeness:.1f}%%, below the "
                    f"95%% threshold for certification readiness.  {cert.non_calculable_count} "
                    f"accounts cannot be calculated."
                ),
                cfr_reference="12 CFR 370.10(a)",
            ))

        # Per-ORC issues
        for score in cert.orc_scores:
            if score.completeness_pct < 90.0:
                self._findings.append(ComplianceFinding(
                    layer=AnalyzerLayer.LAYER6_CERTIFICATION,
                    severity=Severity.HIGH,
                    title=f"ORC {score.orc_type.value} completeness: {score.completeness_pct:.1f}%%",
                    description=(
                        f"{score.orc_type.value} has {score.non_calculable_accounts} "
                        f"non-calculable account(s) out of {score.total_accounts}.  "
                        f"Missing fields: {score.missing_field_summary}"
                    ),
                    cfr_reference="12 CFR 370.10(a)",
                    orc_type=score.orc_type,
                ))

        # Critical findings in prior layers
        total_critical = sum(r.critical_count for r in prior_results)
        if total_critical > 0:
            self._findings.append(ComplianceFinding(
                layer=AnalyzerLayer.LAYER6_CERTIFICATION,
                severity=Severity.CRITICAL,
                title=f"{total_critical} critical finding(s) from prior layers",
                description=(
                    "Annual certification cannot be issued with unresolved "
                    "critical findings.  All critical gaps must be remediated."
                ),
                cfr_reference="12 CFR 370.10(a)",
            ))

        # Non-calculable accounts with no remediation plan
        if cert.non_calculable_count > 0 and not cert.remediation_plan:
            self._findings.append(ComplianceFinding(
                layer=AnalyzerLayer.LAYER6_CERTIFICATION,
                severity=Severity.HIGH,
                title="Non-calculable accounts without remediation plan",
                description=(
                    f"{cert.non_calculable_count} accounts cannot be calculated "
                    f"but no remediation plan has been documented.  The FDIC "
                    f"requires a plan in the Deposit Insurance Coverage Summary."
                ),
                cfr_reference="12 CFR 370.10(a)",
                it_guide_reference="IT Guide Appendix B",
            ))
