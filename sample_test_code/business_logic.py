"""
Business Logic — Insurance determination orchestration and reporting.

Semantic-label key (IDs are in regulations/fdic_370_controls.json; labels here are stable)
-------------------------------------------------------------------------------------------
  [DETERMINATION_LOG]   audit record of every insurance determination run (batch + on-demand)
  [AUDIT_TRAIL]         UTC-timestamped immutable record; naive datetime is a violation
  [RECONCILIATION]      master reconciliation against GL / authoritative source after each run
  [BALANCE_QUALITY]     balance data quality, SMDIA cap (250 000) correctness
  [INSURANCE_CALC]      insured / uninsured amounts surfaced for downstream reporting
  [COMPLIANCE_EVIDENCE] certification documents, test results, and attestation records
  [EXCEPTION_REPORT]    out-of-balance and error conditions routed to structured exception output

Controls correctly implemented (PASS)
--------------------------------------
  [DETERMINATION_LOG]   run_batch_determination() calls audit_logger.record_determination()
                        with run_id, depositor scope, and result counts after every batch.
  [BALANCE_QUALITY]     _determine_single() uses the correct 250 000 SMDIA cap — unlike
                        deposit_service.py which uses the wrong 100 000 constant.
  [INSURANCE_CALC]      Every determination result exposes insured_amount and
                        uninsured_amount for downstream persistence.
  [EXCEPTION_REPORT]    exception_report() collects all errored accounts into a
                        structured output dict rather than silently dropping them.

Intentional violations for Kratos to detect
--------------------------------------------
  HIGH    [RECONCILIATION]      run_batch_determination() never calls reconcile_balances()
                                — no master reconciliation performed after the batch pass.
  HIGH    [COMPLIANCE_EVIDENCE] COMPLIANCE_CERT_PATH points to a file that does not exist
                                in the repository — certification evidence is missing.
  MEDIUM  [EXCEPTION_REPORT]    retry logic uses a bare except with a single immediate
                                re-attempt — no back-off and no dead-letter queue.
  MEDIUM  [AUDIT_TRAIL]         generate_determination_report() uses datetime.utcnow()
                                (no tzinfo) instead of datetime.now(timezone.utc).
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from auth_service import validate_jwt, check_deposit_access
from data_layer import DataStore, audit_logger

# ── CROSS-FILE CALL CHAINS (lineage anchor for compliance analysis) ──────────
# InsuranceDeterminationService.trigger_on_demand(depositor_id, token)
#   → auth_service.validate_jwt(token)               [[AUDIT_TRAIL]: JWT authn + UTC audit]
#   → data_layer.DataStore.get_account(acct_id)       [[UNIQUE_ACCOUNT_ID]: fetch deposit record]
#   → data_layer.audit_logger.record_determination(run_id, 'on-demand', ...) [[DETERMINATION_LOG]]
#
# InsuranceDeterminationService.run_batch_determination(account_ids)
#   → data_layer.DataStore.get_account(acct_id)  [for each account; [RECONCILIATION] gap]
#   → data_layer.audit_logger.record_determination(run_id, 'batch', ...)
#   NOTE [RECONCILIATION] VIOLATION: reconcile_balances() never called inside batch run
#
# InsuranceDeterminationService.generate_determination_report(run_id)
#   → data_layer.DataStore.get_account(acct_id)       [[INSURANCE_CALC]: read records for report]
#   NOTE [PRODUCT_CATEGORY] VIOLATION: output JSON keys do not match FDIC DIF file spec
#
# UserService.get_profile(user_id, token)
#   → auth_service.check_deposit_access(user_id, 'read_profile')
#   → data_layer.DataStore.get_user(user_id)
# ────────────────────────────────────────────────────────────────────────────

logger = logging.getLogger(__name__)

# ── [COMPLIANCE_EVIDENCE]: Compliance certification artifact ────────────────────────────
# [COMPLIANCE_EVIDENCE] VIOLATION: file referenced below does not exist in the repo.
COMPLIANCE_CERT_PATH = Path("certs/fdic_370_compliance_certification.pdf")  # VIOLATION [COMPLIANCE_EVIDENCE]


# ── Insurance determination service ([DETERMINATION_LOG], [BALANCE_QUALITY], [INSURANCE_CALC]) ────

class InsuranceDeterminationService:
    """Orchestrates FDIC 370 insurance determinations at batch and on-demand scale.

    [DETERMINATION_LOG]  PASS  run_batch_determination() writes a determination log entry
                        via audit_logger.record_determination() after every batch.
    [RECONCILIATION]  FAIL  run_batch_determination() does NOT call reconcile_balances();
                        no master reconciliation is performed after the batch pass.
    [BALANCE_QUALITY]   PASS  _determine_single() applies the correct 250 000 SMDIA cap.
    [INSURANCE_CALC]  PASS  Every result exposes insured_amount / uninsured_amount.
    [EXCEPTION_REPORT]  PASS  exception_report() collects all error conditions into a
                        structured dict — errored accounts are never silently dropped.
    [EXCEPTION_REPORT]  FAIL  Retry in run_batch_determination() is a bare immediate
                        re-attempt with no back-off and no dead-letter queue.
    [COMPLIANCE_EVIDENCE]  FAIL  check_certification_artifact() returns False because the
                        certification PDF is absent from the repository.
    [AUDIT_TRAIL]  FAIL  generate_determination_report() uses datetime.utcnow()
                        (naive, no timezone) instead of datetime.now(timezone.utc).
    """

    def __init__(self, db_path: str = "deposits.db") -> None:
        self.store = DataStore(db_path)
        self.store.connect()
        self._progress: Dict[str, Any] = {}  # [DETERMINATION_LOG]: run_id -> progress dict

    def run_batch_determination(self, account_ids: List[str]) -> Dict[str, Any]:
        """[DETERMINATION_LOG] / [RECONCILIATION] — Bulk insurance determination for all accounts.

        [DETERMINATION_LOG] PASS: audit_logger.record_determination() called at end of
        every batch run — run_id, scope, and result counts are all recorded.

        [RECONCILIATION] VIOLATION: reconcile_balances() is never called after the batch
        — no master reconciliation verifies computed totals against the GL source.

        [EXCEPTION_REPORT] VIOLATION: retry on failure uses a bare except with a single
        immediate re-attempt — no exponential back-off and no dead-letter queue
        for accounts that fail on both attempts.
        """
        run_id = str(uuid.uuid4())
        self._progress[run_id] = {"total": len(account_ids), "done": 0, "errors": []}  # progress

        results: List[Dict] = []
        errors: List[Dict] = []

        # [RECONCILIATION] VIOLATION: no start_time / reconciliation checkpoint here
        for acct_id in account_ids:
            try:
                result = self._determine_single(acct_id)
                results.append(result)
            except Exception:     # [EXCEPTION_REPORT] VIOLATION: bare except, no back-off
                try:
                    result = self._determine_single(acct_id)  # single immediate retry
                    results.append(result)
                except Exception as exc2:
                    # [EXCEPTION_REPORT] PASS: error collected into structured list, not discarded
                    errors.append({"account_id": acct_id, "error": str(exc2)})
                    self._progress[run_id]["errors"].append(acct_id)
            finally:
                self._progress[run_id]["done"] += 1
        # [RECONCILIATION] VIOLATION: reconcile_balances() call missing here

        # [DETERMINATION_LOG] PASS: determination log written with run_id and counts
        audit_logger.record_determination(
            run_id, "batch",
            {"count": len(account_ids)},
            {"results_count": len(results), "error_count": len(errors)},
        )
        return {"run_id": run_id, "results": results, "errors": errors}

    def trigger_on_demand(self, depositor_id: str, token: str) -> Dict[str, Any]:
        """[AUDIT_TRAIL] / [DETERMINATION_LOG] — On-demand determination for a single depositor.

        [AUDIT_TRAIL] PASS: validate_jwt() is called first — its implementation
        records a UTC-timestamped authentication audit entry before proceeding.
        [DETERMINATION_LOG] PASS: _determine_single() records a determination audit entry
        via the audit_logger inside the DataStore pipeline.
        """
        payload = validate_jwt(token)       # [AUDIT_TRAIL]: timestamped auth audit logged
        if not payload:                     # authentication required before privileged op
            return {"error": "Unauthorized: invalid token"}
            return {"error": "Unauthorized: invalid token"}
        account = self.store.get_account(depositor_id)
        if not account:
            return {"error": f"Account {depositor_id} not found"}
        return self._determine_single(depositor_id)

    def _determine_single(self, account_id: str) -> Dict:
        """[BALANCE_QUALITY] / [INSURANCE_CALC] — Insurance determination for one account.

        [BALANCE_QUALITY] PASS: correct 250 000 SMDIA cap applied (not the wrong 100 000
        value used in deposit_service.py).
        [INSURANCE_CALC] PASS: insured_amount and uninsured_amount both surfaced
        in the result dict for downstream persistence and reporting.
        """
        account = self.store.get_account(account_id)
        if not account:
            raise ValueError(f"Account {account_id} not in DataStore")
        balance = account.get("balance", 0.0)
        # [BALANCE_QUALITY] PASS: correct 250 000 SMDIA used here
        insured = min(balance, 250_000)  # [BALANCE_QUALITY] PASS — correct SMDIA cap
        return {
            "account_id": account_id,
            "balance": balance,
            "insured_amount": insured,           # [INSURANCE_CALC] PASS: surfaced for reporting
            "uninsured_amount": max(0.0, balance - 250_000),  # [INSURANCE_CALC] PASS
        }

    # ─ Reporting ([AUDIT_TRAIL], [INSURANCE_CALC], [EXCEPTION_REPORT]) ────────────────────────

    def generate_determination_report(self, run_results: Dict) -> Dict:
        """[INSURANCE_CALC] / [AUDIT_TRAIL] — Per-depositor insurance determination report.

        [INSURANCE_CALC] PASS: depositor_results contain insured_amount /
        uninsured_amount from _determine_single (correct 250 000 cap).
        [AUDIT_TRAIL] VIOLATION: generated_at uses datetime.utcnow() — naive
        datetime with no timezone; should use datetime.now(timezone.utc).
        """
        report = {
            "report_type": "fdic_370_determination",
            # [AUDIT_TRAIL] VIOLATION: utcnow() returns naive datetime (no tzinfo)
            "generated_at": __import__("datetime").datetime.utcnow().isoformat(),
            "run_id": run_results.get("run_id"),
            "depositor_results": run_results.get("results", []),  # [INSURANCE_CALC]: insured amounts
            "error_count": len(run_results.get("errors", [])),
        }
        return report  # [INSURANCE_CALC]: machine-readable dict

    def per_depositor_summary(self, account_id: str) -> Dict:
        """[INSURANCE_CALC] — Insured vs. uninsured balance summary for one depositor.

        [INSURANCE_CALC] PASS: result contains both insured_amount and uninsured_amount.
        """
        return self._determine_single(account_id)

    def exception_report(self, run_results: Dict) -> Dict:
        """[EXCEPTION_REPORT] — Exception/error report for a determination run.

        [EXCEPTION_REPORT] PASS: all errored accounts collected into a structured list
        — no error is silently discarded.
        """
        return {
            "report_type": "fdic_370_exceptions",
            "run_id": run_results.get("run_id"),
            "errors": run_results.get("errors", []),  # [EXCEPTION_REPORT] PASS: surfaced
        }

    def progress(self, run_id: str) -> Optional[Dict]:
        """Return completion status for a running determination job."""
        return self._progress.get(run_id)


# ── Testing and certification hooks ([COMPLIANCE_EVIDENCE], [BALANCE_QUALITY]) ─────────────────

def unit_test_insurance_calculation() -> bool:
    """[BALANCE_QUALITY] — Unit test hook: validate SMDIA cap logic.

    [BALANCE_QUALITY] PASS: asserts that accounts with balance > 250 000 have
    insured_amount == 250 000 and uninsured_amount == balance - 250 000.
    """
    svc = InsuranceDeterminationService(":memory:")
    svc.store.upsert_account({"account_id": "T001", "depositor_name": "Alice",
                               "tin": "000-00-0001", "account_type": "savings",
                               "balance": 300_000.0, "ownership_cat": "single",
                               "open_date": "2020-01-01"})
    result = svc._determine_single("T001")
    assert result["insured_amount"] == 250_000.0, "[BALANCE_QUALITY]: SMDIA cap failed"
    assert result["uninsured_amount"] == 50_000.0, "[BALANCE_QUALITY]: uninsured calc failed"
    logger.info("[BALANCE_QUALITY]: unit test passed")  # [COMPLIANCE_EVIDENCE]: test result logged
    return True


def simulate_failure_scenario(account_ids: List[str]) -> Dict:
    """[EXCEPTION_REPORT] — Simulate insured-bank-failure scenario and validate outputs.

    [EXCEPTION_REPORT] PASS: asserts every account has either a determination result
    or an error record — no account silently falls through.
    """
    svc = InsuranceDeterminationService(":memory:")
    run = svc.run_batch_determination(account_ids)
    # [EXCEPTION_REPORT]: assert every account has a determination result or error record
    covered = {r["account_id"] for r in run.get("results", [])}
    errored = {e["account_id"] for e in run.get("errors", [])}
    missing = set(account_ids) - covered - errored
    if missing:
        # [EXCEPTION_REPORT] PASS: gap surfaced as error rather than ignored
        logger.error("[EXCEPTION_REPORT]: failure scenario gap — accounts not determined: %s", missing)
    return run


def check_certification_artifact() -> bool:
    """[COMPLIANCE_EVIDENCE] — Verify compliance certification artifact is present.

    [COMPLIANCE_EVIDENCE] VIOLATION: COMPLIANCE_CERT_PATH does not exist in the repository;
    check returns False — no certification evidence retained.
    """
    exists = COMPLIANCE_CERT_PATH.exists()   # [COMPLIANCE_EVIDENCE] VIOLATION: file missing
    if not exists:
        logger.error("[COMPLIANCE_EVIDENCE]: certification artifact not found at %s", COMPLIANCE_CERT_PATH)
    return exists


# Integration test fixture (wired by nightly CI schedule)
INTEGRATION_TEST_CONFIG = {
    "core_banking_mock_path": "tests/fixtures/core_banking_feed.json",
    "scheduled_test_cron": "0 2 * * *",   # nightly at 02:00 UTC
}


# ── UserService: kept for backward-compat with api_endpoints.py ───────────

class UserService:
    """Legacy orchestrator retained for API endpoint compatibility."""

    def __init__(self) -> None:
        self.data_store = DataStore("users.db")
        self.data_store.connect()

    def register_user(self, token: str, user_id: str, name: str) -> bool:
        """[AUDIT_TRAIL] / [ACCESS_CONTROL]: requires valid JWT and admin role before write."""
        payload = validate_jwt(token)    # [AUDIT_TRAIL]: timestamped auth audit logged
        if not payload:
            logger.warning("Register attempt with invalid token")
            return False
        if not check_deposit_access(payload.get("user_id", ""), "admin"):  # [ACCESS_CONTROL]: access log
            logger.warning("Register attempt without admin role")
            return False
        success = self.data_store.create_user(user_id, name)
        if success:
            logger.info("User %s registered", user_id)
        return success

    def get_user_profile(self, token: str, target_user_id: str) -> dict:
        """[AUDIT_TRAIL] / [ACCESS_CONTROL]: auth and access-control check before data access."""
        payload = validate_jwt(token)    # [AUDIT_TRAIL]: timestamped auth audit logged
        if not payload:
            return {}
        if not check_deposit_access(payload.get("user_id", ""), f"user:{target_user_id}"):
            logger.warning("Access denied to user %s", target_user_id)
            return {}
        user = self.data_store.get_user(target_user_id)
        return user if user else {}
