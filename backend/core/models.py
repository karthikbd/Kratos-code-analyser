"""
Core Domain Models - FDIC Part 370 / 12 CFR Part 330
=====================================================
All Ownership Right and Capacity (ORC) types, data structures for
deposit accounts, calculation engine outputs, and output file schemas
as defined in:
  - 12 CFR Part 370 (Large-Bank Deposit Insurance Determination)
  - 12 CFR Part 330 (Deposit Insurance Coverage)
  - FDIC IT Functional Guide v3.0 (June 2023)
  - FDIC Compliance Review Manual
"""
from __future__ import annotations

import uuid
from datetime import datetime, date
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ============================================================================
# ORC - Ownership Right and Capacity (11 types per IT Guide Section 4)
# ============================================================================

class ORCType(str, Enum):
    """
    The 11 Ownership Right and Capacity categories defined by the FDIC.
    Each maps to a specific section in 12 CFR Part 330.
    """
    SGL  = "SGL"     # Single Ownership (330.6)
    JNT  = "JNT"     # Joint Ownership (330.9)
    BUS  = "BUS"     # Business/Organization (330.11)
    REV  = "REV"     # Revocable Trust (330.10)
    IRR  = "IRR"     # Irrevocable Trust (330.13)
    CRA  = "CRA"     # Certain Retirement Accounts (330.14a)
    EBP  = "EBP"     # Employee Benefit Plan (330.14)
    ANC  = "ANC"     # Annuity Contract (330.15)
    GOV1 = "GOV1"    # Government - Federal (330.15a)
    GOV2 = "GOV2"    # Government - State/Municipal (330.15b)
    GOV3 = "GOV3"    # Government - Tribal/Other (330.15c)


class PendingReasonCode(str, Enum):
    """Reason codes for accounts routed to the Pending File."""
    RAC = "RAC"      # Joint account awaiting signature card remediation
    BEN = "BEN"      # Missing beneficiary data (REV/IRR)
    ORC = "ORC"      # Cannot determine ORC classification
    DUP = "DUP"      # Suspected duplicate depositor record
    GOV = "GOV"      # Government account missing collateral info
    LNK = "LNK"      # Cannot link to unique depositor ID
    MRG = "MRG"      # Merger boundary calculation required
    TIM = "TIM"      # Calculation exceeds 24-hour window
    DAT = "DAT"      # Insufficient data for calculation
    ARE = "ARE"      # Awaiting Alternative Recordkeeping Entity file


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH     = "HIGH"
    MEDIUM   = "MEDIUM"
    LOW      = "LOW"
    INFO     = "INFO"


class FindingStatus(str, Enum):
    OPEN           = "OPEN"
    IN_REMEDIATION = "IN_REMEDIATION"
    RESOLVED       = "RESOLVED"
    ACCEPTED       = "ACCEPTED"


class AnalyzerLayer(str, Enum):
    """The 7 analyzer layers mirroring the FDIC review structure."""
    LAYER1_ORC_STATIC     = "L1_ORC_STATIC_ANALYSIS"
    LAYER2_DATA_COMPLETE  = "L2_DATA_COMPLETENESS"
    LAYER3_CALC_ENGINE    = "L3_CALCULATION_VERIFICATION"
    LAYER4_OUTPUT_PIPE    = "L4_OUTPUT_FILE_PIPELINE"
    LAYER5_BEHAVIORAL     = "L5_BEHAVIORAL_RUNTIME"
    LAYER6_CERTIFICATION  = "L6_CERTIFICATION_ARTIFACTS"
    LAYER7_DATA_LINEAGE   = "L7_DATA_LINEAGE"


# ============================================================================
# ORC Qualification Rules (from 12 CFR Part 330)
# ============================================================================

class ORCQualificationRule(BaseModel):
    """Defines the regulatory qualification criteria for a single ORC type."""
    orc_type: ORCType
    cfr_section: str                       # e.g. "330.9"
    description: str
    required_fields: list[str]             # Fields that MUST be present
    qualification_conditions: list[str]    # Logic conditions (natural language)
    fallback_orc: ORCType = ORCType.SGL    # Default fallback per regulation
    smdia_per_owner: int = 250_000         # Standard Maximum Deposit Insurance Amount
    requires_beneficiary: bool = False
    requires_signature_card: bool = False
    requires_collateral: bool = False
    special_aggregation: str = ""          # Notes on special aggregation rules


