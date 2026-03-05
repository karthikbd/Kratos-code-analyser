"""
Sample Deposit Data Corpus
===========================
Realistic sample data for testing the 6-layer FDIC Part 370 analyzer.
Includes intentional compliance gaps for the analyzer to detect.
"""
from __future__ import annotations

from datetime import date, datetime

from backend.core.models import (
    AccountParticipant,
    AREFileRecord,
    CustomerRecord,
    DepositAccount,
    ORCType,
)


def build_sample_customers() -> list[CustomerRecord]:
    """Sample Customer File with intentional issues."""
    return [
        CustomerRecord(depositor_id="CUST-001", name="Alice Johnson", government_id="111-22-3333"),
        CustomerRecord(depositor_id="CUST-002", name="Bob Smith", government_id="222-33-4444"),
        CustomerRecord(depositor_id="CUST-003", name="Carol Davis", government_id="333-44-5555"),
        CustomerRecord(depositor_id="CUST-004", name="David & Emily Wilson", government_id="444-55-6666"),
        CustomerRecord(depositor_id="CUST-005", name="Acme Corp", government_id="55-1234567",
                        is_natural_person=False),
        CustomerRecord(depositor_id="CUST-006", name="State of Ohio Treasury", government_id="66-0000001",
                        is_natural_person=False),
        # Intentional: deceased owner within 6 months
        CustomerRecord(depositor_id="CUST-007", name="Frank Morris", government_id="777-88-9999",
                        date_of_death=date(2026, 1, 15)),
        # Intentional: deceased owner > 6 months ago
        CustomerRecord(depositor_id="CUST-008", name="Grace Lee", government_id="888-99-0000",
                        date_of_death=date(2025, 6, 1)),
        # Orphan customer - no accounts linked
        CustomerRecord(depositor_id="CUST-009", name="Henry Orphan", government_id="999-00-1111"),
        # Duplicate government_id (same as CUST-001) - intentional data issue
        CustomerRecord(depositor_id="CUST-010", name="Alice J.", government_id="111-22-3333"),
    ]


