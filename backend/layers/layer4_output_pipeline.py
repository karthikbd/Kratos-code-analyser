"""
Layer 4 -- Output File Pipeline Integrity Analyzer
====================================================
Regulatory Source: IT Guide Section 5 + Appendix A

Validates the generation pipeline for the four FDIC-required
pipe-delimited ASCII files (Customer, Account, Account Participant,
Pending), plus ARE file ingestion and Credit Balance Processing.

Sub-checks:

1. **End-to-End Pipeline Tracing** -- trace data lineage from source
   systems through to output files; flag truncation, type coercion,
   or field mapping loss.

2. **Pending File Population Logic** -- every account that cannot be
   calculated within 24 hours must have an explicit Pending File path.

3. **ARE File Ingestion** -- the 29-field pipe-delimited ARE file from
   third parties must be accepted, processed iteratively, and support
   idempotent recalculation.

4. **Credit Balance Processing File** -- overpaid-loan credit balances
   must generate a separate file in ARE format within 24 hours.
"""
from __future__ import annotations

from typing import Any

from backend.core.models import (
    AccountFileRecord,
    AccountParticipant,
    AccountParticipantFileRecord,
    AnalyzerLayer,
    AREFileRecord,
    ComplianceFinding,
    CustomerFileRecord,
    CustomerRecord,
    DepositAccount,
    InsuranceCalculationResult,
    LayerScanResult,
    ORCType,
    PendingFileRecord,
    PendingReasonCode,
    Severity,
)


# Maximum field lengths per FDIC spec (simplified)
_FIELD_LIMITS = {
    "customer_name": 35,
    "address_line1": 40,
    "address_line2": 40,
    "city": 25,
    "state": 2,
    "zip_code": 10,
}