# Pre-built rule definitions from 12 CFR Part 330
ORC_RULES: dict[ORCType, ORCQualificationRule] = {
    ORCType.SGL: ORCQualificationRule(
        orc_type=ORCType.SGL,
        cfr_section="330.6",
        description="Single ownership accounts - deposits owned by one natural person",
        required_fields=["depositor_id", "account_number", "balance", "ownership_category"],
        qualification_conditions=[
            "Owner is a natural person",
            "Account is not held in any fiduciary capacity",
            "Account is not a joint account",
        ],
        smdia_per_owner=250_000,
    ),
    ORCType.JNT: ORCQualificationRule(
        orc_type=ORCType.JNT,
        cfr_section="330.9",
        description="Joint ownership accounts - deposits owned by two or more natural persons",
        required_fields=["depositor_id", "account_number", "balance", "ownership_category",
                         "co_owner_ids", "signature_card_evidence"],
        qualification_conditions=[
            "All co-owners are natural persons",
            "Signature card evidence (or digital equivalent per 2019 amendment) exists",
            "Equal withdrawal rights are confirmed for all co-owners",
        ],
        requires_signature_card=True,
        smdia_per_owner=250_000,
    ),
    ORCType.REV: ORCQualificationRule(
        orc_type=ORCType.REV,
        cfr_section="330.10",
        description="Revocable trust accounts - payable-on-death, living trust, etc.",
        required_fields=["depositor_id", "account_number", "balance", "ownership_category",
                         "beneficiary_ids", "trust_document_ref"],
        qualification_conditions=[
            "Account is a revocable trust deposit",
            "Beneficiary information is on file in the Account Participant File",
            "Number of eligible beneficiaries is determinable",
        ],
        requires_beneficiary=True,
        smdia_per_owner=250_000,
        special_aggregation="Insurance per owner = $250K * number_of_eligible_beneficiaries (up to 5 if > $1.25M)",
    ),
    ORCType.IRR: ORCQualificationRule(
        orc_type=ORCType.IRR,
        cfr_section="330.13",
        description="Irrevocable trust accounts",
        required_fields=["depositor_id", "account_number", "balance", "ownership_category",
                         "beneficiary_ids", "trust_document_ref", "trust_interest_allocation"],
        qualification_conditions=[
            "Trust is irrevocable",
            "Each beneficiary's interest is ascertainable from trust records",
            "Non-contingent interests are identified",
        ],
        requires_beneficiary=True,
        smdia_per_owner=250_000,
    ),
    ORCType.BUS: ORCQualificationRule(
        orc_type=ORCType.BUS,
        cfr_section="330.11",
        description="Business/Organization accounts (corporations, partnerships, LLCs)",
        required_fields=["depositor_id", "account_number", "balance", "ownership_category",
                         "entity_type", "tax_id"],
        qualification_conditions=[
            "Entity is engaged in an independent activity (not sole proprietorship treated as SGL)",
            "Entity has a valid tax ID separate from individual owners",
        ],
    ),
    ORCType.CRA: ORCQualificationRule(
        orc_type=ORCType.CRA,
        cfr_section="330.14a",
        description="Certain Retirement Accounts (IRA, Keogh, 457 plans held by individual)",
        required_fields=["depositor_id", "account_number", "balance", "ownership_category",
                         "retirement_plan_type"],
        qualification_conditions=[
            "Account is an IRA, Keogh, or defined-contribution plan",
            "Held by a natural person (not an employer plan)",
        ],
        smdia_per_owner=250_000,
    ),
    ORCType.EBP: ORCQualificationRule(
        orc_type=ORCType.EBP,
        cfr_section="330.14",
        description="Employee Benefit Plan accounts",
        required_fields=["depositor_id", "account_number", "balance", "ownership_category",
                         "plan_type", "participant_count"],
        qualification_conditions=[
            "Plan is an employee benefit plan as defined under ERISA or equivalent",
            "Plan participant count is determinable",
            "Per-participant allocation is ascertainable",
        ],
        smdia_per_owner=250_000,
        special_aggregation="Pass-through insurance: $250K per plan participant",
    ),
    ORCType.ANC: ORCQualificationRule(
        orc_type=ORCType.ANC,
        cfr_section="330.15",
        description="Annuity contract deposits",
        required_fields=["depositor_id", "account_number", "balance", "ownership_category",
                         "annuity_contract_ref", "insurance_company_id"],
        qualification_conditions=[
            "Deposit is held by an insurance company for annuity obligations",
            "Contract reference is on file",
        ],
    ),
    ORCType.GOV1: ORCQualificationRule(
        orc_type=ORCType.GOV1,
        cfr_section="330.15a",
        description="Federal government deposits",
        required_fields=["depositor_id", "account_number", "balance", "ownership_category",
                         "government_entity_type", "collateral_pledge_ref"],
        qualification_conditions=[
            "Depositor is a federal government entity",
            "Security pledged to the deposit is documented",
        ],
        requires_collateral=True,
        smdia_per_owner=250_000,
    ),
    ORCType.GOV2: ORCQualificationRule(
        orc_type=ORCType.GOV2,
        cfr_section="330.15b",
        description="State and municipal government deposits",
        required_fields=["depositor_id", "account_number", "balance", "ownership_category",
                         "government_entity_type", "collateral_pledge_ref", "official_custodian_name"],
        qualification_conditions=[
            "Depositor is a state, county, or municipal government",
            "Official custodian is identified",
            "Collateral pledge agreement is on record",
        ],
        requires_collateral=True,
        smdia_per_owner=250_000,
    ),
    ORCType.GOV3: ORCQualificationRule(
        orc_type=ORCType.GOV3,
        cfr_section="330.15c",
        description="Tribal and other government deposits",
        required_fields=["depositor_id", "account_number", "balance", "ownership_category",
                         "government_entity_type", "collateral_pledge_ref"],
        qualification_conditions=[
            "Depositor is a tribal or other governmental entity",
            "Collateral documentation exists",
        ],
        requires_collateral=True,
        smdia_per_owner=250_000,
    ),
}