def build_sample_accounts() -> list[DepositAccount]:
    """Sample accounts with intentional compliance gaps across ORC types."""
    return [
        # ---- SGL accounts ----
        DepositAccount(
            account_number="ACCT-001", depositor_id="CUST-001", balance=180_000.00,
            orc_type=ORCType.SGL, account_type="checking", source_system="CORE_BANKING",
        ),
        DepositAccount(
            account_number="ACCT-002", depositor_id="CUST-001", balance=120_000.00,
            orc_type=ORCType.SGL, account_type="savings", source_system="CORE_BANKING",
        ),
        # SGL total for CUST-001 = $300K -> $250K insured, $50K uninsured

        # ---- JNT accounts ----
        DepositAccount(
            account_number="ACCT-003", depositor_id="CUST-002", balance=400_000.00,
            orc_type=ORCType.JNT, account_type="checking", source_system="CORE_BANKING",
            co_owner_ids=["CUST-003"],
            signature_card_evidence=True,  # Properly documented
        ),
        # Intentional gap: JNT account WITHOUT signature card evidence
        DepositAccount(
            account_number="ACCT-004", depositor_id="CUST-004", balance=350_000.00,
            orc_type=ORCType.JNT, account_type="savings", source_system="CORE_BANKING",
            co_owner_ids=["CUST-002"],
            signature_card_evidence=False,  # COMPLIANCE GAP - should be flagged
        ),

        # ---- REV (Revocable Trust) ----
        DepositAccount(
            account_number="ACCT-005", depositor_id="CUST-003", balance=600_000.00,
            orc_type=ORCType.REV, account_type="savings", source_system="TRUST_SYSTEM",
            beneficiary_ids=["CUST-001", "CUST-002"],
            trust_document_ref="TRUST-2024-001",
        ),
        # Intentional gap: REV account missing beneficiary info
        DepositAccount(
            account_number="ACCT-006", depositor_id="CUST-002", balance=500_000.00,
            orc_type=ORCType.REV, account_type="CD", source_system="TRUST_SYSTEM",
            beneficiary_ids=[],  # COMPLIANCE GAP - REV requires beneficiary
            trust_document_ref=None,  # Also missing trust doc
        ),

        # ---- BUS (Business) ----
        DepositAccount(
            account_number="ACCT-007", depositor_id="CUST-005", balance=750_000.00,
            orc_type=ORCType.BUS, account_type="checking", source_system="COMMERCIAL_SYSTEM",
            entity_type="LLC", tax_id="55-1234567",
        ),

        # ---- GOV2 (State Government) ----
        DepositAccount(
            account_number="ACCT-008", depositor_id="CUST-006", balance=2_000_000.00,
            orc_type=ORCType.GOV2, account_type="checking", source_system="GOVERNMENT_DEPOSITS",
            government_entity_type="STATE",
            collateral_pledge_ref="PLEDGE-2024-001",
            official_custodian_name="Ohio State Treasurer",
        ),
        # Intentional gap: GOV1 without collateral
        DepositAccount(
            account_number="ACCT-009", depositor_id="CUST-006", balance=500_000.00,
            orc_type=ORCType.GOV1, account_type="savings", source_system="GOVERNMENT_DEPOSITS",
            government_entity_type="FEDERAL",
            collateral_pledge_ref=None,  # COMPLIANCE GAP
        ),

        # ---- Death-of-owner accounts ----
        # JNT account where one owner died < 6 months ago -> ORC should remain JNT
        DepositAccount(
            account_number="ACCT-010", depositor_id="CUST-007", balance=200_000.00,
            orc_type=ORCType.JNT, account_type="checking", source_system="CORE_BANKING",
            co_owner_ids=["CUST-002"],
            signature_card_evidence=True,
            death_of_owner_date=date(2026, 1, 15),
        ),
        # JNT account where owner died > 6 months ago -> should revert to SGL
        DepositAccount(
            account_number="ACCT-011", depositor_id="CUST-008", balance=300_000.00,
            orc_type=ORCType.JNT, account_type="savings", source_system="CORE_BANKING",
            co_owner_ids=["CUST-003"],
            signature_card_evidence=True,
            death_of_owner_date=date(2025, 6, 1),  # > 6 months - should be SGL now
        ),

        # ---- Debt flag accounts ----
        DepositAccount(
            account_number="ACCT-012", depositor_id="CUST-001", balance=50_000.00,
            orc_type=ORCType.SGL, account_type="savings", source_system="CORE_BANKING",
            debt_flag=True, debt_type="mortgage",  # Correct: mortgage triggers debt flag
        ),
        # Intentional gap: debt flag set for credit card
        DepositAccount(
            account_number="ACCT-013", depositor_id="CUST-002", balance=25_000.00,
            orc_type=ORCType.SGL, account_type="checking", source_system="CORE_BANKING",
            debt_flag=True, debt_type="credit_card",  # WRONG - credit card should NOT set debt flag
        ),

        # ---- Merger boundary account ----
        DepositAccount(
            account_number="ACCT-014", depositor_id="CUST-001", balance=100_000.00,
            orc_type=ORCType.SGL, account_type="CD", source_system="ACQUIRED_BANK_SYSTEM",
            acquired_institution_id="ACQUIRED-BANK-001",  # From merger < 6 months
        ),

        # ---- Orphan account (no matching customer record) ----
        DepositAccount(
            account_number="ACCT-015", depositor_id="CUST-NONEXISTENT", balance=75_000.00,
            orc_type=ORCType.SGL, account_type="savings", source_system="CORE_BANKING",
        ),

        # ---- CRA (Retirement) ----
        DepositAccount(
            account_number="ACCT-016", depositor_id="CUST-003", balance=280_000.00,
            orc_type=ORCType.CRA, account_type="IRA", source_system="RETIREMENT_SYSTEM",
            retirement_plan_type="TRADITIONAL_IRA",
        ),
    ]


def build_sample_participants() -> list[AccountParticipant]:
    """Sample Account Participant records."""
    return [
        AccountParticipant(account_number="ACCT-001", depositor_id="CUST-001", role="OWNER",
                           name="Alice Johnson", government_id="111-22-3333"),
        AccountParticipant(account_number="ACCT-002", depositor_id="CUST-001", role="OWNER",
                           name="Alice Johnson", government_id="111-22-3333"),
        AccountParticipant(account_number="ACCT-003", depositor_id="CUST-002", role="OWNER",
                           name="Bob Smith", government_id="222-33-4444"),
        AccountParticipant(account_number="ACCT-003", depositor_id="CUST-003", role="OWNER",
                           name="Carol Davis", government_id="333-44-5555"),
        AccountParticipant(account_number="ACCT-005", depositor_id="CUST-001", role="BENEFICIARY",
                           name="Alice Johnson", government_id="111-22-3333"),
        AccountParticipant(account_number="ACCT-005", depositor_id="CUST-002", role="BENEFICIARY",
                           name="Bob Smith", government_id="222-33-4444"),
        # Orphan participant - account doesn't exist
        AccountParticipant(account_number="ACCT-NONEXISTENT", depositor_id="CUST-003",
                           role="BENEFICIARY", name="Carol Davis"),
    ]


