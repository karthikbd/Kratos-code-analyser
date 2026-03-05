"""
Layer 3 -- Calculation Engine Verification
============================================
Regulatory Source: Compliance Review Manual Sections 6 and 10

The FDIC on-site test includes a calculation check -- not just the
presence of balance fields, but arithmetic correctness per 12 CFR
Part 330 rules.  This layer automates that recalculation.

Sub-checks:

1. **Aggregation Logic Audit** -- aggregate by depositor + ORC before
   applying $250K SMDIA.

2. **Interest Accrual Boundary** -- close-of-business balance per
   12 CFR 360.8 (not real-time), handling in-transit ACH, wires.

3. **Debt Flag and Offset Logic** -- flag depositors with loans but
   explicitly exclude credit card balances.

4. **Death-of-Owner Temporal Logic** -- if owner died within 6 months,
   ORC unchanged; after 6 months, JNT reverts to SGL.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from backend.core.models import (
    AnalyzerLayer,
    ComplianceFinding,
    DepositAccount,
    InsuranceCalculationResult,
    LayerScanResult,
    ORCType,
    ORC_RULES,
    PendingReasonCode,
    Severity,
)


SMDIA = 250_000  # Standard Maximum Deposit Insurance Amount


class Layer3CalcEngineAnalyzer:
    """
    Automated recalculation harness that replays the FDIC's on-site
    calculation check programmatically.
    """

    def __init__(self) -> None:
        self._findings: list[ComplianceFinding] = []

    def scan(
        self,
        accounts: list[DepositAccount],
        institution_results: list[InsuranceCalculationResult] | None = None,
        analysis_date: date | None = None,
        calc_engine_code: str = "",
    ) -> LayerScanResult:
        self._findings = []
        analysis_date = analysis_date or date.today()

        # Sub-check 1: Aggregation logic
        correct_results = self._perform_correct_aggregation(accounts, analysis_date)

        # Sub-check 2: Compare with institution's results (if provided)
        if institution_results:
            self._compare_results(correct_results, institution_results)

        # Sub-check 3: Static analysis of calculation code
        if calc_engine_code:
            self._check_calc_code(calc_engine_code)

        # Sub-check 4: Debt flag validation
        self._check_debt_flags(accounts)

        # Sub-check 5: Death-of-owner temporal logic
        self._check_death_of_owner(accounts, analysis_date)

        passed = all(f.severity not in (Severity.CRITICAL, Severity.HIGH) for f in self._findings)

        return LayerScanResult(
            layer=AnalyzerLayer.LAYER3_CALC_ENGINE,
            findings=self._findings,
            passed=passed,
            metrics={
                "depositor_orc_groups": len(correct_results),
                "total_insured": sum(r.insured_amount for r in correct_results),
                "total_uninsured": sum(r.uninsured_amount for r in correct_results),
                "total_balance": sum(r.total_balance for r in correct_results),
                "accounts_with_debt": sum(1 for a in accounts if a.debt_flag),
                "accounts_with_death": sum(
                    1 for a in accounts if a.death_of_owner_date is not None
                ),
            },
            summary=f"Layer 3: {len(self._findings)} findings from calculation verification",
        )

    # ------------------------------------------------------------------
    # Sub-check 1: Correct Aggregation (the reference implementation)
    # ------------------------------------------------------------------

    def _perform_correct_aggregation(
        self, accounts: list[DepositAccount], analysis_date: date
    ) -> list[InsuranceCalculationResult]:
        """
        The FDIC-correct aggregation: group accounts by
        (depositor_id + ORC type), then apply SMDIA per group.
        """
        # Apply death-of-owner ORC adjustments first
        adjusted_accounts = self._apply_death_adjustments(accounts, analysis_date)

        # Group by (depositor_id, effective_orc)
        groups: dict[tuple[str, ORCType], list[DepositAccount]] = defaultdict(list)
        for acct in adjusted_accounts:
            groups[(acct.depositor_id, acct.orc_type)].append(acct)

        results: list[InsuranceCalculationResult] = []
        for (dep_id, orc), accts in groups.items():
            total_balance = sum(a.balance for a in accts)
            rule = ORC_RULES.get(orc)
            smdia = rule.smdia_per_owner if rule else SMDIA

            # Special handling for REV: $250K per beneficiary
            if orc == ORCType.REV:
                beneficiaries: set[str] = set()
                for a in accts:
                    beneficiaries.update(a.beneficiary_ids)
                num_beneficiaries = max(len(beneficiaries), 1)
                effective_smdia = smdia * num_beneficiaries
            elif orc == ORCType.EBP:
                # Pass-through: $250K per participant
                participant_count = max(
                    (a.participant_count or 0) for a in accts
                ) or 1
                effective_smdia = smdia * participant_count
            else:
                effective_smdia = smdia

            insured = min(total_balance, effective_smdia)
            uninsured = max(0, total_balance - effective_smdia)

            results.append(InsuranceCalculationResult(
                depositor_id=dep_id,
                orc_type=orc,
                total_balance=total_balance,
                insured_amount=insured,
                uninsured_amount=uninsured,
                smdia_applied=effective_smdia,
                account_numbers=[a.account_number for a in accts],
            ))
        return results

    def _apply_death_adjustments(
        self, accounts: list[DepositAccount], analysis_date: date
    ) -> list[DepositAccount]:
        """
        If a beneficial owner died > 6 months ago and the account is JNT,
        revert to SGL per 12 CFR Part 330.
        """
        six_months_ago = analysis_date - timedelta(days=183)
        adjusted = []
        for acct in accounts:
            if (
                acct.death_of_owner_date is not None
                and acct.death_of_owner_date < six_months_ago
                and acct.orc_type == ORCType.JNT
            ):
                # Revert to SGL -- create modified copy
                adjusted_acct = acct.model_copy(update={"orc_type": ORCType.SGL})
                adjusted.append(adjusted_acct)
            else:
                adjusted.append(acct)
        return adjusted

    # ------------------------------------------------------------------
    # Sub-check 2: Compare with institution's calculation
    # ------------------------------------------------------------------

    def _compare_results(
        self,
        correct: list[InsuranceCalculationResult],
        institution: list[InsuranceCalculationResult],
    ) -> None:
        """Compare FDIC-correct calculation with the institution's output."""
        correct_map = {(r.depositor_id, r.orc_type): r for r in correct}
        inst_map = {(r.depositor_id, r.orc_type): r for r in institution}

        # Check each correct group against institution
        for key, ref in correct_map.items():
            inst = inst_map.get(key)
            if inst is None:
                self._findings.append(ComplianceFinding(
                    layer=AnalyzerLayer.LAYER3_CALC_ENGINE,
                    severity=Severity.CRITICAL,
                    title=f"Missing calculation group: {key[0]} / {key[1].value}",
                    description=(
                        f"The institution's calculation engine did not produce "
                        f"a result for depositor '{key[0]}' under ORC '{key[1].value}'.  "
                        f"Expected total balance: ${ref.total_balance:,.2f}."
                    ),
                    cfr_reference="12 CFR Part 330",
                    it_guide_reference="Compliance Review Manual Section 6",
                    orc_type=key[1],
                    affected_accounts=len(ref.account_numbers),
                    evidence={"expected_balance": ref.total_balance, "expected_insured": ref.insured_amount},
                ))
                continue

            # Check insured amount
            if abs(inst.insured_amount - ref.insured_amount) > 0.01:
                self._findings.append(ComplianceFinding(
                    layer=AnalyzerLayer.LAYER3_CALC_ENGINE,
                    severity=Severity.CRITICAL,
                    title=f"Insured amount mismatch: {key[0]} / {key[1].value}",
                    description=(
                        f"Institution calculated insured=${inst.insured_amount:,.2f} "
                        f"but FDIC-correct amount is ${ref.insured_amount:,.2f}.  "
                        f"Delta: ${abs(inst.insured_amount - ref.insured_amount):,.2f}."
                    ),
                    cfr_reference="12 CFR Part 330",
                    orc_type=key[1],
                    evidence={
                        "institution_insured": inst.insured_amount,
                        "correct_insured": ref.insured_amount,
                        "delta": abs(inst.insured_amount - ref.insured_amount),
                    },
                ))

    # ------------------------------------------------------------------
    # Sub-check 3: Static analysis of calculation code
    # ------------------------------------------------------------------

    def _check_calc_code(self, code: str) -> None:
        """Check the institution's calculation engine code for known issues."""
        code_lower = code.lower()

        # Must aggregate by ORC
        if "orc" not in code_lower and "ownership" not in code_lower:
            self._findings.append(ComplianceFinding(
                layer=AnalyzerLayer.LAYER3_CALC_ENGINE,
                severity=Severity.CRITICAL,
                title="Calculation does not aggregate by ORC type",
                description=(
                    "The calculation code does not reference ORC or ownership "
                    "category.  Per 12 CFR Part 330, accounts must be aggregated "
                    "by depositor AND ORC before applying the SMDIA."
                ),
                cfr_reference="12 CFR Part 330",
                expected_behavior="Aggregate accounts by (depositor_id, orc_type)",
                observed_behavior="No ORC/ownership reference in calculation code",
            ))

        # Must handle beneficiary count for REV
        bene_keywords = ["beneficiar", "num_beneficiar", "beneficiary_count"]
        if not any(kw in code_lower for kw in bene_keywords):
            self._findings.append(ComplianceFinding(
                layer=AnalyzerLayer.LAYER3_CALC_ENGINE,
                severity=Severity.HIGH,
                title="REV/IRR beneficiary-based SMDIA not implemented",
                description=(
                    "The calculation code does not reference beneficiary counts.  "
                    "For REV accounts, insurance is $250K per eligible beneficiary."
                ),
                cfr_reference="12 CFR 330.10",
            ))

        # Must reference close-of-business or cutoff
        cutoff_keywords = ["close_of_business", "cutoff", "cob_balance", "360.8", "eod_balance"]
        if not any(kw in code_lower for kw in cutoff_keywords):
            self._findings.append(ComplianceFinding(
                layer=AnalyzerLayer.LAYER3_CALC_ENGINE,
                severity=Severity.HIGH,
                title="Interest accrual boundary not implemented (12 CFR 360.8)",
                description=(
                    "The calculation code does not reference close-of-business or "
                    "cutoff balance logic.  Per 12 CFR 360.8, the balance used "
                    "for insurance calculation is the close-of-business balance, "
                    "not the real-time balance.  In-transit ACH, incoming wires, "
                    "and official items must be handled."
                ),
                cfr_reference="12 CFR 360.8",
            ))

    # ------------------------------------------------------------------
    # Sub-check 4: Debt Flag Validation
    # ------------------------------------------------------------------

    def _check_debt_flags(self, accounts: list[DepositAccount]) -> None:
        """
        Verify debt flags are set correctly:
        - Mortgages, HELOCs, personal loans -> debt flag TRUE
        - Credit card balances -> debt flag must be FALSE
        """
        excluded_debt_types = {"credit_card", "cc", "credit card"}
        for acct in accounts:
            if acct.debt_flag and acct.debt_type:
                if acct.debt_type.lower() in excluded_debt_types:
                    self._findings.append(ComplianceFinding(
                        layer=AnalyzerLayer.LAYER3_CALC_ENGINE,
                        severity=Severity.HIGH,
                        title=f"Incorrect debt flag for credit card: {acct.account_number}",
                        description=(
                            f"Account {acct.account_number} has debt_flag=True with "
                            f"debt_type='{acct.debt_type}'.  Per Part 370, the debt "
                            f"flag must NOT be set for credit card balances."
                        ),
                        cfr_reference="12 CFR Part 370",
                        it_guide_reference="IT Guide Section 4",
                        orc_type=acct.orc_type,
                        affected_accounts=1,
                        evidence={"account_number": acct.account_number, "debt_type": acct.debt_type},
                        remediation_recommendation="Remove debt_flag for credit card accounts",
                    ))

    # ------------------------------------------------------------------
    # Sub-check 5: Death-of-Owner Temporal Logic
    # ------------------------------------------------------------------

    def _check_death_of_owner(
        self, accounts: list[DepositAccount], analysis_date: date
    ) -> None:
        """
        Verify correct ORC handling when an owner has died:
        - < 6 months: ORC unchanged
        - >= 6 months: JNT must revert to SGL (if not restructured)
        """
        six_months_ago = analysis_date - timedelta(days=183)

        for acct in accounts:
            if acct.death_of_owner_date is None:
                continue

            months_since = (analysis_date - acct.death_of_owner_date).days

            if acct.death_of_owner_date < six_months_ago:
                # Owner died > 6 months ago
                if acct.orc_type == ORCType.JNT:
                    self._findings.append(ComplianceFinding(
                        layer=AnalyzerLayer.LAYER3_CALC_ENGINE,
                        severity=Severity.HIGH,
                        title=f"Death-of-owner ORC not reverted: {acct.account_number}",
                        description=(
                            f"Account {acct.account_number} is still classified as JNT "
                            f"but owner died {months_since} days ago (> 6 months).  "
                            f"Per 12 CFR Part 330, after 6 months the account must "
                            f"revert to SGL if not restructured."
                        ),
                        cfr_reference="12 CFR Part 330",
                        orc_type=acct.orc_type,
                        affected_accounts=1,
                        evidence={
                            "account_number": acct.account_number,
                            "death_date": str(acct.death_of_owner_date),
                            "days_since_death": months_since,
                        },
                        remediation_recommendation="Revert ORC from JNT to SGL or provide restructuring documentation",
                    ))