# ============================================================================
# Deposit Account & Participant Structures
# ============================================================================

class DepositAccount(BaseModel):
    """A single deposit account record as it exists in the CI's systems."""
    account_number: str
    depositor_id: str
    balance: float
    orc_type: ORCType
    account_type: str = ""             # checking, savings, CD, money market
    branch_code: str = ""
    open_date: Optional[date] = None
    source_system: str = ""            # Which deposit system this came from
    co_owner_ids: list[str] = Field(default_factory=list)
    beneficiary_ids: list[str] = Field(default_factory=list)
    signature_card_evidence: bool = False
    trust_document_ref: Optional[str] = None
    trust_interest_allocation: Optional[str] = None
    retirement_plan_type: Optional[str] = None
    government_entity_type: Optional[str] = None
    collateral_pledge_ref: Optional[str] = None
    debt_flag: bool = False
    debt_type: Optional[str] = None    # mortgage, HELOC, personal (not credit card)
    entity_type: Optional[str] = None
    tax_id: Optional[str] = None
    plan_type: Optional[str] = None
    participant_count: Optional[int] = None
    annuity_contract_ref: Optional[str] = None
    insurance_company_id: Optional[str] = None
    official_custodian_name: Optional[str] = None
    death_of_owner_date: Optional[date] = None
    acquired_institution_id: Optional[str] = None  # For merger boundary


class AccountParticipant(BaseModel):
    """Account Participant File record - links people to accounts."""
    participant_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    account_number: str
    depositor_id: str
    role: str = "OWNER"                # OWNER, BENEFICIARY, TRUSTEE, CUSTODIAN
    name: str = ""
    government_id: Optional[str] = None
    is_natural_person: bool = True


class CustomerRecord(BaseModel):
    """Customer File record - unique depositor."""
    depositor_id: str
    name: str
    government_id: Optional[str] = None     # SSN / TIN for linking
    address: str = ""
    is_natural_person: bool = True
    date_of_death: Optional[date] = None


# ============================================================================
# Calculation Engine Outputs
# ============================================================================

class InsuranceCalculationResult(BaseModel):
    """Result of the FDIC insurance calculation for one depositor + ORC."""
    depositor_id: str
    orc_type: ORCType
    total_balance: float
    insured_amount: float
    uninsured_amount: float
    smdia_applied: int = 250_000
    account_numbers: list[str] = Field(default_factory=list)
    calculation_timestamp: datetime = Field(default_factory=datetime.utcnow)
    pending: bool = False
    pending_reason: Optional[PendingReasonCode] = None


# ============================================================================
# Output File Schemas (per IT Guide Appendix A)
# ============================================================================

class CustomerFileRecord(BaseModel):
    """One row in the FDIC Customer File (pipe-delimited ASCII)."""
    unique_customer_id: str
    customer_name: str
    government_id: str = ""
    address_line1: str = ""
    address_line2: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""
    country: str = "US"


class AccountFileRecord(BaseModel):
    """One row in the FDIC Account File."""
    account_number: str
    unique_customer_id: str
    account_type: str
    orc_type: str
    balance: float
    insured_amount: float
    uninsured_amount: float
    branch_code: str = ""


class AccountParticipantFileRecord(BaseModel):
    """One row in the FDIC Account Participant File."""
    account_number: str
    participant_id: str
    participant_name: str
    role: str
    government_id: str = ""


