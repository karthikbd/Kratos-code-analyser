"""
FDIC Part 370 / Part 330 Control Library
==========================================

Complete enumeration of all compliance controls derived from:
  - 12 CFR Part 370 (Recordkeeping for Timely Deposit Insurance)
  - 12 CFR Part 330 (Deposit Insurance Coverage)
  - 12 CFR 360.8  (Method for Determining Coverage at Failure)
  - FDIC IT Functional Guide v3.0

Each control has:
  - A unique ID (e.g. CTRL-370-3a)
  - Source regulation + section
  - Category
  - Description of the requirement
  - Which analyzer layer validates it
  - Severity if violated
"""
from __future__ import annotations

import re as _re
from enum import Enum
from typing import Optional
from pydantic import BaseModel


class ControlCategory(str, Enum):
    RECORDKEEPING = "Recordkeeping"
    ORC_ASSIGNMENT = "ORC Assignment"
    DATA_QUALITY = "Data Quality"
    CALCULATION = "Calculation Engine"
    OUTPUT_FILES = "Output Files"
    PENDING_MGMT = "Pending Management"
    BEHAVIORAL = "Behavioral / Runtime"
    CERTIFICATION = "Certification"
    ARE_PROCESSING = "ARE Processing"
    INSURANCE_COVERAGE = "Insurance Coverage"
    DATA_LINEAGE = "Data Lineage"


class ControlStatus(str, Enum):
    NOT_TESTED = "not_tested"
    PASS = "pass"
    FAIL = "fail"
    PARTIAL = "partial"
    NOT_APPLICABLE = "not_applicable"


class FDICControl(BaseModel):
    """A single regulatory control from the FDIC Part 370/330 control library."""
    control_id: str
    title: str
    description: str
    regulation: str           # e.g. "12 CFR Part 370"
    section: str             # e.g. "370.3(a)"
    category: ControlCategory
    severity: str            # CRITICAL / HIGH / MEDIUM / LOW
    layer: int               # Which analyzer layer (1-6) validates this
    layer_name: str
    status: ControlStatus = ControlStatus.NOT_TESTED
    rag_validated: bool = False
    rag_citation: str = ""
    finding_ids: list[str] = []


# ═══════════════════════════════════════════════════════════════════════════════
# COMPLETE FDIC PART 370 / PART 330 CONTROL LIBRARY
# ═══════════════════════════════════════════════════════════════════════════════

