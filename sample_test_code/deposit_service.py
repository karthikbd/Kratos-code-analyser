"""
Deposit Service — FDIC 12 CFR Part 370 compliance mock.

Semantic-label key (IDs are in regulations/fdic_370_controls.json; labels here are stable)
-------------------------------------------------------------------------------------------
  [INPUT_VALIDATION]      pre-flight data validation before any write
  [NULL_HANDLING]         valid null / missing-value handling for optional fields
  [REQUIRED_DATA]         enforcement of mandatory depositor fields
  [RECORDKEEPING]         completeness of required account-record fields
  [OWNERSHIP_TYPE]        account ownership category enumeration (single/joint/POD/trust …)
  [PRODUCT_CATEGORY]      deposit product-code classification (DDA/NOW/MMA/SDA/TDA)
  [TRUST_COVERAGE]        revocable/irrevocable trust beneficiary interest calculation
  [JOINT_COVERAGE]        joint-account co-owner proportional interest
  [REFERENTIAL_INTEGRITY] cross-table referential integrity checks
  [BALANCE_QUALITY]       balance data quality, reconciliation, and completeness
  [INSURANCE_CALC]        SMDIA cap computation and insured/uninsured amounts
  [RECONCILIATION]        master reconciliation against GL / authoritative source
  [RECONCILIATION_SCHEDULE] scheduled timing and frequency of reconciliation runs
  [AUDIT_TRAIL]           UTC-timestamped immutable record of every significant event
  [DETERMINATION_LOG]     audit record of every insurance determination run
  [EXCEPTION_REPORT]      out-of-balance and error conditions routed to exception report
  [RECORD_MATCHING]       depositor name / govt-ID matching and nominee attribution
  [UNIQUE_ACCOUNT_ID]     unique stable identifier per deposit account
  [DEPOSITOR_AGGREGATION] depositor-level aggregation key across accounts
  [GOVT_ID_TYPE]          SSN / EIN / ITIN type code
  [PARTICIPANT_ID]        uniqueness constraint on participant/beneficiary IDs

Controls correctly implemented (PASS)
--------------------------------------
  [TRUST_COVERAGE]        calculate_trust_coverage() — per-beneficiary 250 k cap applied
  [JOINT_COVERAGE]        calculate_joint_coverage() — proportional split per co-owner
  [OWNERSHIP_TYPE]        determine_pod_coverage() — 250 k POD cap per beneficiary
  [RECONCILIATION]        reconcile_balances() function exists and compares GL vs. DB
  [BALANCE_QUALITY]       validate_core_banking_feed() checks required fields present

Intentional violations for Kratos to detect
--------------------------------------------
  CRITICAL  [BALANCE_QUALITY] / [INSURANCE_CALC] : SMDIA_LIMIT = 100_000  (must be 250_000)
  CRITICAL  [INPUT_VALIDATION]  : get_raw_balance() uses f-string SQL injection
  HIGH      [OWNERSHIP_TYPE]   : OWNERSHIP_CATEGORIES omits 'government' + 'employee_benefit_plan'
  HIGH      [AUDIT_TRAIL]      : process_accounts() has no audit log call
  HIGH      [RECONCILIATION]   : reconcile_balances() never called in process_accounts()
  MEDIUM    [EXCEPTION_REPORT] : discrepancy loop uses bare `continue` instead of alert
  MEDIUM    [RECORD_MATCHING]  : nominee_principal_map is empty — no custodian attribution
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional

# ── CROSS-FILE CALL CHAINS (lineage anchor for compliance analysis) ──────────
# DepositService.process_accounts(accounts)
#   → data_layer.DataStore.create_deposit_record(record)  [[UNIQUE_ACCOUNT_ID]: write]
#   → data_layer.DataStore.get_all_accounts()              [[UNIQUE_ACCOUNT_ID]: read-back]
#   NOTE [AUDIT_TRAIL] VIOLATION: no audit_logger.log() call in process_accounts()
#   NOTE [RECONCILIATION] VIOLATION: reconcile_balances() never called from process_accounts()
#
# DepositService.reconcile_balances()
#   → data_layer.DataStore.get_all_accounts()              [[RECONCILIATION]]
#   → data_layer.audit_logger.log('reconciliation', ...)   [[AUDIT_TRAIL]: logged]
#
# DepositService.get_raw_balance(account_id)  [[INPUT_VALIDATION] VIOLATION: SQL injection]
#   → data_layer.DataStore raw sqlite3 cursor  (f-string interpolation)
# ────────────────────────────────────────────────────────────────────────────

logger = logging.getLogger(__name__)

# ── FDIC regulatory constants ────────────────────────────────────────────────
# [BALANCE_QUALITY] VIOLATION: 12 CFR 330.4 requires SMDIA = 250_000. Value below is wrong.
SMDIA_LIMIT: int = 100_000           # VIOLATION [BALANCE_QUALITY] / [INSURANCE_CALC]
# Correct: SMDIA_LIMIT: int = 250_000  # 12 CFR 330.4 Standard Maximum Deposit Insurance Amount

RETIREMENT_SEPARATE_LIMIT: int = 250_000  # [BALANCE_QUALITY] / [INSURANCE_CALC] — correct per 330.14

# ── Part 330 ownership categories ([OWNERSHIP_TYPE], [PRODUCT_CATEGORY]) ─────────────────
# [OWNERSHIP_TYPE] VIOLATION: 'government' and 'employee_benefit_plan' product codes are absent.
OWNERSHIP_CATEGORIES: List[str] = [
    "single",             # [PRODUCT_CATEGORY] / 330.6
    "joint",              # [PRODUCT_CATEGORY] / 330.9
    "revocable_trust",    # [OWNERSHIP_TYPE] / 330.10  (includes POD)
    "irrevocable_trust",  # [OWNERSHIP_TYPE] / 330.13
    "retirement",         # [PRODUCT_CATEGORY] / 330.14
    "business_entity",    # [PRODUCT_CATEGORY] / 330.11
    # MISSING: "government"            -> [OWNERSHIP_TYPE] VIOLATION
    # MISSING: "employee_benefit_plan"  -> [OWNERSHIP_TYPE] VIOLATION (ERISA)
]


# ── Account record ([UNIQUE_ACCOUNT_ID], [DEPOSITOR_AGGREGATION], [GOVT_ID_TYPE], [PRODUCT_CATEGORY], [BALANCE_QUALITY]) ──────
@dataclass
class AccountRecord:
    """Full depositor account record aligned with 370.4(a) required fields.

    [UNIQUE_ACCOUNT_ID]  account_id           — unique stable identifier (CS_Unique_ID)
    [DEPOSITOR_AGGREGATION]   account_id           — same field used as aggregation key
    [RECORD_MATCHING]  depositor_name       — full legal name (matched against CS_Govt_ID)
    [GOVT_ID_TYPE]   tin                  — SSN or Tax Identification Number (CS_Govt_ID_Type)
    [PRODUCT_CATEGORY]   account_type         — product classification (DP_Prod_Cat: DDA/NOW/MMA/SDA/TDA)
    [BALANCE_QUALITY]   balance              — dollar-cent precision / balance reconciliation
    [REQUIRED_DATA]  open_date / close_date — records with unavailable required data
    [OWNERSHIP_TYPE]   pod_beneficiaries    — list of {name, ssn} dicts (AP_Participant_Type: BEN)
    [TRUST_COVERAGE]  trust_beneficiaries  — revocable/irrevocable trust beneficiaries
    [JOINT_COVERAGE]  co_owners            — joint account co-owner list (AP_Participant_ID)
    [PARTICIPANT_ID]  retirement_beneficiary — AP_Participant_ID uniqueness constraint
    [NULL_HANDLING]  address              — null field representation in output
    """
    account_id: str                                          # [UNIQUE_ACCOUNT_ID] / [DEPOSITOR_AGGREGATION]
    depositor_name: str                                      # [RECORD_MATCHING]
    tin: str                                                 # [GOVT_ID_TYPE]
    account_type: str                                        # [PRODUCT_CATEGORY]
    balance: float                                           # [BALANCE_QUALITY]
    open_date: date                                          # [REQUIRED_DATA]
    ownership_category: str = "single"                       # [PRODUCT_CATEGORY] / [OWNERSHIP_TYPE]
    right_and_capacity: str = "owner"                        # [TRUST_COVERAGE]
    close_date: Optional[date] = None                        # [REQUIRED_DATA]
    address: Optional[str] = None                            # [NULL_HANDLING]
    pod_beneficiaries: List[Dict] = field(default_factory=list)       # [OWNERSHIP_TYPE]
    trust_beneficiaries: List[Dict] = field(default_factory=list)     # [TRUST_COVERAGE]
    co_owners: List[Dict] = field(default_factory=list)               # [JOINT_COVERAGE]
    retirement_beneficiary: Optional[Dict] = None                     # [PARTICIPANT_ID]


# ── RNC: Right and Capacity helpers ─────────────────────────────────────────

# [RECORD_MATCHING] VIOLATION: map is empty — custodian/nominee arrangements are never
# attributed to the underlying principal depositor.
nominee_principal_map: Dict[str, str] = {}


def determine_beneficial_owner(record: AccountRecord) -> str:
    """[TRUST_COVERAGE] / 330 — Identify who holds the beneficial interest.

    [OWNERSHIP_TYPE]: validates POD beneficiary presence (revocable_trust).
    [TRUST_COVERAGE]: computes trust beneficiary interest for irrevocable trusts.
    [JOINT_COVERAGE]: assigns proportional joint-owner capacity (330.9(c)).
    [PARTICIPANT_ID]: uses right_and_capacity for business entity officer role.
    [RECORD_MATCHING]: looks up nominee principal map (empty → logs error).
    [AUDIT_TRAIL]: caller must record a right-and-capacity change audit entry.
    """
    if record.ownership_category == "revocable_trust":
        if not record.pod_beneficiaries:                 # [OWNERSHIP_TYPE] POD validation
            logger.warning("POD account %s has no beneficiaries", record.account_id)
        return record.depositor_name  # grantor retains interest during lifetime

    if record.ownership_category == "irrevocable_trust":
        if not record.trust_beneficiaries:               # [TRUST_COVERAGE]
            logger.warning("Irrevocable trust %s missing beneficiary list", record.account_id)
        return ";" .join(b.get("name", "") for b in record.trust_beneficiaries)

    if record.ownership_category == "joint":
        # [JOINT_COVERAGE]: each co-owner holds proportional interest
        return ";".join(c.get("name", "") for c in record.co_owners) or record.depositor_name

    if record.ownership_category == "business_entity":
        return record.right_and_capacity  # [PARTICIPANT_ID]: officer/agent name for entity

    if record.right_and_capacity == "nominee":
        # [RECORD_MATCHING]: nominee lookup — always empty dict → VIOLATION
        principal = nominee_principal_map.get(record.account_id, "")
        if not principal:
            logger.error("Nominee account %s has no principal mapping", record.account_id)
        return principal

    return record.depositor_name


# ── Insurance aggregation ([BALANCE_QUALITY], [INSURANCE_CALC], [INSURANCE_CALC]) ────────────────

def aggregate_insurance(
    depositor_id: str,
    accounts: List[AccountRecord],
) -> Dict[str, Any]:
    """Aggregate insured amounts per depositor per ownership category.

    [BALANCE_QUALITY] / [INSURANCE_CALC]: Accumulates balances by category then caps at
    SMDIA ([BALANCE_QUALITY]).  Retirement accounts use separate limit ([BALANCE_QUALITY]).
    Results returned for persistence by caller ([INSURANCE_CALC]).
    [PRODUCT_CATEGORY]: All listed OWNERSHIP_CATEGORIES are processed.
    [RECONCILIATION]: FDIC Part 370 reconciliation references appear in comments.
    Errors are caught and logged — no silent failure.
    """
    category_totals: Dict[str, float] = {}

    for acct in accounts:
        if acct.ownership_category not in OWNERSHIP_CATEGORIES:
            # [OWNERSHIP_TYPE]: multi-category depositor — unknown category triggers warning
            logger.warning(
                "Unknown ownership category '%s' for account %s",
                acct.ownership_category, acct.account_id,
            )
            continue
        category_totals[acct.ownership_category] = (
            category_totals.get(acct.ownership_category, 0.0) + acct.balance
        )

    results: Dict[str, Any] = {}
    for cat, total in category_totals.items():
        # [BALANCE_QUALITY]: retirement uses separate limit
        limit = RETIREMENT_SEPARATE_LIMIT if cat == "retirement" else SMDIA_LIMIT
        insured = min(total, limit)                  # [BALANCE_QUALITY] (wrong limit)
        uninsured = max(0.0, total - limit)
        results[cat] = {
            "total_balance": round(total, 2),
            "insured_amount": round(insured, 2),    # [INSURANCE_CALC]: result surfaced for downstream
            "uninsured_amount": round(uninsured, 2),
            "limit_applied": limit,
        }

    logger.info(
        "Insurance aggregation complete for depositor %s: %d categories",
        depositor_id, len(results),
    )
    return results


def calculate_pod_coverage(account: AccountRecord) -> float:
    """[OWNERSHIP_TYPE] / 330.10 — POD per-beneficiary $250K rule.

    Total insured = min(balance, count_of_qualifying_beneficiaries * 250_000).
    """
    count = len(account.pod_beneficiaries)
    if count == 0:
        return 0.0
    # [OWNERSHIP_TYPE]: correct 250_000 (separate constant from SMDIA_LIMIT above)
    return min(account.balance, count * 250_000)


def calculate_joint_coverage(account: AccountRecord) -> Dict[str, float]:
    """[JOINT_COVERAGE] / 330.9(c) — Each joint owner gets up to $250K."""
    result: Dict[str, float] = {}
    for owner in account.co_owners:
        per_owner = account.balance / max(len(account.co_owners), 1)
        result[owner.get("name", "unknown")] = min(per_owner, 250_000)
    return result


# ── DR: Data reconciliation ([RECONCILIATION], [EXCEPTION_REPORT], [BALANCE_QUALITY]) ───────────────

def reconcile_balances(
    computed: Dict[str, float],
    authoritative: Dict[str, float],
) -> Dict[str, Any]:
    """[RECONCILIATION] / [EXCEPTION_REPORT] — Reconcile computed balances against GL source.

    [BALANCE_QUALITY]: `authoritative` dict represents validated core-banking system feed.
    [RECONCILIATION]: account count checked against authoritative count.
    [EXCEPTION_REPORT]: structured reconciliation report returned as dict.
    [RECONCILIATION_SCHEDULE]: intended to run on a daily schedule after every processing pass.
    """
    discrepancies: List[Dict] = []
    for acct_id, calc_bal in computed.items():
        auth_bal = authoritative.get(acct_id)
        if auth_bal is None:
            # [EXCEPTION_REPORT] VIOLATION: bare `continue` — missing account not surfaced as alert
            continue
        diff = round(abs(calc_bal - auth_bal), 2)
        if diff > 0.01:
            discrepancies.append({
                "account_id": acct_id,
                "computed": calc_bal,
                "authoritative": auth_bal,
                "difference": diff,
            })

    report = {
        "run_at": datetime.utcnow().isoformat(),
        "accounts_checked": len(computed),
        "count_match": len(computed) == len(authoritative),  # [RECONCILIATION]
        "discrepancies": discrepancies,
        "discrepancy_count": len(discrepancies),
    }
    if discrepancies:
        logger.error("[EXCEPTION_REPORT]: %d balance discrepancies detected", len(discrepancies))
    else:
        logger.info("[RECONCILIATION]: Balance reconciliation passed (%d accounts)", len(computed))
    return report


def validate_core_banking_feed(feed_records: List[Dict]) -> List[Dict]:
    """[BALANCE_QUALITY] — Validate records from core banking system before processing."""
    valid: List[Dict] = []
    for rec in feed_records:
        if not rec.get("account_id") or rec.get("balance") is None:
            # [BALANCE_QUALITY] / 370.6(b): invalid record should route to Pending File
            logger.warning("Core banking feed record missing required fields: %s", rec)
            continue
        valid.append(rec)
    return valid


# ── Public entry points ──────────────────────────────────────────────────────

def get_raw_balance(account_id: str) -> float:
    """Fetch balance from database.

    [INPUT_VALIDATION] CRITICAL VIOLATION: raw f-string in SQL — pre-flight input validation bypassed.
    [BALANCE_QUALITY] / [RECONCILIATION]: this is the balance source used in reconciliation.
    """
    conn = sqlite3.connect("deposits.db")
    # [INPUT_VALIDATION] VIOLATION: f-string interpolation directly into SQL — no input sanitization
    result = conn.execute(
        f"SELECT balance FROM accounts WHERE id='{account_id}'"
    ).fetchone()
    return float(result[0]) if result else 0.0


def process_accounts(account_list: List[AccountRecord]) -> List[Dict]:
    """Orchestrate per-depositor insurance determination across all accounts.

    [AUDIT_TRAIL] VIOLATION: no audit log call for the determination run.
    [RECONCILIATION] VIOLATION: reconcile_balances() is not invoked.
    Errors are caught and logged (no silent failure — PARTIAL pass).
    [BALANCE_QUALITY]: aggregate_insurance() is the dedicated insurance calculation function.
    """
    results: List[Dict] = []
    for acct in account_list:
        try:
            summary = aggregate_insurance(acct.depositor_name, [acct])  # [BALANCE_QUALITY]
            results.append({
                "account_id": acct.account_id,
                "depositor": acct.depositor_name,
                "insurance_summary": summary,
            })
        except Exception as exc:
            logger.error("Insurance determination failed for %s: %s", acct.account_id, exc)
    # [AUDIT_TRAIL] VIOLATION: missing -> audit_logger.record_determination(results)
    # [RECONCILIATION] VIOLATION: missing -> reconcile_balances(computed_balances, gl_balances)
    return results
