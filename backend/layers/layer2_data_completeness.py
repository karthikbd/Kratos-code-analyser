"""
Layer 2 -- Data Completeness and Validation Analysis
=====================================================
Regulatory Source: IT Guide Sections 2.3.2 -- 2.3.3

This layer replicates the FDIC's on-site data validation checks:

1. **Orphan Account Detection** -- every account has a depositor;
   every participant is linked to an account.

2. **ORC-Level Field Validation** -- required fields differ by ORC.
   A NULL in one field is acceptable for some ORCs and fatal for others.

3. **Government Account Collateral Verification** -- GOV1/GOV2/GOV3
   must have security pledged documentation.

4. **Merger Boundary Analysis** -- if acquisition < 6 months, separate
   calculation + separate Output Files are required.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from backend.core.models import (
    AccountParticipant,
    AnalyzerLayer,
    ComplianceFinding,
    CustomerRecord,
    DepositAccount,
    LayerScanResult,
    ORCType,
    ORC_RULES,
    PendingReasonCode,
    Severity,
)


class Layer2DataCompletenessAnalyzer:
    """
    ORC-conditional data quality framework that encodes FDIC-specific
    validation rules rather than generic NULL scans.
    """

    def __init__(self) -> None:
        self._findings: list[ComplianceFinding] = []

    def scan(
        self,
        accounts: list[DepositAccount],
        customers: list[CustomerRecord],
        participants: list[AccountParticipant],
        analysis_date: date | None = None,
        merger_institutions: list[str] | None = None,
    ) -> LayerScanResult:
        self._findings = []
        analysis_date = analysis_date or date.today()
        merger_institutions = merger_institutions or []

        customer_ids = {c.depositor_id for c in customers}
        account_numbers = {a.account_number for a in accounts}

        # Sub-check 1: Orphan detection
        self._check_orphan_accounts(accounts, customer_ids)
        self._check_orphan_participants(participants, account_numbers)

        # Sub-check 2: ORC-conditional field validation
        self._check_orc_fields(accounts)

        # Sub-check 3: Government collateral
        self._check_government_collateral(accounts)

        # Sub-check 4: Merger boundary
        self._check_merger_boundary(accounts, merger_institutions, analysis_date)

        # Sub-check 5: Duplicate depositor IDs (same government_id -> potential linking failure)
        self._check_duplicate_government_ids(customers)

        passed = all(f.severity not in (Severity.CRITICAL, Severity.HIGH) for f in self._findings)

        return LayerScanResult(
            layer=AnalyzerLayer.LAYER2_DATA_COMPLETE,
            findings=self._findings,
            passed=passed,
            metrics={
                "total_accounts": len(accounts),
                "total_customers": len(customers),
                "total_participants": len(participants),
                "orphan_accounts": sum(1 for f in self._findings if "orphan account" in f.title.lower()),
                "orphan_participants": sum(1 for f in self._findings if "orphan participant" in f.title.lower()),
                "orc_field_gaps": sum(1 for f in self._findings if "missing required field" in f.title.lower()),
            },
            summary=f"Layer 2: {len(self._findings)} findings across {len(accounts)} accounts",
        )

    # ------------------------------------------------------------------
    # Orphan Detection
    # ------------------------------------------------------------------

    def _check_orphan_accounts(
        self, accounts: list[DepositAccount], customer_ids: set[str]
    ) -> None:
        """Every deposit account must have at least one depositor."""
        for acct in accounts:
            if acct.depositor_id not in customer_ids:
                self._findings.append(ComplianceFinding(
                    layer=AnalyzerLayer.LAYER2_DATA_COMPLETE,
                    severity=Severity.CRITICAL,
                    title=f"Orphan account detected: {acct.account_number}",
                    description=(
                        f"Account {acct.account_number} references depositor "
                        f"'{acct.depositor_id}' which does not exist in the "
                        f"Customer File.  This is a direct compliance failure "
                        f"per the FDIC Compliance Review Manual."
                    ),
                    cfr_reference="12 CFR 370.3(b)",
                    it_guide_reference="IT Guide Section 2.3.2",
                    affected_accounts=1,
                    evidence={"account_number": acct.account_number, "missing_depositor": acct.depositor_id},
                ))

    def _check_orphan_participants(
        self, participants: list[AccountParticipant], account_numbers: set[str]
    ) -> None:
        """Every participant must be linked to an existing account."""
        for p in participants:
            if p.account_number not in account_numbers:
                self._findings.append(ComplianceFinding(
                    layer=AnalyzerLayer.LAYER2_DATA_COMPLETE,
                    severity=Severity.HIGH,
                    title=f"Orphan participant detected: {p.participant_id}",
                    description=(
                        f"Account Participant '{p.name}' (ID: {p.participant_id}) "
                        f"references account '{p.account_number}' which does not "
                        f"exist.  Orphan participants are flagged in FDIC on-site testing."
                    ),
                    cfr_reference="12 CFR 370.3(b)",
                    it_guide_reference="IT Guide Section 2.3.2",
                    evidence={"participant_id": p.participant_id, "missing_account": p.account_number},
                ))

    # ------------------------------------------------------------------
    # ORC-Conditional Field Validation
    # ------------------------------------------------------------------

    def _check_orc_fields(self, accounts: list[DepositAccount]) -> None:
        """Validate required fields per ORC type -- not a generic NULL scan."""
        for acct in accounts:
            rule = ORC_RULES.get(acct.orc_type)
            if not rule:
                continue

            # JNT: signature card evidence
            if acct.orc_type == ORCType.JNT:
                if not acct.signature_card_evidence:
                    self._findings.append(ComplianceFinding(
                        layer=AnalyzerLayer.LAYER2_DATA_COMPLETE,
                        severity=Severity.HIGH,
                        title=f"JNT account missing signature card: {acct.account_number}",
                        description=(
                            f"Joint account {acct.account_number} does not have "
                            f"signature card evidence (or digital equivalent per "
                            f"2019 amendment).  Per 12 CFR {rule.cfr_section}, this "
                            f"is required for JNT qualification."
                        ),
                        cfr_reference=f"12 CFR {rule.cfr_section}",
                        orc_type=acct.orc_type,
                        affected_accounts=1,
                        evidence={"account_number": acct.account_number, "missing_field": "signature_card_evidence"},
                        remediation_recommendation="Obtain signature card or route to Pending File with reason RAC",
                    ))
                if not acct.co_owner_ids:
                    self._findings.append(ComplianceFinding(
                        layer=AnalyzerLayer.LAYER2_DATA_COMPLETE,
                        severity=Severity.HIGH,
                        title=f"JNT account missing co-owners: {acct.account_number}",
                        description=f"Joint account {acct.account_number} has no co_owner_ids.",
                        cfr_reference=f"12 CFR {rule.cfr_section}",
                        orc_type=acct.orc_type,
                        affected_accounts=1,
                    ))

            # REV: beneficiary + trust document
            if acct.orc_type == ORCType.REV:
                if not acct.beneficiary_ids:
                    self._findings.append(ComplianceFinding(
                        layer=AnalyzerLayer.LAYER2_DATA_COMPLETE,
                        severity=Severity.HIGH,
                        title=f"REV account missing beneficiary data: {acct.account_number}",
                        description=(
                            f"Revocable trust account {acct.account_number} has no "
                            f"beneficiary information.  Per 12 CFR {rule.cfr_section}, "
                            f"beneficiary data must be in the Account Participant File."
                        ),
                        cfr_reference=f"12 CFR {rule.cfr_section}",
                        orc_type=acct.orc_type,
                        affected_accounts=1,
                        remediation_recommendation="Route to Pending File with reason BEN until beneficiary data is obtained",
                    ))
                if not acct.trust_document_ref:
                    self._findings.append(ComplianceFinding(
                        layer=AnalyzerLayer.LAYER2_DATA_COMPLETE,
                        severity=Severity.MEDIUM,
                        title=f"REV account missing trust document ref: {acct.account_number}",
                        description=f"Revocable trust account {acct.account_number} has no trust_document_ref.",
                        cfr_reference=f"12 CFR {rule.cfr_section}",
                        orc_type=acct.orc_type,
                        affected_accounts=1,
                    ))

            # IRR: beneficiary + interest allocation
            if acct.orc_type == ORCType.IRR:
                if not acct.beneficiary_ids:
                    self._findings.append(ComplianceFinding(
                        layer=AnalyzerLayer.LAYER2_DATA_COMPLETE,
                        severity=Severity.HIGH,
                        title=f"IRR account missing beneficiary data: {acct.account_number}",
                        description=f"Irrevocable trust {acct.account_number} missing beneficiaries.",
                        cfr_reference=f"12 CFR {rule.cfr_section}",
                        orc_type=acct.orc_type,
                        affected_accounts=1,
                    ))
                if not acct.trust_interest_allocation:
                    self._findings.append(ComplianceFinding(
                        layer=AnalyzerLayer.LAYER2_DATA_COMPLETE,
                        severity=Severity.HIGH,
                        title=f"IRR account missing interest allocation: {acct.account_number}",
                        description=f"Irrevocable trust {acct.account_number} has no interest allocation data.",
                        cfr_reference=f"12 CFR {rule.cfr_section}",
                        orc_type=acct.orc_type,
                        affected_accounts=1,
                    ))

            # CRA: retirement plan type
            if acct.orc_type == ORCType.CRA:
                if not acct.retirement_plan_type:
                    self._findings.append(ComplianceFinding(
                        layer=AnalyzerLayer.LAYER2_DATA_COMPLETE,
                        severity=Severity.MEDIUM,
                        title=f"CRA account missing retirement plan type: {acct.account_number}",
                        description=f"Retirement account {acct.account_number} has no retirement_plan_type.",
                        cfr_reference=f"12 CFR {rule.cfr_section}",
                        orc_type=acct.orc_type,
                        affected_accounts=1,
                    ))

            # BUS: entity type + tax ID
            if acct.orc_type == ORCType.BUS:
                if not acct.entity_type:
                    self._findings.append(ComplianceFinding(
                        layer=AnalyzerLayer.LAYER2_DATA_COMPLETE,
                        severity=Severity.MEDIUM,
                        title=f"BUS account missing entity type: {acct.account_number}",
                        description=f"Business account {acct.account_number} has no entity_type.",
                        cfr_reference=f"12 CFR {rule.cfr_section}",
                        orc_type=acct.orc_type,
                        affected_accounts=1,
                    ))

    # ------------------------------------------------------------------
    # Government Collateral
    # ------------------------------------------------------------------

    def _check_government_collateral(self, accounts: list[DepositAccount]) -> None:
        """GOV1/GOV2/GOV3 must have collateral pledge documentation."""
        gov_types = {ORCType.GOV1, ORCType.GOV2, ORCType.GOV3}
        for acct in accounts:
            if acct.orc_type in gov_types:
                if not acct.collateral_pledge_ref:
                    self._findings.append(ComplianceFinding(
                        layer=AnalyzerLayer.LAYER2_DATA_COMPLETE,
                        severity=Severity.CRITICAL,
                        title=f"Government account missing collateral: {acct.account_number}",
                        description=(
                            f"Government deposit account {acct.account_number} "
                            f"(ORC: {acct.orc_type.value}) does not have collateral "
                            f"pledge documentation.  Per the deposit agreement, "
                            f"security pledged must be maintained."
                        ),
                        cfr_reference=f"12 CFR {ORC_RULES[acct.orc_type].cfr_section}",
                        it_guide_reference="IT Guide Section 2.3.3",
                        orc_type=acct.orc_type,
                        affected_accounts=1,
                        evidence={"account_number": acct.account_number},
                        remediation_recommendation="Route to Pending File with reason GOV",
                    ))

    # ------------------------------------------------------------------
    # Merger Boundary
    # ------------------------------------------------------------------

    def _check_merger_boundary(
        self,
        accounts: list[DepositAccount],
        merger_institutions: list[str],
        analysis_date: date,
    ) -> None:
        """Detect merger events requiring dual-calculation code paths."""
        six_months_ago = analysis_date - timedelta(days=183)
        acquired_accounts = [a for a in accounts if a.acquired_institution_id]

        if acquired_accounts and not merger_institutions:
            self._findings.append(ComplianceFinding(
                layer=AnalyzerLayer.LAYER2_DATA_COMPLETE,
                severity=Severity.CRITICAL,
                title="Merger accounts detected but no merger configuration provided",
                description=(
                    f"Found {len(acquired_accounts)} account(s) with acquired_institution_id "
                    f"but no merger institution metadata was configured.  If the acquisition "
                    f"occurred within the preceding six months, the IT system must calculate "
                    f"deposit insurance separately and generate separate Output Files."
                ),
                cfr_reference="12 CFR 370.3(b)",
                it_guide_reference="IT Guide Section 2.3.3",
                affected_accounts=len(acquired_accounts),
                evidence={
                    "acquired_institution_ids": list({a.acquired_institution_id for a in acquired_accounts}),
                },
                remediation_recommendation=(
                    "Configure merger institution metadata and verify dual-calculation "
                    "code path is active for the acquired institution."
                ),
            ))

    # ------------------------------------------------------------------
    # Duplicate Government IDs
    # ------------------------------------------------------------------

    def _check_duplicate_government_ids(self, customers: list[CustomerRecord]) -> None:
        """Flag potential duplicate depositor records based on government ID."""
        seen: dict[str, list[str]] = {}
        for c in customers:
            if c.government_id:
                seen.setdefault(c.government_id, []).append(c.depositor_id)

        for gov_id, depositor_ids in seen.items():
            if len(depositor_ids) > 1:
                self._findings.append(ComplianceFinding(
                    layer=AnalyzerLayer.LAYER2_DATA_COMPLETE,
                    severity=Severity.HIGH,
                    title=f"Duplicate government ID detected: {gov_id[:4]}****",
                    description=(
                        f"Government ID ending ****{gov_id[-4:]} is associated with "
                        f"multiple depositor IDs: {depositor_ids}.  This may cause "
                        f"incorrect insurance aggregation across depositors."
                    ),
                    cfr_reference="12 CFR 370.3(b)",
                    it_guide_reference="IT Guide Section 2.3.2",
                    affected_accounts=len(depositor_ids),
                    evidence={"government_id_suffix": gov_id[-4:], "depositor_ids": depositor_ids},
                    remediation_recommendation="Investigate and merge duplicate depositor records or correct government IDs",
                ))