CONTROL_LIBRARY: list[FDICControl] = [

    # ─── 12 CFR Part 370 – Recordkeeping Requirements ─────────────────────

    FDICControl(
        control_id="CTRL-370-01",
        title="24-Hour Insurance Determination Capability",
        description="IT system must calculate deposit insurance coverage for each depositor by ORC within 24 hours of institution failure.",
        regulation="12 CFR Part 370",
        section="370.1",
        category=ControlCategory.RECORDKEEPING,
        severity="CRITICAL",
        layer=5,
        layer_name="Behavioral Compliance Tester",
    ),
    FDICControl(
        control_id="CTRL-370-02",
        title="Covered Institution Threshold",
        description="Regulation applies to insured depository institutions with 2 million or more deposit accounts.",
        regulation="12 CFR Part 370",
        section="370.2(a)",
        category=ControlCategory.RECORDKEEPING,
        severity="HIGH",
        layer=6,
        layer_name="Certification Generator",
    ),
    FDICControl(
        control_id="CTRL-370-03",
        title="Unique Depositor Identifier",
        description="Each depositor must have a unique identifier in the IT system for aggregation purposes.",
        regulation="12 CFR Part 370",
        section="370.2(f)",
        category=ControlCategory.DATA_QUALITY,
        severity="CRITICAL",
        layer=2,
        layer_name="Data Completeness Validator",
    ),
    FDICControl(
        control_id="CTRL-370-04",
        title="Complete Depositor Data Maintenance",
        description="Maintain complete and accurate data for each depositor including unique identifier, ORC, and balance.",
        regulation="12 CFR Part 370",
        section="370.3(a)",
        category=ControlCategory.DATA_QUALITY,
        severity="CRITICAL",
        layer=2,
        layer_name="Data Completeness Validator",
    ),
    FDICControl(
        control_id="CTRL-370-05",
        title="Daily Data Currency",
        description="All depositor data must be current as of the close of business each day.",
        regulation="12 CFR Part 370",
        section="370.3(b)",
        category=ControlCategory.DATA_QUALITY,
        severity="HIGH",
        layer=2,
        layer_name="Data Completeness Validator",
    ),
    FDICControl(
        control_id="CTRL-370-06",
        title="Balance Aggregation by Depositor and ORC",
        description="IT system must aggregate deposit balances by depositor and ownership right and capacity.",
        regulation="12 CFR Part 370",
        section="370.3(c)(1)",
        category=ControlCategory.CALCULATION,
        severity="CRITICAL",
        layer=3,
        layer_name="Calculation Engine Verifier",
    ),
    FDICControl(
        control_id="CTRL-370-07",
        title="SMDIA Limit Application",
        description="Apply the Standard Maximum Deposit Insurance Amount ($250,000) to each aggregated balance.",
        regulation="12 CFR Part 370",
        section="370.3(c)(2)",
        category=ControlCategory.CALCULATION,
        severity="CRITICAL",
        layer=3,
        layer_name="Calculation Engine Verifier",
    ),
    FDICControl(
        control_id="CTRL-370-08",
        title="FDIC Output File Generation",
        description="Generate output files in the format specified by the FDIC (pipe-delimited ASCII).",
        regulation="12 CFR Part 370",
        section="370.3(c)(3)",
        category=ControlCategory.OUTPUT_FILES,
        severity="CRITICAL",
        layer=4,
        layer_name="Output Pipeline Inspector",
    ),
    FDICControl(
        control_id="CTRL-370-09",
        title="ARE File Processing",
        description="IT system must be capable of processing Additional Record Entity (ARE) files.",
        regulation="12 CFR Part 370",
        section="370.3(c)(4)",
        category=ControlCategory.ARE_PROCESSING,
        severity="CRITICAL",
        layer=4,
        layer_name="Output Pipeline Inspector",
    ),

    # ─── Output Files (370.4) ────────────────────────────────────────────

    FDICControl(
        control_id="CTRL-370-10",
        title="Customer File Generation",
        description="Produce Customer File containing depositor identity information per Appendix A spec.",
        regulation="12 CFR Part 370",
        section="370.4(a)",
        category=ControlCategory.OUTPUT_FILES,
        severity="CRITICAL",
        layer=4,
        layer_name="Output Pipeline Inspector",
    ),
    FDICControl(
        control_id="CTRL-370-11",
        title="Account File Generation",
        description="Produce Account File with account details, ORC classification, and calculated insurance amounts.",
        regulation="12 CFR Part 370",
        section="370.4(b)",
        category=ControlCategory.OUTPUT_FILES,
        severity="CRITICAL",
        layer=4,
        layer_name="Output Pipeline Inspector",
    ),
    FDICControl(
        control_id="CTRL-370-12",
        title="Account Participant File Generation",
        description="Produce Account Participant File with beneficial owner information.",
        regulation="12 CFR Part 370",
        section="370.4(c)",
        category=ControlCategory.OUTPUT_FILES,
        severity="CRITICAL",
        layer=4,
        layer_name="Output Pipeline Inspector",
    ),
    FDICControl(
        control_id="CTRL-370-13",
        title="Pending File Generation",
        description="Produce Pending File for accounts that could not be fully resolved within 24 hours.",
        regulation="12 CFR Part 370",
        section="370.4(d)",
        category=ControlCategory.PENDING_MGMT,
        severity="CRITICAL",
        layer=4,
        layer_name="Output Pipeline Inspector",
    ),
    FDICControl(
        control_id="CTRL-370-14",
        title="Pipe-Delimited ASCII Format",
        description="All output files must be pipe-delimited ASCII text files.",
        regulation="12 CFR Part 370",
        section="370.4",
        category=ControlCategory.OUTPUT_FILES,
        severity="HIGH",
        layer=4,
        layer_name="Output Pipeline Inspector",
    ),

    # ─── Pending Accounts (370.5) ────────────────────────────────────────

    FDICControl(
        control_id="CTRL-370-15",
        title="Pending Account Classification",
        description="Account is pending when insurance coverage cannot be determined within 24 hours.",
        regulation="12 CFR Part 370",
        section="370.5(a)",
        category=ControlCategory.PENDING_MGMT,
        severity="HIGH",
        layer=1,
        layer_name="ORC Static Analyzer",
    ),
    FDICControl(
        control_id="CTRL-370-16",
        title="Pending Reason Code Assignment",
        description="Each pending account must have a valid reason code (RAC, BEN, ORC, DUP, GOV, LNK, MRG, TIM, DAT, ARE).",
        regulation="12 CFR Part 370",
        section="370.5(b)",
        category=ControlCategory.PENDING_MGMT,
        severity="HIGH",
        layer=1,
        layer_name="ORC Static Analyzer",
    ),

    # ─── ARE Processing (370.6) ──────────────────────────────────────────

    FDICControl(
        control_id="CTRL-370-17",
        title="ARE 29-Field Specification",
        description="ARE files must conform to the 29-field specification defined by the FDIC.",
        regulation="12 CFR Part 370",
        section="370.6(b)",
        category=ControlCategory.ARE_PROCESSING,
        severity="HIGH",
        layer=4,
        layer_name="Output Pipeline Inspector",
    ),
    FDICControl(
        control_id="CTRL-370-18",
        title="ARE Idempotent Processing",
        description="ARE file processing must be iterative and idempotent—no duplicate calculations.",
        regulation="12 CFR Part 370",
        section="370.6(c)",
        category=ControlCategory.ARE_PROCESSING,
        severity="HIGH",
        layer=4,
        layer_name="Output Pipeline Inspector",
    ),

    # ─── Testing (370.7) ─────────────────────────────────────────────────

    FDICControl(
        control_id="CTRL-370-19",
        title="Annual IT System Testing",
        description="Covered institutions must conduct annual testing of the IT system.",
        regulation="12 CFR Part 370",
        section="370.7(a)",
        category=ControlCategory.CERTIFICATION,
        severity="CRITICAL",
        layer=6,
        layer_name="Certification Generator",
    ),
    FDICControl(
        control_id="CTRL-370-20",
        title="ORC Logic Verification for All 11 Types",
        description="Testing must verify ORC assignment logic for all 11 ownership right and capacity types.",
        regulation="12 CFR Part 370",
        section="370.7(b)(1)",
        category=ControlCategory.ORC_ASSIGNMENT,
        severity="CRITICAL",
        layer=1,
        layer_name="ORC Static Analyzer",
    ),
    FDICControl(
        control_id="CTRL-370-21",
        title="Insurance Calculation Accuracy",
        description="Testing must verify the accuracy of insurance calculations.",
        regulation="12 CFR Part 370",
        section="370.7(b)(2)",
        category=ControlCategory.CALCULATION,
        severity="CRITICAL",
        layer=3,
        layer_name="Calculation Engine Verifier",
    ),
    FDICControl(
        control_id="CTRL-370-22",
        title="Output File Completeness Testing",
        description="Testing must verify completeness of all four output files.",
        regulation="12 CFR Part 370",
        section="370.7(b)(3)",
        category=ControlCategory.OUTPUT_FILES,
        severity="HIGH",
        layer=4,
        layer_name="Output Pipeline Inspector",
    ),
    FDICControl(
        control_id="CTRL-370-23",
        title="ARE Processing Testing",
        description="Testing must include verification of ARE file processing.",
        regulation="12 CFR Part 370",
        section="370.7(b)(4)",
        category=ControlCategory.ARE_PROCESSING,
        severity="HIGH",
        layer=4,
        layer_name="Output Pipeline Inspector",
    ),
    FDICControl(
        control_id="CTRL-370-24",
        title="24-Hour Completion Testing",
        description="Testing must verify the system can complete processing within 24 hours.",
        regulation="12 CFR Part 370",
        section="370.7(b)(5)",
        category=ControlCategory.BEHAVIORAL,
        severity="CRITICAL",
        layer=5,
        layer_name="Behavioral Compliance Tester",
    ),

    # ─── Interest / Debt (370.8, 370.9) ──────────────────────────────────

    FDICControl(
        control_id="CTRL-370-25",
        title="Interest Accrual Through Failure Date",
        description="Interest must be calculated through close of business on the day of failure per 12 CFR 360.8.",
        regulation="12 CFR Part 370",
        section="370.8",
        category=ControlCategory.CALCULATION,
        severity="CRITICAL",
        layer=3,
        layer_name="Calculation Engine Verifier",
    ),
    FDICControl(
        control_id="CTRL-370-26",
        title="Debt Offset Identification",
        description="Outstanding debts owed by depositors must be identified for offset.",
        regulation="12 CFR Part 370",
        section="370.9(a)",
        category=ControlCategory.CALCULATION,
        severity="HIGH",
        layer=3,
        layer_name="Calculation Engine Verifier",
    ),
    FDICControl(
        control_id="CTRL-370-27",
        title="Credit Card Exclusion from Offset",
        description="Credit card balances must be excluded from debt offset calculations.",
        regulation="12 CFR Part 370",
        section="370.9(b)",
        category=ControlCategory.CALCULATION,
        severity="HIGH",
        layer=3,
        layer_name="Calculation Engine Verifier",
    ),
    FDICControl(
        control_id="CTRL-370-28",
        title="Post-Aggregation Offset Application",
        description="Offset amounts must be applied after aggregation by depositor and ORC.",
        regulation="12 CFR Part 370",
        section="370.9(c)",
        category=ControlCategory.CALCULATION,
        severity="HIGH",
        layer=3,
        layer_name="Calculation Engine Verifier",
    ),

    # ─── Certification (370.10) ──────────────────────────────────────────

    FDICControl(
        control_id="CTRL-370-29",
        title="Annual Board Certification",
        description="Board of directors must certify annually that institution complies with Part 370.",
        regulation="12 CFR Part 370",
        section="370.10(a)",
        category=ControlCategory.CERTIFICATION,
        severity="CRITICAL",
        layer=6,
        layer_name="Certification Generator",
    ),
    FDICControl(
        control_id="CTRL-370-30",
        title="Certification Filing Deadline",
        description="Certification must be filed with FDIC within 10 business days after calendar year end.",
        regulation="12 CFR Part 370",
        section="370.10(b)",
        category=ControlCategory.CERTIFICATION,
        severity="HIGH",
        layer=6,
        layer_name="Certification Generator",
    ),
    FDICControl(
        control_id="CTRL-370-31",
        title="IT System Output Capability Confirmation",
        description="Certification must confirm IT system can produce required output files.",
        regulation="12 CFR Part 370",
        section="370.10(c)(1)",
        category=ControlCategory.CERTIFICATION,
        severity="HIGH",
        layer=6,
        layer_name="Certification Generator",
    ),
    FDICControl(
        control_id="CTRL-370-32",
        title="Annual Test Results Inclusion",
        description="Certification must include results of annual testing.",
        regulation="12 CFR Part 370",
        section="370.10(c)(2)",
        category=ControlCategory.CERTIFICATION,
        severity="HIGH",
        layer=6,
        layer_name="Certification Generator",
    ),
    FDICControl(
        control_id="CTRL-370-33",
        title="Deficiency Identification and Remediation",
        description="Certification must include identified deficiencies and remediation plans.",
        regulation="12 CFR Part 370",
        section="370.10(c)(3)",
        category=ControlCategory.CERTIFICATION,
        severity="MEDIUM",
        layer=6,
        layer_name="Certification Generator",
    ),

    # ─── Record Retention (370.11) ───────────────────────────────────────

    FDICControl(
        control_id="CTRL-370-34",
        title="5-Year Record Retention",
        description="All records must be maintained for 5 years from date of creation.",
        regulation="12 CFR Part 370",
        section="370.11",
        category=ControlCategory.RECORDKEEPING,
        severity="MEDIUM",
        layer=6,
        layer_name="Certification Generator",
    ),

    # ─── Appendix A – Output File Specs ──────────────────────────────────

    FDICControl(
        control_id="CTRL-370-35",
        title="Customer File Field Completeness",
        description="Customer File must contain: customer_id, first_name, last_name, ssn_tin, dob, address, city, state, zip, phone, email, customer_type.",
        regulation="12 CFR Part 370",
        section="Appendix A",
        category=ControlCategory.OUTPUT_FILES,
        severity="HIGH",
        layer=4,
        layer_name="Output Pipeline Inspector",
    ),
    FDICControl(
        control_id="CTRL-370-36",
        title="Account File Field Completeness",
        description="Account File must contain: account_id, customer_id, account_type, orc_type, balance, insured_amount, uninsured_amount, institution_id.",
        regulation="12 CFR Part 370",
        section="Appendix A",
        category=ControlCategory.OUTPUT_FILES,
        severity="HIGH",
        layer=4,
        layer_name="Output Pipeline Inspector",
    ),
    FDICControl(
        control_id="CTRL-370-37",
        title="Participant File Field Completeness",
        description="Participant File must contain: account_id, participant_id, participant_type, ownership_share.",
        regulation="12 CFR Part 370",
        section="Appendix A",
        category=ControlCategory.OUTPUT_FILES,
        severity="HIGH",
        layer=4,
        layer_name="Output Pipeline Inspector",
    ),
    FDICControl(
        control_id="CTRL-370-38",
        title="Pending File Field Completeness",
        description="Pending File must contain: account_id, pending_reason_code, pending_description.",
        regulation="12 CFR Part 370",
        section="Appendix A",
        category=ControlCategory.PENDING_MGMT,
        severity="HIGH",
        layer=4,
        layer_name="Output Pipeline Inspector",
    ),

    # ─── Appendix B – Certification Format ───────────────────────────────

    FDICControl(
        control_id="CTRL-370-39",
        title="Per-ORC Completeness Scores",
        description="Certification report must include completeness scores for each of the 11 ORC types.",
        regulation="12 CFR Part 370",
        section="Appendix B(1)",
        category=ControlCategory.CERTIFICATION,
        severity="HIGH",
        layer=6,
        layer_name="Certification Generator",
    ),
    FDICControl(
        control_id="CTRL-370-40",
        title="Pending File Summary by Reason Code",
        description="Certification report must include pending file summary broken down by reason code.",
        regulation="12 CFR Part 370",
        section="Appendix B(2)",
        category=ControlCategory.CERTIFICATION,
        severity="MEDIUM",
        layer=6,
        layer_name="Certification Generator",
    ),
    FDICControl(
        control_id="CTRL-370-41",
        title="Data Quality Exception Log",
        description="Certification report must include data quality exception log with root causes.",
        regulation="12 CFR Part 370",
        section="Appendix B(3)",
        category=ControlCategory.CERTIFICATION,
        severity="MEDIUM",
        layer=6,
        layer_name="Certification Generator",
    ),

    # ═══════════════════════════════════════════════════════════════════════
    # 12 CFR Part 330 – Deposit Insurance Coverage Controls
    # ═══════════════════════════════════════════════════════════════════════

    # ─── General Principles (330.1–330.5) ────────────────────────────────

    FDICControl(
        control_id="CTRL-330-01",
        title="ORC-Based Insurance Determination",
        description="Insurance coverage is determined based on depositor's ownership right and capacity.",
        regulation="12 CFR Part 330",
        section="330.3(a)",
        category=ControlCategory.INSURANCE_COVERAGE,
        severity="CRITICAL",
        layer=1,
        layer_name="ORC Static Analyzer",
    ),
    FDICControl(
        control_id="CTRL-330-02",
        title="SMDIA per Depositor per ORC",
        description="SMDIA of $250,000 applies per depositor, per institution, per ownership category.",
        regulation="12 CFR Part 330",
        section="330.3(b)",
        category=ControlCategory.INSURANCE_COVERAGE,
        severity="CRITICAL",
        layer=3,
        layer_name="Calculation Engine Verifier",
    ),
    FDICControl(
        control_id="CTRL-330-03",
        title="Separate Insurance per ORC Category",
        description="Funds in different ownership categories are insured separately.",
        regulation="12 CFR Part 330",
        section="330.3(c)",
        category=ControlCategory.CALCULATION,
        severity="CRITICAL",
        layer=3,
        layer_name="Calculation Engine Verifier",
    ),
    FDICControl(
        control_id="CTRL-330-04",
        title="Deposit Ownership Recognition",
        description="FDIC presumes deposits belong to named owner unless records indicate otherwise.",
        regulation="12 CFR Part 330",
        section="330.5(a)",
        category=ControlCategory.RECORDKEEPING,
        severity="HIGH",
        layer=2,
        layer_name="Data Completeness Validator",
    ),

    # ─── SGL – Single Ownership (330.6) ──────────────────────────────────

    FDICControl(
        control_id="CTRL-330-05",
        title="SGL: Single Ownership Aggregation",
        description="All deposits owned by a single person in their own right are aggregated and insured up to SMDIA.",
        regulation="12 CFR Part 330",
        section="330.6(a)",
        category=ControlCategory.ORC_ASSIGNMENT,
        severity="CRITICAL",
        layer=1,
        layer_name="ORC Static Analyzer",
    ),
    FDICControl(
        control_id="CTRL-330-06",
        title="SGL: Default Fallback ORC",
        description="If ORC cannot be determined, default to Single Ownership (SGL).",
        regulation="12 CFR Part 330",
        section="330.6(b)",
        category=ControlCategory.ORC_ASSIGNMENT,
        severity="HIGH",
        layer=1,
        layer_name="ORC Static Analyzer",
    ),

    # ─── JNT – Joint Ownership (330.7/330.9) ────────────────────────────

    FDICControl(
        control_id="CTRL-330-07",
        title="JNT: Co-Owner Interest Aggregation",
        description="Each co-owner's interest in all joint accounts is aggregated and insured up to SMDIA.",
        regulation="12 CFR Part 330",
        section="330.9(a)",
        category=ControlCategory.ORC_ASSIGNMENT,
        severity="CRITICAL",
        layer=1,
        layer_name="ORC Static Analyzer",
    ),
    FDICControl(
        control_id="CTRL-330-08",
        title="JNT: Natural Person Requirement",
        description="Each co-owner of a joint account must be a natural person.",
        regulation="12 CFR Part 330",
        section="330.9(b)(1)",
        category=ControlCategory.ORC_ASSIGNMENT,
        severity="HIGH",
        layer=1,
        layer_name="ORC Static Analyzer",
    ),
    FDICControl(
        control_id="CTRL-330-09",
        title="JNT: Signature Card Requirement",
        description="Each co-owner must have personally signed a deposit account signature card.",
        regulation="12 CFR Part 330",
        section="330.9(b)(2)",
        category=ControlCategory.ORC_ASSIGNMENT,
        severity="HIGH",
        layer=1,
        layer_name="ORC Static Analyzer",
    ),
    FDICControl(
        control_id="CTRL-330-10",
        title="JNT: Equal Withdrawal Rights",
        description="All co-owners must have equal withdrawal rights.",
        regulation="12 CFR Part 330",
        section="330.9(b)(3)",
        category=ControlCategory.ORC_ASSIGNMENT,
        severity="HIGH",
        layer=1,
        layer_name="ORC Static Analyzer",
    ),
    FDICControl(
        control_id="CTRL-330-11",
        title="JNT: Death-of-Owner Temporal Logic",
        description="Upon death of co-owner, deceased's share treated as SGL for 6 months per 360.8.",
        regulation="12 CFR 360.8",
        section="330.9 / 360.8",
        category=ControlCategory.CALCULATION,
        severity="CRITICAL",
        layer=3,
        layer_name="Calculation Engine Verifier",
    ),

    # ─── REV – Revocable Trust (330.10) ──────────────────────────────────

    FDICControl(
        control_id="CTRL-330-12",
        title="REV: Per-Beneficiary Coverage",
        description="Revocable trust coverage is $250,000 per qualifying beneficiary.",
        regulation="12 CFR Part 330",
        section="330.10(a)",
        category=ControlCategory.ORC_ASSIGNMENT,
        severity="CRITICAL",
        layer=1,
        layer_name="ORC Static Analyzer",
    ),
    FDICControl(
        control_id="CTRL-330-13",
        title="REV: Beneficiary Identification",
        description="The owner must identify all beneficiaries of the revocable trust.",
        regulation="12 CFR Part 330",
        section="330.10(b)",
        category=ControlCategory.DATA_QUALITY,
        severity="HIGH",
        layer=2,
        layer_name="Data Completeness Validator",
    ),
    FDICControl(
        control_id="CTRL-330-14",
        title="REV: Trust Documentation",
        description="Valid trust documentation must be on file for revocable trust accounts.",
        regulation="12 CFR Part 330",
        section="330.10(c)",
        category=ControlCategory.DATA_QUALITY,
        severity="HIGH",
        layer=2,
        layer_name="Data Completeness Validator",
    ),

    # ─── IRR – Irrevocable Trust (330.13) ────────────────────────────────

    FDICControl(
        control_id="CTRL-330-15",
        title="IRR: Non-Contingent Beneficiary Coverage",
        description="Irrevocable trust coverage is $250,000 per non-contingent ascertainable beneficiary.",
        regulation="12 CFR Part 330",
        section="330.13(a)",
        category=ControlCategory.ORC_ASSIGNMENT,
        severity="CRITICAL",
        layer=1,
        layer_name="ORC Static Analyzer",
    ),
    FDICControl(
        control_id="CTRL-330-16",
        title="IRR: Trust Instrument Requirements",
        description="The trust must be irrevocable with clearly defined beneficiary interests.",
        regulation="12 CFR Part 330",
        section="330.13(b)",
        category=ControlCategory.DATA_QUALITY,
        severity="HIGH",
        layer=2,
        layer_name="Data Completeness Validator",
    ),

    # ─── BUS – Business/Organization (330.11) ───────────────────────────

    FDICControl(
        control_id="CTRL-330-17",
        title="BUS: Business Entity Coverage",
        description="Deposits owned by a corporation, partnership, or unincorporated association insured up to $250,000.",
        regulation="12 CFR Part 330",
        section="330.11(a)",
        category=ControlCategory.ORC_ASSIGNMENT,
        severity="HIGH",
        layer=1,
        layer_name="ORC Static Analyzer",
    ),
    FDICControl(
        control_id="CTRL-330-18",
        title="BUS: Entity Identification Fields",
        description="Business accounts require EIN/TIN, entity type, and authorized signers.",
        regulation="12 CFR Part 330",
        section="330.11",
        category=ControlCategory.DATA_QUALITY,
        severity="HIGH",
        layer=2,
        layer_name="Data Completeness Validator",
    ),

    # ─── CRA – Certain Retirement Accounts (330.12/330.14a) ─────────────

    FDICControl(
        control_id="CTRL-330-19",
        title="CRA: Retirement Account Coverage",
        description="IRAs, Keogh plans, and certain retirement accounts insured up to $250,000 per depositor.",
        regulation="12 CFR Part 330",
        section="330.14(a)",
        category=ControlCategory.ORC_ASSIGNMENT,
        severity="HIGH",
        layer=1,
        layer_name="ORC Static Analyzer",
    ),
    FDICControl(
        control_id="CTRL-330-20",
        title="CRA: Required Data Fields",
        description="Retirement accounts require retirement_account_type and plan_administrator.",
        regulation="12 CFR Part 330",
        section="330.14(a)",
        category=ControlCategory.DATA_QUALITY,
        severity="MEDIUM",
        layer=2,
        layer_name="Data Completeness Validator",
    ),

    # ─── EBP – Employee Benefit Plan (330.14) ───────────────────────────

    FDICControl(
        control_id="CTRL-330-21",
        title="EBP: Per-Participant Coverage",
        description="Employee benefit plan coverage is $250,000 per plan participant.",
        regulation="12 CFR Part 330",
        section="330.14(b)",
        category=ControlCategory.ORC_ASSIGNMENT,
        severity="HIGH",
        layer=1,
        layer_name="ORC Static Analyzer",
    ),
    FDICControl(
        control_id="CTRL-330-22",
        title="EBP: Required Data Fields",
        description="EBP accounts require plan_participants, plan_type, and employer_ein.",
        regulation="12 CFR Part 330",
        section="330.14",
        category=ControlCategory.DATA_QUALITY,
        severity="MEDIUM",
        layer=2,
        layer_name="Data Completeness Validator",
    ),

    # ─── GOV – Government Accounts (330.15) ─────────────────────────────

    FDICControl(
        control_id="CTRL-330-23",
        title="GOV1: Federal Government Full Insurance",
        description="Federal government deposits are fully insured without limit via U.S. government guarantee.",
        regulation="12 CFR Part 330",
        section="330.15(a)",
        category=ControlCategory.ORC_ASSIGNMENT,
        severity="HIGH",
        layer=1,
        layer_name="ORC Static Analyzer",
    ),
    FDICControl(
        control_id="CTRL-330-24",
        title="GOV2: State/Municipal Collateral Requirement",
        description="State and municipal deposits insured if collateralized per state law. Requires collateral_amount, collateral_documentation, pledging_institution.",
        regulation="12 CFR Part 330",
        section="330.15(b)",
        category=ControlCategory.ORC_ASSIGNMENT,
        severity="CRITICAL",
        layer=1,
        layer_name="ORC Static Analyzer",
    ),
    FDICControl(
        control_id="CTRL-330-25",
        title="GOV3: Tribal/Other Government Coverage",
        description="Tribal and other government deposits follow specific FDIC guidance for coverage.",
        regulation="12 CFR Part 330",
        section="330.15(c)",
        category=ControlCategory.ORC_ASSIGNMENT,
        severity="HIGH",
        layer=1,
        layer_name="ORC Static Analyzer",
    ),
    FDICControl(
        control_id="CTRL-330-26",
        title="GOV: Government Collateral Data Completeness",
        description="Government accounts must have collateral documentation for non-federal entities.",
        regulation="12 CFR Part 330",
        section="330.15(b)",
        category=ControlCategory.DATA_QUALITY,
        severity="CRITICAL",
        layer=2,
        layer_name="Data Completeness Validator",
    ),

    # ─── ANC – Annuity Contracts (330.15) ────────────────────────────────

    FDICControl(
        control_id="CTRL-330-27",
        title="ANC: Annuity Contract Coverage",
        description="Annuity contract deposits follow FDIC coverage rules under Part 330.15.",
        regulation="12 CFR Part 330",
        section="330.15",
        category=ControlCategory.ORC_ASSIGNMENT,
        severity="MEDIUM",
        layer=1,
        layer_name="ORC Static Analyzer",
    ),

    # ═══════════════════════════════════════════════════════════════════════
    # FDIC IT Functional Guide Controls
    # ═══════════════════════════════════════════════════════════════════════

    FDICControl(
        control_id="CTRL-ITG-01",
        title="ORC Decision Tree Completeness",
        description="ORC assignment logic must cover all 11 ORC types with proper decision tree per IT Guide Section 4.",
        regulation="FDIC IT Guide v3.0",
        section="Section 4",
        category=ControlCategory.ORC_ASSIGNMENT,
        severity="CRITICAL",
        layer=1,
        layer_name="ORC Static Analyzer",
    ),
    FDICControl(
        control_id="CTRL-ITG-02",
        title="ORC Fallback/Default Logic",
        description="System must have explicit fallback logic when ORC cannot be determined.",
        regulation="FDIC IT Guide v3.0",
        section="Section 4",
        category=ControlCategory.ORC_ASSIGNMENT,
        severity="HIGH",
        layer=1,
        layer_name="ORC Static Analyzer",
    ),
    FDICControl(
        control_id="CTRL-ITG-03",
        title="Data Completeness per ORC-Conditional Fields",
        description="All ORC-conditional required fields must be populated per IT Guide Sections 2.3.2-2.3.3.",
        regulation="FDIC IT Guide v3.0",
        section="Section 2.3.2-2.3.3",
        category=ControlCategory.DATA_QUALITY,
        severity="HIGH",
        layer=2,
        layer_name="Data Completeness Validator",
    ),
    FDICControl(
        control_id="CTRL-ITG-04",
        title="Orphan Account Detection",
        description="Accounts without matching customer records must be identified and flagged.",
        regulation="FDIC IT Guide v3.0",
        section="Section 2.3.3",
        category=ControlCategory.DATA_QUALITY,
        severity="CRITICAL",
        layer=2,
        layer_name="Data Completeness Validator",
    ),
    FDICControl(
        control_id="CTRL-ITG-05",
        title="Orphan Participant Detection",
        description="Account participants without matching account records must be identified.",
        regulation="FDIC IT Guide v3.0",
        section="Section 2.3.3",
        category=ControlCategory.DATA_QUALITY,
        severity="HIGH",
        layer=2,
        layer_name="Data Completeness Validator",
    ),
    FDICControl(
        control_id="CTRL-ITG-06",
        title="Merger Boundary Data Integrity",
        description="Post-merger data must maintain separate deposit tracking per IT Guide.",
        regulation="FDIC IT Guide v3.0",
        section="Section 2.3.3",
        category=ControlCategory.DATA_QUALITY,
        severity="HIGH",
        layer=2,
        layer_name="Data Completeness Validator",
    ),
    FDICControl(
        control_id="CTRL-ITG-07",
        title="Output File Data Lineage",
        description="Each output file record must trace back to source deposit data with full lineage.",
        regulation="FDIC IT Guide v3.0",
        section="Section 5",
        category=ControlCategory.OUTPUT_FILES,
        severity="HIGH",
        layer=4,
        layer_name="Output Pipeline Inspector",
    ),
    FDICControl(
        control_id="CTRL-ITG-08",
        title="Credit/Negative Balance Processing",
        description="Credit balances and negative balances must be handled per IT Guide Section 5.",
        regulation="FDIC IT Guide v3.0",
        section="Section 5",
        category=ControlCategory.OUTPUT_FILES,
        severity="MEDIUM",
        layer=4,
        layer_name="Output Pipeline Inspector",
    ),
    FDICControl(
        control_id="CTRL-ITG-09",
        title="Account Restriction Speed",
        description="System must restrict/freeze accounts within acceptable time limits.",
        regulation="FDIC IT Guide v3.0",
        section="Section 4.5",
        category=ControlCategory.BEHAVIORAL,
        severity="HIGH",
        layer=5,
        layer_name="Behavioral Compliance Tester",
    ),
    FDICControl(
        control_id="CTRL-ITG-10",
        title="Failover/DR Capability",
        description="System must have failover and disaster recovery capability for compliance processing.",
        regulation="FDIC IT Guide v3.0",
        section="Section 6",
        category=ControlCategory.BEHAVIORAL,
        severity="HIGH",
        layer=5,
        layer_name="Behavioral Compliance Tester",
    ),
    FDICControl(
        control_id="CTRL-ITG-11",
        title="ARE Recalculation Throughput",
        description="System must handle iterative ARE recalculations within time limits.",
        regulation="FDIC IT Guide v3.0",
        section="Section 5.3",
        category=ControlCategory.BEHAVIORAL,
        severity="MEDIUM",
        layer=5,
        layer_name="Behavioral Compliance Tester",
    ),

    # ── Layer 7: Data Lineage & Back-Traceability ─────────────────────────
    FDICControl(
        control_id="CTRL-LIN-01",
        title="Source System Identification",
        description="All upstream source systems feeding depositor/account data must be explicitly identified, documented, and mapped in the processing chain.",
        regulation="12 CFR Part 370",
        section="370.3(b)",
        category=ControlCategory.DATA_LINEAGE,
        severity="CRITICAL",
        layer=7,
        layer_name="Data Lineage Tracer",
    ),
    FDICControl(
        control_id="CTRL-LIN-02",
        title="Field-Level Lineage Completeness",
        description="Every critical data field (SSN/TIN, balance, ORC, beneficiary data) must be traceable from source system extraction through transformation to output file generation.",
        regulation="FDIC IT Guide v3.0",
        section="Section 2.3",
        category=ControlCategory.DATA_LINEAGE,
        severity="CRITICAL",
        layer=7,
        layer_name="Data Lineage Tracer",
    ),
    FDICControl(
        control_id="CTRL-LIN-03",
        title="ETL Transformation Chain Integrity",
        description="The Extract-Transform-Load chain must be complete with documented extract, transform, and load phases for all depositor data.",
        regulation="FDIC IT Guide v3.0",
        section="Section 5.1",
        category=ControlCategory.DATA_LINEAGE,
        severity="HIGH",
        layer=7,
        layer_name="Data Lineage Tracer",
    ),
    FDICControl(
        control_id="CTRL-LIN-04",
        title="Audit Trail at Each Processing Stage",
        description="Every data transformation must maintain a complete audit trail including timestamps, source identification, record counts, checksums, and exception logs.",
        regulation="12 CFR Part 370",
        section="370.10(a)",
        category=ControlCategory.DATA_LINEAGE,
        severity="CRITICAL",
        layer=7,
        layer_name="Data Lineage Tracer",
    ),
    FDICControl(
        control_id="CTRL-LIN-05",
        title="Cross-System Balance Reconciliation",
        description="Aggregate deposit balances must reconcile between source extraction, transformation, and output generation stages within defined tolerance thresholds.",
        regulation="FDIC IT Guide v3.0",
        section="Section 5.4",
        category=ControlCategory.DATA_LINEAGE,
        severity="CRITICAL",
        layer=7,
        layer_name="Data Lineage Tracer",
    ),
    FDICControl(
        control_id="CTRL-LIN-06",
        title="Record Count Reconciliation",
        description="Record counts must match between processing stages; any discrepancy must be logged and investigated before output generation.",
        regulation="FDIC IT Guide v3.0",
        section="Section 5.4",
        category=ControlCategory.DATA_LINEAGE,
        severity="HIGH",
        layer=7,
        layer_name="Data Lineage Tracer",
    ),
    FDICControl(
        control_id="CTRL-LIN-07",
        title="ORC-Specific Data Lineage",
        description="Each of the 11 ORC types must have its specific data requirements (beneficiary data for REV/IRR, signature cards for JNT, collateral for GOV) traced from source to output.",
        regulation="12 CFR Part 330",
        section="Sections 330.6-330.15",
        category=ControlCategory.DATA_LINEAGE,
        severity="CRITICAL",
        layer=7,
        layer_name="Data Lineage Tracer",
    ),
    FDICControl(
        control_id="CTRL-LIN-08",
        title="Silent Data Drop Detection",
        description="Any filtering operation that excludes depositor records from insurance calculation must be documented and excluded records must be routed to the Pending File.",
        regulation="FDIC IT Guide v3.0",
        section="Section 5.2",
        category=ControlCategory.DATA_LINEAGE,
        severity="HIGH",
        layer=7,
        layer_name="Data Lineage Tracer",
    ),
    FDICControl(
        control_id="CTRL-LIN-09",
        title="Data Flow Documentation",
        description="Data flows between source systems and the deposit insurance calculation system must be documented including field mappings, transformation rules, and system interfaces.",
        regulation="FDIC IT Guide v3.0",
        section="Section 2.1",
        category=ControlCategory.DATA_LINEAGE,
        severity="MEDIUM",
        layer=7,
        layer_name="Data Lineage Tracer",
    ),
    FDICControl(
        control_id="CTRL-LIN-10",
        title="Dead-End Data Path Prevention",
        description="All data stores written to during processing must have downstream consumers. Orphan data paths indicate processing gaps or abandoned code paths.",
        regulation="FDIC IT Guide v3.0",
        section="Section 5.1",
        category=ControlCategory.DATA_LINEAGE,
        severity="MEDIUM",
        layer=7,
        layer_name="Data Lineage Tracer",
    ),
    FDICControl(
        control_id="CTRL-LIN-11",
        title="Hardcoded Path Externalization",
        description="Data source paths must be externalized to configuration. Hardcoded paths create brittle lineage that can silently break during migration or DR failover.",
        regulation="12 CFR Part 370",
        section="370.3(b)",
        category=ControlCategory.DATA_LINEAGE,
        severity="HIGH",
        layer=7,
        layer_name="Data Lineage Tracer",
    ),
]


