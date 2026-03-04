"""
Replace hard-coded FDIC 370 control IDs in sample code comments / docstrings
with stable semantic labels so the files stay valid across ID-format changes.

Semantic-label vocabulary
--------------------------
[AUDIT_TRAIL]           – timestamped, immutable record of every auth/modification event
[ACCESS_CONTROL]        – authentication and RBAC authorisation decisions
[INPUT_VALIDATION]      – pre-flight data validation before any write
[PII_PROTECTION]        – encryption/masking of SSN, TIN, and other sensitive fields
[INSURANCE_CALC]        – SMDIA cap computation and insured/uninsured amounts
[BALANCE_QUALITY]       – balance data quality, reconciliation, and completeness
[RECONCILIATION]        – master reconciliation against GL / authoritative source
[RECONCILIATION_SCHEDULE] – scheduled timing of reconciliation runs
[DETERMINATION_LOG]     – audit record of every insurance determination run
[REQUIRED_DATA]         – enforcement of required (non-optional) depositor fields
[NULL_HANDLING]         – valid null / missing-value handling for optional attributes
[UNIQUE_ACCOUNT_ID]     – unique stable identifier per deposit account (CS_Unique_ID)
[DEPOSITOR_AGGREGATION] – depositor-level aggregation key across accounts
[PRODUCT_CATEGORY]      – DP_Prod_Cat product-code enumeration (DDA/NOW/MMA/SDA/TDA)
[OWNERSHIP_TYPE]        – AP_Participant_Type / ownership category (POD, BEN, ERISA …)
[GOVT_ID_TYPE]          – CS_Govt_ID_Type enumeration (SSN, EIN, ITIN)
[TRUST_COVERAGE]        – revocable/irrevocable trust beneficiary interest calculation
[JOINT_COVERAGE]        – joint-account co-owner proportional interest
[PARTICIPANT_ID]        – uniqueness constraint on AP_Participant_ID
[RECORD_MATCHING]       – depositor name / CS_Govt_ID matching and nominee attribution
[REFERENTIAL_INTEGRITY] – cross-table / cross-file referential integrity checks
[EXCEPTION_REPORT]      – out-of-balance and error conditions routed to exception report
[COMPLIANCE_EVIDENCE]   – certification documents, test results, and attestation records
[DATA_RETENTION]        – record retention duration, archival, and purge policy
[RECORDKEEPING]         – completeness of required account-record fields
"""

import re
from pathlib import Path

# ── Mapping: exact ID substring → semantic label ─────────────────────────────
ID_TO_LABEL: dict[str, str] = {
    "R-CTL-ac034e": "[INPUT_VALIDATION]",
    "R-CTL-4368ba": "[PII_PROTECTION]",
    "R-CTL-ac2235": "[AUDIT_TRAIL]",
    "R-CTL-1c220e": "[ACCESS_CONTROL]",
    "R-CTL-0a6249": "[NULL_HANDLING]",
    "R-CTL-0aade6": "[DETERMINATION_LOG]",
    "R-CTL-2a3f02": "[RECONCILIATION]",
    "R-CTL-60f8e6": "[INSURANCE_CALC]",
    "R-CTL-40b954": "[REQUIRED_DATA]",
    "R-CTL-aedd5e": "[TRUST_COVERAGE]",
    "R-CTL-29ffa1": "[JOINT_COVERAGE]",
    "R-CTL-bb2667": "[PARTICIPANT_ID]",
    "R-CTL-5f8e2d": "[RECORD_MATCHING]",
    "R-CTL-0eb988": "[UNIQUE_ACCOUNT_ID]",
    "R-CTL-e3331e": "[RECONCILIATION_SCHEDULE]",
    "R-CTL-b751cc": "[RECORDKEEPING]",
    "R-CTL-2c959e": "[INSURANCE_CALC]",
    "R-DQ-402c1c":  "[BALANCE_QUALITY]",
    "R-DQ-673660":  "[DEPOSITOR_AGGREGATION]",
    "R-EC-248a2b":  "[PRODUCT_CATEGORY]",
    "R-EC-a9d855":  "[OWNERSHIP_TYPE]",
    "R-EC-f6e1bb":  "[GOVT_ID_TYPE]",
    "R-EC-838c41":  "[PRODUCT_CATEGORY]",
    "R-RI-90bc8e":  "[REFERENTIAL_INTEGRITY]",
    "R-DOC-23d934": "[EXCEPTION_REPORT]",
    "R-DOC-7466b2": "[COMPLIANCE_EVIDENCE]",
    "R-DOC-af21ed": "[DATA_RETENTION]",
}

# Build a single regex that matches any known ID (longest-first avoids prefix collisions)
_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in sorted(ID_TO_LABEL, key=len, reverse=True)) + r")\b"
)


def _replace(match: re.Match) -> str:
    return ID_TO_LABEL[match.group(0)]


TARGET_FILES = [
    Path("sample_test_code/auth_service.py"),
    Path("sample_test_code/business_logic.py"),
    Path("sample_test_code/api_endpoints.py"),
    Path("sample_test_code/deposit_service.py"),
    Path("sample_test_code/data_layer.py"),
]

ROOT = Path(__file__).resolve().parent.parent  # kratos_v3/

for rel in TARGET_FILES:
    path = ROOT / rel
    original = path.read_text(encoding="utf-8")
    updated, n = _PATTERN.subn(_replace, original)
    if n:
        path.write_text(updated, encoding="utf-8")
        print(f"  {rel}  — {n} replacement(s)")
    else:
        print(f"  {rel}  — nothing to replace")

print("\nDone. Semantic labels now in use; IDs removed from code comments.")