class PendingFileRecord(BaseModel):
    """One row in the FDIC Pending File."""
    account_number: str
    unique_customer_id: str
    balance: float
    pending_reason_code: PendingReasonCode
    estimated_resolution: str = ""


# ============================================================================
# Analyzer Finding (output of any layer)
# ============================================================================

class ComplianceFinding(BaseModel):
    """A compliance gap or issue found by any analyzer layer."""
    finding_id: str = Field(default_factory=lambda: f"CF-{uuid.uuid4().hex[:8].upper()}")
    layer: AnalyzerLayer
    severity: Severity
    title: str
    description: str
    cfr_reference: str = ""            # e.g. "12 CFR 370.3(b)"
    it_guide_reference: str = ""       # e.g. "IT Guide Section 4.2"
    orc_type: Optional[ORCType] = None
    affected_accounts: int = 0
    expected_behavior: str = ""
    observed_behavior: str = ""
    remediation_recommendation: str = ""
    evidence: dict[str, Any] = Field(default_factory=dict)
    source_file: str = ""              # e.g. "ORC-ASSIGNMENT.cob"
    line_number: int = 0               # line in source file
    code_snippet: str = ""             # relevant code fragment
    status: FindingStatus = FindingStatus.OPEN
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# Layer Scan Results
# ============================================================================

class LayerScanResult(BaseModel):
    """Result from running one analyzer layer."""
    layer: AnalyzerLayer
    scan_timestamp: datetime = Field(default_factory=datetime.utcnow)
    findings: list[ComplianceFinding] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    passed: bool = True
    summary: str = ""

    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.CRITICAL)

    @property
    def high_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.HIGH)


class FullPipelineResult(BaseModel):
    """Result from running the complete 6-layer pipeline."""
    pipeline_id: str = Field(default_factory=lambda: f"PL-{uuid.uuid4().hex[:8].upper()}")
    institution_name: str = ""
    run_timestamp: datetime = Field(default_factory=datetime.utcnow)
    layer_results: list[LayerScanResult] = Field(default_factory=list)
    total_findings: int = 0
    critical_findings: int = 0
    high_findings: int = 0
    overall_completeness_score: float = 0.0  # 0-100%
    certification_ready: bool = False
    certification_blockers: list[str] = Field(default_factory=list)


# ============================================================================
# Alternative Recordkeeping Entity (ARE) File
# ============================================================================

class AREFileRecord(BaseModel):
    """
    29-field ARE file record (FDIC Addendum format) for brokered deposits
    and sweep accounts where a third party holds beneficial owner records.
    """
    are_submission_id: str
    account_number: str
    beneficial_owner_id: str
    beneficial_owner_name: str
    government_id: str = ""
    orc_type: str = ""
    balance: float = 0.0
    submission_sequence: int = 1       # Supports iterative recalculation
    # Additional fields per Appendix format (simplified)
    address: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""
    is_natural_person: bool = True


# ============================================================================
# Certification Artifacts (Layer 6 output per 12 CFR 370.10(a))
# ============================================================================

class ORCCompletenessScore(BaseModel):
    """Per-ORC completeness score for the certification report."""
    orc_type: ORCType
    total_accounts: int
    calculable_accounts: int
    non_calculable_accounts: int
    completeness_pct: float            # 0-100
    missing_field_summary: dict[str, int] = Field(default_factory=dict)


class CertificationReport(BaseModel):
    """
    Annual certification artifact per 12 CFR 370.10(a).
    Maps to FDIC IT Guide Appendix B format.
    """
    report_id: str = Field(default_factory=lambda: f"CERT-{uuid.uuid4().hex[:8].upper()}")
    institution_name: str
    certification_date: date = Field(default_factory=date.today)
    testing_period_start: date = Field(default_factory=lambda: date.today())
    testing_period_end: date = Field(default_factory=date.today)
    orc_scores: list[ORCCompletenessScore] = Field(default_factory=list)
    overall_completeness: float = 0.0
    total_accounts: int = 0
    total_deposits: float = 0.0
    total_insured: float = 0.0
    total_uninsured: float = 0.0
    non_calculable_count: int = 0
    pending_file_summary: dict[str, int] = Field(default_factory=dict)  # reason_code -> count
    data_quality_exceptions: list[dict[str, Any]] = Field(default_factory=list)
    test_execution_log: list[dict[str, Any]] = Field(default_factory=list)
    remediation_plan: list[dict[str, Any]] = Field(default_factory=list)
    certification_statement: str = ""
    signed_by: str = ""