class Layer4OutputPipelineAnalyzer:
    """
    Data lineage tracer + format validator for FDIC output files.
    """

    def __init__(self) -> None:
        self._findings: list[ComplianceFinding] = []

    def scan(
        self,
        accounts: list[DepositAccount],
        customers: list[CustomerRecord],
        participants: list[AccountParticipant],
        calc_results: list[InsuranceCalculationResult] | None = None,
        are_files: list[AREFileRecord] | None = None,
        output_generation_code: str = "",
    ) -> LayerScanResult:
        self._findings = []

        # Sub-check 1: Output file completeness
        self._check_output_file_coverage(accounts, customers, participants, calc_results)

        # Sub-check 2: Field truncation / mapping
        self._check_field_truncation(customers)

        # Sub-check 3: Pending file population
        self._check_pending_population(accounts)

        # Sub-check 4: ARE file ingestion
        if are_files:
            self._check_are_ingestion(are_files)

        # Sub-check 5: Output generation code analysis
        if output_generation_code:
            self._check_output_code(output_generation_code)

        # Sub-check 6: Credit balance processing file
        self._check_credit_balance_file(accounts)

        passed = all(f.severity not in (Severity.CRITICAL, Severity.HIGH) for f in self._findings)

        return LayerScanResult(
            layer=AnalyzerLayer.LAYER4_OUTPUT_PIPE,
            findings=self._findings,
            passed=passed,
            metrics={
                "customer_records": len(customers),
                "account_records": len(accounts),
                "participant_records": len(participants),
                "are_records": len(are_files) if are_files else 0,
                "truncation_warnings": sum(
                    1 for f in self._findings if "truncat" in f.title.lower()
                ),
            },
            summary=f"Layer 4: {len(self._findings)} output pipeline findings",
        )

    # ------------------------------------------------------------------
    # Sub-check 1: Output File Coverage
    # ------------------------------------------------------------------

    def _check_output_file_coverage(
        self,
        accounts: list[DepositAccount],
        customers: list[CustomerRecord],
        participants: list[AccountParticipant],
        calc_results: list[InsuranceCalculationResult] | None,
    ) -> None:
        """Verify all 4 required output files can be generated."""
        # Customer File: every depositor referenced by accounts should exist
        depositor_ids_in_accounts = {a.depositor_id for a in accounts}
        depositor_ids_in_customers = {c.depositor_id for c in customers}
        missing = depositor_ids_in_accounts - depositor_ids_in_customers
        if missing:
            self._findings.append(ComplianceFinding(
                layer=AnalyzerLayer.LAYER4_OUTPUT_PIPE,
                severity=Severity.CRITICAL,
                title=f"Customer File incomplete: {len(missing)} depositors missing",
                description=(
                    f"{len(missing)} depositor ID(s) referenced in Account File "
                    f"have no matching Customer File record: {list(missing)[:5]}..."
                ),
                cfr_reference="12 CFR 370.3(b)",
                it_guide_reference="IT Guide Section 5, Appendix A",
                affected_accounts=len(missing),
            ))

        # Account Participant File: at least one participant per account
        accounts_with_participants = {p.account_number for p in participants}
        accounts_without = {a.account_number for a in accounts} - accounts_with_participants
        if accounts_without:
            self._findings.append(ComplianceFinding(
                layer=AnalyzerLayer.LAYER4_OUTPUT_PIPE,
                severity=Severity.HIGH,
                title=f"Account Participant File gaps: {len(accounts_without)} accounts",
                description=(
                    f"{len(accounts_without)} account(s) have no entries in the "
                    f"Account Participant File.  Examples: {list(accounts_without)[:5]}"
                ),
                cfr_reference="12 CFR 370.3(b)",
                it_guide_reference="IT Guide Appendix A",
                affected_accounts=len(accounts_without),
            ))

        # Calculation results coverage
        if calc_results:
            calc_depositors = {r.depositor_id for r in calc_results}
            uncalculated = depositor_ids_in_accounts - calc_depositors
            if uncalculated:
                self._findings.append(ComplianceFinding(
                    layer=AnalyzerLayer.LAYER4_OUTPUT_PIPE,
                    severity=Severity.HIGH,
                    title=f"Accounts without calculation results: {len(uncalculated)}",
                    description=(
                        f"{len(uncalculated)} depositor(s) have accounts but no "
                        f"insurance calculation result.  Must be in Pending File."
                    ),
                    affected_accounts=len(uncalculated),
                ))

    # ------------------------------------------------------------------
    # Sub-check 2: Field Truncation
    # ------------------------------------------------------------------

    def _check_field_truncation(self, customers: list[CustomerRecord]) -> None:
        """Flag data truncation that exceeds FDIC field limits."""
        for cust in customers:
            if len(cust.name) > _FIELD_LIMITS["customer_name"]:
                self._findings.append(ComplianceFinding(
                    layer=AnalyzerLayer.LAYER4_OUTPUT_PIPE,
                    severity=Severity.MEDIUM,
                    title=f"Name truncation: {cust.depositor_id}",
                    description=(
                        f"Customer name '{cust.name}' is {len(cust.name)} chars, "
                        f"exceeding the Customer File limit of "
                        f"{_FIELD_LIMITS['customer_name']} chars.  Truncation must "
                        f"be explicitly justified and documented."
                    ),
                    it_guide_reference="IT Guide Appendix A",
                    evidence={"full_name": cust.name, "limit": _FIELD_LIMITS["customer_name"]},
                ))

    # ------------------------------------------------------------------
    # Sub-check 3: Pending File Population
    # ------------------------------------------------------------------

    def _check_pending_population(self, accounts: list[DepositAccount]) -> None:
        """Verify accounts that should be pending are correctly routed."""
        pending_candidates: list[tuple[DepositAccount, PendingReasonCode]] = []

        for acct in accounts:
            # JNT without signature card -> RAC
            if acct.orc_type == ORCType.JNT and not acct.signature_card_evidence:
                pending_candidates.append((acct, PendingReasonCode.RAC))
            # REV/IRR without beneficiary -> BEN
            if acct.orc_type in (ORCType.REV, ORCType.IRR) and not acct.beneficiary_ids:
                pending_candidates.append((acct, PendingReasonCode.BEN))
            # GOV without collateral -> GOV
            if acct.orc_type in (ORCType.GOV1, ORCType.GOV2, ORCType.GOV3) and not acct.collateral_pledge_ref:
                pending_candidates.append((acct, PendingReasonCode.GOV))
            # Merger accounts -> MRG
            if acct.acquired_institution_id:
                pending_candidates.append((acct, PendingReasonCode.MRG))

        if pending_candidates:
            self._findings.append(ComplianceFinding(
                layer=AnalyzerLayer.LAYER4_OUTPUT_PIPE,
                severity=Severity.HIGH,
                title=f"{len(pending_candidates)} accounts should be in Pending File",
                description=(
                    f"The following accounts require Pending File routing: "
                    + ", ".join(f"{a.account_number} ({r.value})" for a, r in pending_candidates[:10])
                ),
                cfr_reference="12 CFR 370.3(b)",
                it_guide_reference="IT Guide Section 5.3",
                affected_accounts=len(pending_candidates),
                evidence={
                    "pending_by_reason": {
                        r.value: sum(1 for _, rc in pending_candidates if rc == r)
                        for r in PendingReasonCode
                        if any(rc == r for _, rc in pending_candidates)
                    }
                },
            ))

    # ------------------------------------------------------------------
    # Sub-check 4: ARE File Ingestion
    # ------------------------------------------------------------------

    def _check_are_ingestion(self, are_files: list[AREFileRecord]) -> None:
        """Validate ARE file format and iterative recalculation support."""
        # Check for required 29 fields (simplified: check key fields exist)
        for rec in are_files:
            if not rec.beneficial_owner_id or not rec.beneficial_owner_name:
                self._findings.append(ComplianceFinding(
                    layer=AnalyzerLayer.LAYER4_OUTPUT_PIPE,
                    severity=Severity.HIGH,
                    title=f"ARE record missing beneficial owner: {rec.are_submission_id}",
                    description="ARE file record is missing beneficial owner identification.",
                    cfr_reference="12 CFR Part 370",
                    it_guide_reference="IT Guide Addendum - ARE Format",
                ))

        # Check iterative submission support
        submission_ids = {r.are_submission_id for r in are_files}
        sequences = {r.submission_sequence for r in are_files}
        if len(sequences) <= 1:
            self._findings.append(ComplianceFinding(
                layer=AnalyzerLayer.LAYER4_OUTPUT_PIPE,
                severity=Severity.MEDIUM,
                title="ARE iterative recalculation not demonstrated",
                description=(
                    "Sample ARE files have only one submission sequence.  The system "
                    "must support multiple sequential batches and recalculate without "
                    "corrupting prior calculation state."
                ),
                it_guide_reference="IT Guide Section 5",
            ))

        # Check idempotency: same submission_id should not create duplicates
        seen_keys: set[tuple[str, str]] = set()
        for rec in are_files:
            key = (rec.are_submission_id, rec.beneficial_owner_id)
            if key in seen_keys:
                self._findings.append(ComplianceFinding(
                    layer=AnalyzerLayer.LAYER4_OUTPUT_PIPE,
                    severity=Severity.HIGH,
                    title=f"Potential ARE duplicate: {rec.are_submission_id}/{rec.beneficial_owner_id}",
                    description="Same ARE submission+owner combination appears multiple times.",
                ))
            seen_keys.add(key)

    # ------------------------------------------------------------------
    # Sub-check 5: Output Generation Code Analysis
    # ------------------------------------------------------------------

    def _check_output_code(self, code: str) -> None:
        """Static analysis of the output file generation code."""
        code_lower = code.lower()

        required_files = [
            ("Customer File", "customer_file"),
            ("Account File", "account_file"),
            ("Account Participant File", "account_participant"),
            ("Pending File", "pending_file"),
        ]

        for file_name, keyword in required_files:
            if keyword not in code_lower and file_name.lower().replace(" ", "_") not in code_lower:
                self._findings.append(ComplianceFinding(
                    layer=AnalyzerLayer.LAYER4_OUTPUT_PIPE,
                    severity=Severity.CRITICAL,
                    title=f"Missing output file generation: {file_name}",
                    description=(
                        f"The output generation code does not appear to generate "
                        f"the {file_name}.  All four files are required by FDIC."
                    ),
                    cfr_reference="12 CFR 370.3(b)",
                    it_guide_reference="IT Guide Section 5, Appendix A",
                ))

        # Check for pipe delimiter
        if "|" not in code and "pipe" not in code_lower and "delimiter" not in code_lower:
            self._findings.append(ComplianceFinding(
                layer=AnalyzerLayer.LAYER4_OUTPUT_PIPE,
                severity=Severity.HIGH,
                title="Output files may not use pipe-delimited format",
                description=(
                    "FDIC requires pipe-delimited ASCII format for all output files.  "
                    "No pipe delimiter or delimiter reference found in code."
                ),
                it_guide_reference="IT Guide Appendix A",
            ))

    # ------------------------------------------------------------------
    # Sub-check 6: Credit Balance Processing File
    # ------------------------------------------------------------------

    def _check_credit_balance_file(self, accounts: list[DepositAccount]) -> None:
        """
        For overpaid loans creating credit balances on debt accounts,
        a separate Credit Balance Processing File in ARE format is required.
        """
        debt_accounts = [a for a in accounts if a.debt_flag]
        if debt_accounts:
            self._findings.append(ComplianceFinding(
                layer=AnalyzerLayer.LAYER4_OUTPUT_PIPE,
                severity=Severity.MEDIUM,
                title="Credit Balance Processing File generation required",
                description=(
                    f"Found {len(debt_accounts)} account(s) with debt flags.  If any "
                    f"have credit balances on debt accounts (e.g., overpaid loans), "
                    f"a separate Credit Balance Processing File in ARE format must "
                    f"be generated within 24 hours per Appendix C."
                ),
                cfr_reference="12 CFR Part 370",
                it_guide_reference="IT Guide Appendix C",
                affected_accounts=len(debt_accounts),
            ))
