"""Update module docstrings for business_logic.py and api_endpoints.py."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

BUSINESS_LOGIC_DOC = '''\
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
"""'''

API_ENDPOINTS_DOC = '''\
"""
API Endpoints — FastAPI routes for FDIC 370 insurance determination and reporting.

Semantic-label key (IDs are in regulations/fdic_370_controls.json; labels here are stable)
-------------------------------------------------------------------------------------------
  [INPUT_VALIDATION]   Pydantic models enforce pre-flight validation on all incoming requests
  [AUDIT_TRAIL]        JWT authentication event logged before any privileged route proceeds
  [ACCESS_CONTROL]     RBAC authorisation decision logged before determination runs
  [DETERMINATION_LOG]  Batch determination result persisted via audit_logger after run
  [BALANCE_QUALITY]    BatchDetermineRequest validator rejects empty account ID strings
  [REQUIRED_DATA]      Required fields enforced by Pydantic Field(min_length=1)

Controls correctly implemented (PASS)
--------------------------------------
  [INPUT_VALIDATION]   DetermineRequest and BatchDetermineRequest are Pydantic models —
                       all fields validated (type, length, non-empty) before handler runs.
  [AUDIT_TRAIL]        on_demand_determine() calls validate_jwt() which records a
                       UTC-timestamped auth audit entry before any privileged action.
  [ACCESS_CONTROL]     on_demand_determine() checks check_deposit_access() and logs the
                       access-control decision before running the determination.
  [BALANCE_QUALITY]    BatchDetermineRequest.no_empty_ids validator rejects requests that
                       contain blank account ID strings before any processing starts.
  [REQUIRED_DATA]      depositor_id and account_ids use Field(min_length=1) —
                       requests with missing required data are rejected at ingress.

Intentional violations for Kratos to detect
--------------------------------------------
  HIGH    [ACCESS_CONTROL]     get_depositor_summary() validates JWT but does NOT call
                               check_deposit_access() — any valid token reads any depositor.
  HIGH    [AUDIT_TRAIL]        batch_determine() does NOT call audit_logger after the batch
                               run — no determination audit entry at the API layer.
  MEDIUM  [AUDIT_TRAIL]        get_determination_report() checks authorization header
                               presence but does not decode or audit the token contents.
"""'''

for fpath, new_doc in [
    (ROOT / "sample_test_code/business_logic.py", BUSINESS_LOGIC_DOC),
    (ROOT / "sample_test_code/api_endpoints.py",  API_ENDPOINTS_DOC),
]:
    src = fpath.read_text(encoding="utf-8")
    updated = re.sub(r'^""".*?"""', new_doc, src, count=1, flags=re.DOTALL)
    fpath.write_text(updated, encoding="utf-8")
    print(f"Updated {fpath.name}")