def get_controls_by_layer(layer: int) -> list[FDICControl]:
    """Get all controls validated by a specific layer."""
    return [c for c in CONTROL_LIBRARY if c.layer == layer]


def get_controls_by_category(category: ControlCategory) -> list[FDICControl]:
    """Get all controls in a specific category."""
    return [c for c in CONTROL_LIBRARY if c.category == category]


def get_control_summary() -> dict:
    """Get summary statistics of the control library."""
    by_regulation = {}
    by_category = {}
    by_severity = {}
    by_layer = {}

    for c in CONTROL_LIBRARY:
        by_regulation[c.regulation] = by_regulation.get(c.regulation, 0) + 1
        by_category[c.category.value] = by_category.get(c.category.value, 0) + 1
        by_severity[c.severity] = by_severity.get(c.severity, 0) + 1
        by_layer[c.layer] = by_layer.get(c.layer, 0) + 1

    return {
        "total_controls": len(CONTROL_LIBRARY),
        "by_regulation": by_regulation,
        "by_category": by_category,
        "by_severity": by_severity,
        "by_layer": {f"Layer {k}": v for k, v in sorted(by_layer.items())},
    }


# ═══════════════════════════════════════════════════════════════════════════════
# DYNAMIC CONTROL APPLICABILITY
# Scans operational-system source code to detect which ORC types and features
# are present, then determines which controls are applicable to that system.
# ═══════════════════════════════════════════════════════════════════════════════