def build_sample_are_files() -> list[AREFileRecord]:
    """Sample ARE file submissions (brokered deposit records)."""
    return [
        AREFileRecord(
            are_submission_id="ARE-2026-001",
            account_number="ACCT-100-BROKERED",
            beneficial_owner_id="BO-001",
            beneficial_owner_name="Brokered Depositor One",
            government_id="100-11-2222",
            orc_type="SGL",
            balance=125_000.00,
            submission_sequence=1,
        ),
        AREFileRecord(
            are_submission_id="ARE-2026-001",
            account_number="ACCT-100-BROKERED",
            beneficial_owner_id="BO-002",
            beneficial_owner_name="Brokered Depositor Two",
            government_id="100-22-3333",
            orc_type="SGL",
            balance=175_000.00,
            submission_sequence=1,
        ),
        # Second submission batch (iterative)
        AREFileRecord(
            are_submission_id="ARE-2026-002",
            account_number="ACCT-100-BROKERED",
            beneficial_owner_id="BO-003",
            beneficial_owner_name="Brokered Depositor Three",
            government_id="100-33-4444",
            orc_type="JNT",
            balance=200_000.00,
            submission_sequence=2,
        ),
    ]


# ============================================================================
# Sample ORC Assignment Code (the code BEING ANALYZED by Layer 1)
# ============================================================================

SAMPLE_ORC_ASSIGNMENT_CODE = '''
def assign_orc(account: dict) -> str:
    """Assign Ownership Right and Capacity to a deposit account."""
    acct_type = account.get("account_type", "")
    entity = account.get("entity_type", "")

    if entity in ("LLC", "CORP", "PARTNERSHIP"):
        return "BUS"

    if acct_type == "IRA":
        return "CRA"

    co_owners = account.get("co_owner_ids", [])
    if len(co_owners) > 0:
        # BUG: Does not check if co-owners are natural persons
        # BUG: Does not verify signature card evidence
        return "JNT"

    trust_ref = account.get("trust_document_ref")
    if trust_ref:
        # BUG: Does not check beneficiary list
        # BUG: Does not distinguish REV vs IRR
        return "REV"

    # Missing: GOV1, GOV2, GOV3 handling
    # Missing: EBP handling
    # Missing: ANC handling

    return "SGL"
    # NOTE: SGL fallback exists but is not explicitly tested
'''

SAMPLE_CALCULATION_CODE = '''
INSURANCE_LIMIT = 250000

def calculate_insurance(accounts: list[dict]) -> dict:
    """Calculate insured/uninsured for a depositor."""
    total = sum(a["balance"] for a in accounts)
    insured = min(total, INSURANCE_LIMIT)
    uninsured = max(0, total - INSURANCE_LIMIT)
    return {"insured": insured, "uninsured": uninsured}
    # BUG: Does not aggregate by ORC type first
    # BUG: Does not handle per-beneficiary SMDIA for REV
    # BUG: Uses simple sum, not close-of-business balance per 360.8
'''

SAMPLE_DEBT_FLAG_CODE = '''
def set_debt_flag(depositor: dict, loans: list[dict]) -> bool:
    """Set debt flag if depositor has outstanding obligations."""
    for loan in loans:
        if loan["depositor_id"] == depositor["depositor_id"]:
            return True  # BUG: Does not exclude credit card balances
    return False
'''

SAMPLE_PENDING_ROUTING_CODE = '''
def route_to_pending(account: dict) -> tuple[bool, str]:
    """Determine if account should go to Pending File."""
    if not account.get("depositor_id"):
        return True, "LNK"
    if account.get("orc_type") == "REV" and not account.get("beneficiary_ids"):
        return True, "BEN"
    # Missing: RAC for JNT without signature card
    # Missing: GOV for government without collateral
    # Missing: MRG for merger boundary accounts
    return False, ""
'''

SAMPLE_OUTPUT_GENERATION_CODE = '''
def generate_customer_file(customers: list[dict]) -> str:
    """Generate pipe-delimited Customer File."""
    lines = []
    for c in customers:
        # BUG: Name field truncated to 35 chars without documentation
        name = c["name"][:35]
        line = "|".join([c["id"], name, c.get("gov_id", ""), c.get("address", "")])
        lines.append(line)
    return "\\n".join(lines)

def generate_account_file(accounts: list[dict]) -> str:
    """Generate pipe-delimited Account File."""
    lines = []
    for a in accounts:
        line = "|".join([
            a["account_number"],
            a["customer_id"],
            a["account_type"],
            a["orc_type"],
            str(a["balance"]),
            str(a["insured"]),
            str(a["uninsured"]),
        ])
        lines.append(line)
    return "\\n".join(lines)
    # Missing: Account Participant File generation
    # Missing: Pending File generation
    # Missing: Credit Balance Processing File
'''
