"""
Auth Service — Authentication, authorisation, and depositor input validation.

Semantic-label key (IDs are in regulations/fdic_370_controls.json; labels here are stable)
-------------------------------------------------------------------------------------------
  [AUDIT_TRAIL]      UTC-timestamped immutable record of every authentication event
  [ACCESS_CONTROL]   RBAC authentication and authorisation decision logging
  [INPUT_VALIDATION] pre-flight data validation before accepting any depositor record
  [PII_PROTECTION]   encryption/masking of SSN, TIN, and other sensitive PII fields
  [NULL_HANDLING]    valid null / missing-value handling for optional attributes

Controls correctly implemented (PASS)
--------------------------------------
  [AUDIT_TRAIL]      validate_jwt() records a UTC-timestamped audit entry on every
                     authentication event (success and failure) with user_id and iat.
  [NULL_HANDLING]    validate_depositor_input() treats a missing `address` field as
                     a valid null and does NOT raise an error for it.
  [INPUT_VALIDATION] validate_depositor_input() rejects unknown account_type values
                     and non-negative balance before any record is written.
  [INPUT_VALIDATION] validate_tin_format() enforces strict NNN-NN-NNNN regex pattern.

Intentional violations for Kratos to detect
--------------------------------------------
  CRITICAL  [PII_PROTECTION]   SECRET_KEY is a hardcoded plaintext string — must be
                                loaded from a secrets manager, not source code.
  CRITICAL  [PII_PROTECTION]   encrypt_pii() returns plaintext unchanged — no AES-256
                                encryption applied to SSN/TIN before storage.
  HIGH      [ACCESS_CONTROL]   check_deposit_access() hard-codes role='admin' for every
                                authenticated user — no actual user-role lookup.
  MEDIUM    [INPUT_VALIDATION] validate_depositor_input() performs only a presence check
                                on TIN/SSN — format pattern not enforced at that call site.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

try:
    import jwt
except ImportError:               # allow static analysis when PyJWT absent
    jwt = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# ── [PII_PROTECTION] VIOLATION: SECRET_KEY is a hardcoded plaintext string ──────────
SECRET_KEY = "secret-key-placeholder"   # [PII_PROTECTION] CRITICAL VIOLATION
# In production: SECRET_KEY = os.environ["JWT_SIGNING_KEY"]  (loaded from vault / env)

# ── [ACCESS_CONTROL]: Role-based access control definitions ──────────────────────
# Roles that are permitted to read/write deposit records
ROLE_HIERARCHY: Dict[str, List[str]] = {
    "admin":      ["read_deposit", "write_deposit", "run_determination", "admin"],
    "analyst":    ["read_deposit", "run_determination"],
    "auditor":    ["read_deposit"],
    "readonly":   ["read_deposit"],
}


def validate_jwt(token: str) -> Optional[dict]:
    """[AUDIT_TRAIL] — Validate JWT and write a UTC-timestamped audit entry.

    PASS: every call (success or failure) records a timestamped audit log entry
    containing user_id and the UTC timestamp of the authentication event.
    Administrative operations MUST call this before proceeding.
    """
    import datetime as _dt
    if jwt is None:
        logger.error("[AUDIT_TRAIL]: PyJWT not installed — cannot validate token")
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])  # [PII_PROTECTION]: weak secret
        # [AUDIT_TRAIL] PASS: UTC-timestamped audit entry on every successful auth
        logger.info(
            "[AUDIT_TRAIL]: auth_success user=%s iat=%s ts=%s",
            payload.get("user_id"),
            payload.get("iat"),
            _dt.datetime.now(_dt.timezone.utc).isoformat(),
        )
        return payload
    except Exception as exc:  # jwt.InvalidTokenError or AttributeError when jwt=None
        logger.error("[AUDIT_TRAIL]: auth_failure ts=%s reason=%s",
                     _dt.datetime.now(_dt.timezone.utc).isoformat(), exc)
        return None


def check_deposit_access(user_id: str, permission: str) -> bool:
    """[ACCESS_CONTROL] — RBAC check for deposit record operations.

    [ACCESS_CONTROL] PASS: every access decision is written to the access-control log
    with user_id, requested permission, resolved role, and decision outcome.

    [ACCESS_CONTROL] VIOLATION: role is hard-coded to 'admin' for every non-empty
    user_id — no actual user-role lookup is performed against the user store.
    All authenticated users therefore receive full admin permissions.
    """
    if not user_id:
        logger.warning("[ACCESS_CONTROL]: access denied — no user_id")  # [ACCESS_CONTROL]: logged
        return False
    # [ACCESS_CONTROL] VIOLATION: role always 'admin' regardless of actual user role
    role = "admin"                            # should be: load_user_role(user_id)
    allowed = permission in ROLE_HIERARCHY.get(role, [])
    # [ACCESS_CONTROL] PASS: decision logged with user, role, permission, and result
    logger.info("[ACCESS_CONTROL]: user=%s role=%s permission=%s allowed=%s",
                user_id, role, permission, allowed)
    return allowed


# Kept for backward compatibility
check_permission = check_deposit_access


def validate_depositor_input(data: Dict) -> Dict[str, str]:
    """[INPUT_VALIDATION] — Pre-flight depositor data validation before any record write.

    [INPUT_VALIDATION] PASS: account_type and balance are validated against known
    enumerated values and type constraints before any write is allowed.
    [NULL_HANDLING] PASS: missing `address` field is treated as a valid null —
    no error raised for optional attributes that may be unavailable.
    [INPUT_VALIDATION] VIOLATION: TIN/SSN accepted with presence-only check — the
    format pattern r'^\\d{3}-\\d{2}-\\d{4}$' is NOT enforced.
    """
    errors: Dict[str, str] = {}

    # [INPUT_VALIDATION]: full legal name required (CS_Name equivalent)
    name = data.get("depositor_name", "")
    if not name or not name.strip():
        errors["depositor_name"] = "Full legal name is required"

    # [INPUT_VALIDATION] VIOLATION: TIN accepted as-is — only presence checked
    tin = data.get("tin", "")
    if not tin:  # presence-only check — format not validated
        errors["tin"] = "TIN/SSN is required"
    # Missing: import re; if not re.match(r'^\d{3}-\d{2}-\d{4}$', tin): errors['tin']='Invalid SSN format'

    # [INPUT_VALIDATION] PASS: account type validated against DP_Prod_Cat enumeration
    valid_types = {"checking", "savings", "cd", "ira", "money_market", "trust"}
    acct_type = data.get("account_type", "")
    if acct_type not in valid_types:             # [INPUT_VALIDATION]: reject unknown type codes
        errors["account_type"] = (
            f"Unknown account type '{acct_type}'; expected one of {valid_types}"
        )

    # [INPUT_VALIDATION] PASS: balance validated as non-negative number before write
    balance = data.get("balance")
    if balance is None:
        errors["balance"] = "Balance is required"
    elif not isinstance(balance, (int, float)) or balance < 0:
        errors["balance"] = "Balance must be a non-negative number"

    # [NULL_HANDLING] PASS: address is optional — missing value accepted as valid null
    # (no error added for data.get('address') returning None)

    if errors:
        logger.warning("[INPUT_VALIDATION]: depositor input validation failed: %s", errors)
    return errors


def encrypt_pii(plaintext: str) -> str:
    """[PII_PROTECTION] — AES-256 encryption of PII fields (SSN/TIN) before storage.

    [PII_PROTECTION] VIOLATION: function returns plaintext unchanged — no encryption
    is applied.  Every TIN/SSN written through this path is stored as raw text.
    In production: use cryptography.fernet (AES-128-CBC) or a KMS-backed envelope.
    """
    # [PII_PROTECTION] VIOLATION: no-op — plaintext returned without encryption
    return plaintext  # VIOLATION — caller receives unencrypted SSN/TIN


def validate_tin_format(tin: str) -> bool:
    """[INPUT_VALIDATION] / [PII_PROTECTION] — Validate SSN/TIN format before accepting.

    [INPUT_VALIDATION] PASS: regex pattern enforced; rejects malformed TIN strings.
    Called separately from validate_depositor_input() — the main input validator
    currently does NOT call this function (see violation note there).
    """
    import re
    # [INPUT_VALIDATION] PASS: strict format check — 9 digits in NNN-NN-NNNN pattern
    return bool(re.match(r'^\d{3}-\d{2}-\d{4}$', tin.strip()))


def require_admin_auth(token: str) -> bool:
    """[AUDIT_TRAIL] — Gate for administrative operations; requires valid auth token.

    [AUDIT_TRAIL] PASS: validate_jwt() records a timestamped audit entry before
    any privileged action is permitted (see validate_jwt implementation).
    """
    payload = validate_jwt(token)   # [AUDIT_TRAIL]: timestamped audit logged inside
    if not payload:
        return False
    return check_deposit_access(payload.get("user_id", ""), "admin")