# Regex patterns to detect ORC ownership types in source code
_ORC_DETECT_PATTERNS: dict[str, list[str]] = {
    "SGL": [r"\bSGL\b", r"SINGLE.?OWNER", r"SINGLE.?OWNERSHIP"],
    "JNT": [r"\bJNT\b", r"JOINT", r"CO.?OWNER"],
    "REV": [r"\bREV\b", r"REVOCABLE", r"TRUST.*BENEFICIAR"],
    "IRR": [r"\bIRR\b", r"IRREVOCABLE"],
    "BUS": [r"\bBUS\b", r"BUSINESS", r"CORPORAT"],
    "CRA": [r"\bCRA\b", r"RETIREMENT", r"\bIRA\b", r"KEOGH"],
    "EBP": [r"\bEBP\b", r"EMPLOYEE.?BENEFIT", r"PLAN.?PARTICIPANT"],
    "GOV": [r"\bGOV\b", r"GOVERNMENT", r"FEDERAL", r"MUNICIPAL", r"TRIBAL"],
    "ANC": [r"\bANC\b", r"ANNUITY"],
}

# Regex patterns to detect compliance features in source code
_FEATURE_DETECT_PATTERNS: dict[str, list[str]] = {
    "OUTPUT_FILES": [
        r"OUTPUT.?FILE", r"PIPE.?DELIMIT", r"QDF",
        r"CUSTOMER.?FILE", r"ACCOUNT.?FILE", r"WRITE.*FILE",
    ],
    "PENDING": [r"PENDING", r"REASON.?CODE", r"UNRESOL"],
    "ARE": [r"\bARE\b.*(?:FILE|RECORD|PROCESS)", r"ADDITIONAL.?RECORD"],
    "CALCULATION": [
        r"INSURANCE.*CALC|CALC.*INSURANCE", r"SMDIA",
        r"250.?000", r"INSURED.?AMOUNT", r"AGGREGAT",
    ],
    "DEBT_OFFSET": [r"DEBT.?OFFSET", r"OFFSET.?AMOUNT"],
    "BENEFICIARY": [r"BENEFICIAR"],
    "TRUST": [r"TRUST", r"GRANTOR"],
}

