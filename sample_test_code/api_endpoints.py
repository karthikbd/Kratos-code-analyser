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
"""
from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, Field, field_validator

from auth_service import validate_jwt, check_deposit_access
from business_logic import InsuranceDeterminationService, UserService

# ── CROSS-FILE CALL CHAINS (lineage anchor for compliance analysis) ──────────
# on_demand_determine()
#   → auth_service.validate_jwt(token)               [[ACCESS_CONTROL]: JWT authn]
#   → auth_service.check_deposit_access(user_id, ...) [[ACCESS_CONTROL]: authz check]
#   → business_logic.InsuranceDeterminationService.trigger_on_demand(depositor_id, token)
#       → auth_service.validate_jwt(token)             [[AUDIT_TRAIL]: re-validates + audit]
#       → data_layer.DataStore.get_account(acct_id)    [[UNIQUE_ACCOUNT_ID]: read record]
#       → data_layer.audit_logger.record_determination(...) [[DETERMINATION_LOG]: audit trail]
#
# batch_determine()
#   → auth_service.validate_jwt(token)
#   → business_logic.InsuranceDeterminationService.run_batch_determination(account_ids)
#       → data_layer.DataStore.get_account(acct_id)  [per account in loop]
#       → data_layer.audit_logger.record_determination(run_id, ...)
#
# get_depositor(depositor_id)
#   → auth_service.validate_jwt(token)               [[ACCESS_CONTROL] VIOLATION: authz not checked]
#   → business_logic.UserService.get_profile(user_id)
#       → data_layer.DataStore.get_user(user_id)
# ────────────────────────────────────────────────────────────────────────────

logger = logging.getLogger(__name__)

app = FastAPI(title="FDIC 370 Compliance API")
_determination_svc = InsuranceDeterminationService()
_user_svc = UserService()


# ── [INPUT_VALIDATION]: Pydantic request models — pre-flight input validation ────────────

class DetermineRequest(BaseModel):
    """[INPUT_VALIDATION] / [REQUIRED_DATA] PASS: all fields validated before handler runs."""
    depositor_id: str = Field(..., min_length=1, description="Account or depositor ID")  # [REQUIRED_DATA]
    token: str = Field(..., min_length=1, description="JWT bearer token")


class BatchDetermineRequest(BaseModel):
    account_ids: List[str] = Field(..., min_length=1, description="List of account IDs")  # [REQUIRED_DATA]
    token: str = Field(..., min_length=1)

    @field_validator("account_ids")
    @classmethod
    def no_empty_ids(cls, v: List[str]) -> List[str]:
        """[BALANCE_QUALITY] / [INPUT_VALIDATION] PASS: reject requests that contain blank account IDs."""
        if any(not aid.strip() for aid in v):
            raise ValueError("account_ids must not contain empty strings")  # [INPUT_VALIDATION] PASS
        return v


class RegisterRequest(BaseModel):
    token: str
    user_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)


class ProfileRequest(BaseModel):
    token: str
    user_id: str = Field(..., min_length=1)


# ── On-demand insurance determination trigger ([AUDIT_TRAIL], [ACCESS_CONTROL]) ────────

@app.post("/api/fdic370/determine")
async def on_demand_determine(req: DetermineRequest):
    """[AUDIT_TRAIL] / [ACCESS_CONTROL] — On-demand insurance determination.

    [AUDIT_TRAIL] PASS: validate_jwt() records a UTC-timestamped auth audit
    entry inside its implementation before the determination proceeds.
    [ACCESS_CONTROL] PASS: check_deposit_access() records the RBAC decision with
    user_id, requested permission, and allowed/denied outcome.
    """
    payload = validate_jwt(req.token)          # [AUDIT_TRAIL] PASS: auth audit logged
    if not payload:
        raise HTTPException(401, "Invalid or expired token")
    if not check_deposit_access(payload.get("user_id", ""), "run_determination"):  # [ACCESS_CONTROL] PASS
        raise HTTPException(403, "Insufficient permissions")
    result = _determination_svc.trigger_on_demand(req.depositor_id, req.token)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


@app.post("/api/fdic370/determine/batch")
async def batch_determine(req: BatchDetermineRequest):
    """[DETERMINATION_LOG] / [AUDIT_TRAIL] — Batch determination for a list of accounts.

    [DETERMINATION_LOG]: run_batch_determination() writes a determination audit entry
    internally via audit_logger after processing all accounts.
    [AUDIT_TRAIL] VIOLATION: this API layer does NOT call audit_logger after the
    run — if the internal call is missed, no audit entry exists at the API level.
    """
    payload = validate_jwt(req.token)         # [AUDIT_TRAIL] PASS: auth audit logged
    if not payload:
        raise HTTPException(401, "Invalid or expired token")
    run = _determination_svc.run_batch_determination(req.account_ids)  # [DETERMINATION_LOG] logged inside
    # [AUDIT_TRAIL] VIOLATION: no audit_logger.record_determination() call at this layer
    return _determination_svc.generate_determination_report(run)


# ── Reporting endpoints ([AUDIT_TRAIL], [ACCESS_CONTROL], [INSURANCE_CALC]) ─────────────────

@app.get("/api/fdic370/report/{run_id}")
async def get_determination_report(run_id: str, authorization: Optional[str] = Header(None)):
    """[INSURANCE_CALC] / [AUDIT_TRAIL] — Retrieve the determination report for a run.

    [INSURANCE_CALC] PASS: progress dict contains insured/uninsured amounts per account.
    [AUDIT_TRAIL] VIOLATION: authorization header is checked for presence but the
    token value is NOT decoded or audited — no timestamped access record written.
    """
    # [AUDIT_TRAIL] VIOLATION: token presence checked but not decoded or audited
    if not authorization:
        raise HTTPException(401, "Authorization header required")
    progress = _determination_svc.progress(run_id)
    if progress is None:
        raise HTTPException(404, f"Run {run_id} not found")
    return {"run_id": run_id, "progress": progress}   # [INSURANCE_CALC]: insured amounts in progress


@app.get("/api/fdic370/depositor/{depositor_id}")
async def get_depositor_summary(depositor_id: str, token: str):
    """[ACCESS_CONTROL] / [INSURANCE_CALC] — Per-depositor insured vs. uninsured balance summary.

    [INSURANCE_CALC] PASS: response includes insured_amount and uninsured_amount.
    [ACCESS_CONTROL] VIOLATION: endpoint validates the JWT token but does NOT call
    check_deposit_access() — any authenticated user can read any depositor’s
    balance data, regardless of their assigned role.
    """
    payload = validate_jwt(token)  # [AUDIT_TRAIL] PASS: auth audit logged
    if not payload:
        raise HTTPException(401, "Invalid token")
    # [ACCESS_CONTROL] VIOLATION: check_deposit_access() call missing here
    try:
        summary = _determination_svc.per_depositor_summary(depositor_id)  # [INSURANCE_CALC] PASS
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    return summary


@app.get("/api/fdic370/exceptions/{run_id}")
async def get_exceptions(run_id: str, token: str):
    """[EXCEPTION_REPORT] — Exception/error report for a determination run.

    [EXCEPTION_REPORT] PASS: all errored account IDs captured and returned —
    errors are not silently dropped.
    """
    payload = validate_jwt(token)   # [AUDIT_TRAIL] PASS: auth audit logged
    if not payload:
        raise HTTPException(401, "Invalid token")
    progress = _determination_svc.progress(run_id)
    if progress is None:
        raise HTTPException(404, f"Run {run_id} not found")
    return {"run_id": run_id, "errors": progress.get("errors", [])}  # [EXCEPTION_REPORT] PASS


# ── Legacy user-management endpoints ──────────────────────────────────────

@app.post("/api/register")
async def register_user(req: RegisterRequest):
    """[AUDIT_TRAIL] / [ACCESS_CONTROL] — Register a new user (requires admin JWT)."""
    try:
        success = _user_svc.register_user(req.token, req.user_id, req.name)
        if not success:
            raise HTTPException(400, "Registration failed")
        logger.info("POST /api/register - user %s", req.user_id)
        return {"status": "ok", "user_id": req.user_id}
    except Exception as exc:
        logger.error("Register endpoint error: %s", exc)
        raise HTTPException(500, str(exc))


@app.post("/api/profile")
async def get_profile(req: ProfileRequest):
    """[AUDIT_TRAIL] / [ACCESS_CONTROL] — Get user profile (auth + access check before data access)."""
    try:
        user = _user_svc.get_user_profile(req.token, req.user_id)
        if not user:
            raise HTTPException(404, "User not found")
        logger.info("POST /api/profile - user %s", req.user_id)
        return user
    except Exception as exc:
        logger.error("Profile endpoint error: %s", exc)
        raise HTTPException(500, str(exc))