# Always-applicable control categories — apply regardless of system code
_ALWAYS_APPLICABLE_CATEGORIES: set[ControlCategory] = {
    ControlCategory.RECORDKEEPING,
    ControlCategory.BEHAVIORAL,
    ControlCategory.CERTIFICATION,
    ControlCategory.DATA_LINEAGE,
    ControlCategory.INSURANCE_COVERAGE,
    ControlCategory.DATA_QUALITY,
}


def _control_required_orcs(section: str) -> set[str] | None:
    """Return ORC types required for a control's section, or None if not ORC-specific."""
    if section.startswith("330.6"):
        return {"SGL"}
    if section.startswith("330.9") or "360.8" in section:
        return {"JNT"}
    if section.startswith("330.10"):
        return {"REV"}
    if section.startswith("330.13"):
        return {"IRR"}
    if section.startswith("330.11"):
        return {"BUS"}
    if section.startswith("330.14(a)"):
        return {"CRA"}
    if section.startswith("330.14(b)") or section == "330.14":
        return {"EBP"}
    if section.startswith("330.15(a)") or section.startswith("330.15(b)") or section.startswith("330.15(c)"):
        return {"GOV"}
    if section == "330.15":
        return {"GOV", "ANC"}
    return None


def detect_system_capabilities(source_contents: dict[str, str]) -> dict:
    """
    Scan an operational system's source code to detect ORC types and features.

    Detection uses a 3-tier priority cascade:
      1. Explicit config  — parse `insurance.orc_types.supported=SGL,JNT,...` from
                           .properties / .yaml / .yml files; if found, use as
                           authoritative ORC list.
      2. CSV exclusions   — scan orc-mapping CSV files; any ORC with status
                           NOT_IMPLEMENTED is excluded from the detected set.
      3. Code scan        — scan source code files (.java, .py, .sql, .cob, .jcl,
                           .sh, .cobol, .xml, .yaml) for ORC references, but skip
                           lines that contain a NOT_IMPLEMENTED marker next to the
                           ORC code, and skip pure reference/data files (.csv, .md,
                           .txt, .dat, .json).

    Returns dict with:
      - orc_types: set[str] of ORC codes the system actively supports
      - features: set[str] of features found (e.g. {"OUTPUT_FILES", "PENDING"})
    """
    _CODE_EXTENSIONS = {
        '.java', '.py', '.sql', '.cob', '.jcl', '.sh', '.cobol', '.pc', '.pco',
        '.yaml', '.yml', '.xml', '.kt', '.scala', '.go', '.rb',
    }
    _PROP_EXTENSIONS = {'.properties', '.yaml', '.yml', '.xml', '.cfg', '.conf'}
    _DATA_EXTENSIONS = {'.csv', '.dat', '.txt', '.md', '.json', '.log'}

    def _ext(fname: str) -> str:
        dot = fname.rfind('.')
        return fname[dot:].lower() if dot != -1 else ''

    orc_types: set[str] = set()
    not_implemented_orcs: set[str] = set()

    # ── Tier 1: explicit supported list in .properties / config ──────────────
    explicit_found = False
    for fname, content in source_contents.items():
        if _ext(fname) not in _PROP_EXTENSIONS:
            continue
        # e.g. insurance.orc_types.supported=SGL,JNT,REV,BUS
        m = _re.search(
            r'orc[._]types?[._]supported\s*[=:]\s*([A-Z0-9,\s]+)',
            content, _re.IGNORECASE,
        )
        if m:
            raw = m.group(1).strip().rstrip(',')
            for code in _re.split(r'[,\s]+', raw):
                code = code.strip().upper()
                # Normalise GOV1/GOV2/GOV3 → GOV
                if code.startswith('GOV'):
                    orc_types.add('GOV')
                elif code and _re.match(r'^[A-Z]{2,4}\d?$', code):
                    orc_types.add(code)
            if orc_types:
                explicit_found = True
                break

    # ── Tier 2: CSV orc-mapping files — collect NOT_IMPLEMENTED markers ───────
    csv_orcs_active: set[str] = set()
    for fname, content in source_contents.items():
        if _ext(fname) != '.csv':
            continue
        if 'orc' not in fname.lower() and 'mapping' not in fname.lower():
            continue
        for line in content.splitlines():
            parts = [p.strip() for p in line.split(',')]
            if not parts:
                continue
            code = parts[0].strip().upper()
            if not _re.match(r'^[A-Z]{2,4}$', code):
                continue
            status = next((p.upper() for p in parts if 'NOT_IMPLEMENTED' in p.upper()
                           or p.upper() in ('ACTIVE', 'PARTIAL')), '')
            if 'NOT_IMPLEMENTED' in status:
                not_implemented_orcs.add(code)
            elif status in ('ACTIVE', 'PARTIAL'):
                csv_orcs_active.add(code)

    if not explicit_found and csv_orcs_active:
        # Use CSV active set as the base if no explicit config found
        orc_types = csv_orcs_active

    # ── Tier 3: code file scan (only if no explicit config and no CSV active) ──
    if not explicit_found and not csv_orcs_active:
        code_lines: list[str] = []
        for fname, content in source_contents.items():
            if _ext(fname) in _DATA_EXTENSIONS:
                continue  # skip data/reference files
            if _ext(fname) in _CODE_EXTENSIONS or _ext(fname) in _PROP_EXTENSIONS:
                for line in content.splitlines():
                    # Skip lines that have NOT_IMPLEMENTED marker (they reference
                    # the ORC type only as a placeholder / missing case)
                    if 'NOT_IMPLEMENTED' in line.upper():
                        continue
                    code_lines.append(line)
        all_code = "\n".join(code_lines)
        for orc_type, patterns in _ORC_DETECT_PATTERNS.items():
            for pat in patterns:
                if _re.search(pat, all_code, _re.IGNORECASE):
                    orc_types.add(orc_type)
                    break

    # Remove any ORC types explicitly marked NOT_IMPLEMENTED in CSV mapping
    orc_types -= not_implemented_orcs

    # ── Feature detection across ALL code files (no data files) ──────────────
    code_for_features: list[str] = []
    for fname, content in source_contents.items():
        if _ext(fname) not in _DATA_EXTENSIONS:
            code_for_features.append(content)
    all_code_feat = "\n".join(code_for_features)

    features: set[str] = set()
    for feature, patterns in _FEATURE_DETECT_PATTERNS.items():
        for pat in patterns:
            if _re.search(pat, all_code_feat, _re.IGNORECASE):
                features.add(feature)
                break

    return {"orc_types": orc_types, "features": features}


def get_applicable_control_ids(capabilities: dict) -> set[str]:
    """
    Determine which controls are applicable based on detected system capabilities.

    Returns a set of control_id strings for controls applicable to this system.
    """
    orc_types: set[str] = capabilities.get("orc_types", set())
    features: set[str] = capabilities.get("features", set())

    applicable: set[str] = set()

    for ctrl in CONTROL_LIBRARY:
        # Always-applicable categories
        if ctrl.category in _ALWAYS_APPLICABLE_CATEGORIES:
            applicable.add(ctrl.control_id)
            continue

        # ORC-specific controls (Part 330 sections)
        required_orcs = _control_required_orcs(ctrl.section)
        if required_orcs is not None:
            # This control requires specific ORC types — check if found in code
            if required_orcs & orc_types:  # set intersection
                applicable.add(ctrl.control_id)
            continue

        # Category-based feature checks
        if ctrl.category == ControlCategory.OUTPUT_FILES:
            if "OUTPUT_FILES" in features:
                applicable.add(ctrl.control_id)
            continue

        if ctrl.category == ControlCategory.PENDING_MGMT:
            if "PENDING" in features:
                applicable.add(ctrl.control_id)
            continue

        if ctrl.category == ControlCategory.ARE_PROCESSING:
            if "ARE" in features:
                applicable.add(ctrl.control_id)
            continue

        if ctrl.category == ControlCategory.CALCULATION:
            if "CALCULATION" in features:
                applicable.add(ctrl.control_id)
            continue

        if ctrl.category == ControlCategory.ORC_ASSIGNMENT:
            # General ORC assignment controls — applicable if system handles any ORC
            if orc_types:
                applicable.add(ctrl.control_id)
            continue

        # Default: applicable (don't accidentally exclude controls)
        applicable.add(ctrl.control_id)

    return applicable
