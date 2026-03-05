"""
Layer 7 -- Data Lineage & Back-Traceability Analyzer
=====================================================
Regulatory Source: 12 CFR 370.3(b), IT Guide §§2.1, 2.3, 5.1-5.4

Under 12 CFR 370.3(b), a Covered Institution must maintain an IT system
capable of rapidly and accurately calculating deposit insurance coverage
for each depositor.  The FDIC IT Functional Guide requires demonstrable
data lineage from source-of-record systems through transformation layers
to the final output files (QDF, ARE, Pending).

This layer:

1. **Source System Mapping** -- Identifies all upstream source systems
   feeding depositor/account data and validates complete coverage of
   required data fields across all ORC types.

2. **Transformation Traceability** -- Traces how data flows through
   ETL jobs, stored procedures, batch scripts, and application code;
   flags any transformation that is undocumented or breaks the chain.

3. **Field-Level Lineage** -- Maps critical fields (SSN/TIN, account
   balance, ORC classification, beneficiary data) from source to
   output, detecting silent drops, truncation, or type coercion.

4. **Audit Trail Completeness** -- Verifies that every data mutation
   is timestamped, logged, and traceable to the originating system.

5. **Cross-System Reconciliation** -- Checks that record counts and
   aggregate balances reconcile between source systems, intermediate
   stores, and output files.
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, datetime
from typing import Any

from backend.core.models import (
    AnalyzerLayer,
    ComplianceFinding,
    DepositAccount,
    FindingStatus,
    LayerScanResult,
    ORCType,
    Severity,
)


# ============================================================================
# Critical fields that MUST have end-to-end lineage per IT Guide §2.3
# ============================================================================

CRITICAL_LINEAGE_FIELDS = {
    "depositor_id":          "Unique depositor identifier (SSN/TIN/EIN)",
    "account_id":            "Unique account identifier",
    "account_balance":       "Current account balance including accrued interest",
    "orc_type":              "Ownership Right and Capacity classification",
    "beneficiary_data":      "Beneficiary names, counts, and allocation percentages",
    "joint_owner_data":      "Co-owner identifiers and signature card evidence",
    "government_id":         "Government-issued identification (SSN, TIN, EIN)",
    "account_type":          "Product type (checking, savings, CD, etc.)",
    "institution_id":        "FDIC certificate number / institution identifier",
    "insurance_amount":      "Calculated insured amount per SMDIA rules",
    "uninsured_amount":      "Calculated uninsured amount",
    "pending_reason":        "Reason code when routed to Pending File",
    "death_of_owner_date":   "Date of owner death for temporal coverage rules",
    "trust_interest":        "Beneficiary interest allocation for REV/IRR trusts",
    "participant_data":      "EBP participant records and vested amounts",
    "collateral_data":       "Collateral pledging evidence for GOV accounts",
}

# Source system patterns expected in a compliant legacy banking system
SOURCE_SYSTEM_PATTERNS = {
    "core_banking":     r"(?i)(core.?bank|deposit.?system|account.?master|DDA|customer.?master)",
    "trust_system":     r"(?i)(trust|beneficiar|estate|fiduciar)",
    "retirement":       r"(?i)(retirement|pension|401k|ira|ebp|benefit.?plan)",
    "government":       r"(?i)(government|municipal|federal|state|collateral|pledg)",
    "data_warehouse":   r"(?i)(warehouse|data.?lake|staging|etl|extract|transform)",
    "output_generator": r"(?i)(output|qdf|are|pending.?file|report.?gen|coverage.?calc)",
}

# Required audit trail elements
AUDIT_TRAIL_REQUIREMENTS = [
    "timestamp",
    "source_system",
    "record_count",
    "checksum",
    "batch_id",
    "reconciliation",
    "exception_log",
]


class Layer7DataLineageAnalyzer:
    """
    Traces data flows across the complete deposit insurance processing
    chain and validates end-to-end lineage from source systems to
    FDIC output files (QDF, ARE, Pending).
    """

    def scan(
        self,
        accounts: list[DepositAccount] | None = None,
        system_source_code: str = "",
        source_file_names: list[str] | None = None,
        analysis_date: date | None = None,
    ) -> LayerScanResult:
        """Execute Layer 7 data lineage analysis."""
        findings: list[ComplianceFinding] = []
        metrics: dict[str, Any] = {}
        _date = analysis_date or date.today()
        _files = source_file_names or []

        # ── Check 7.1: Source System Coverage ─────────────────────────
        findings.extend(self._check_source_system_coverage(system_source_code, _files))

        # ── Check 7.2: Field-Level Lineage Completeness ──────────────
        findings.extend(self._check_field_lineage(system_source_code))

        # ── Check 7.3: Transformation Chain Integrity ────────────────
        findings.extend(self._check_transformation_chain(system_source_code, _files))

        # ── Check 7.4: Audit Trail Completeness ──────────────────────
        findings.extend(self._check_audit_trail(system_source_code))

        # ── Check 7.5: Cross-System Reconciliation ───────────────────
        findings.extend(self._check_reconciliation(system_source_code))

        # ── Check 7.6: ORC-Specific Lineage Gaps ────────────────────
        findings.extend(self._check_orc_lineage_gaps(system_source_code))

        # ── Check 7.7: Data Flow Documentation ──────────────────────
        findings.extend(self._check_data_flow_documentation(system_source_code, _files))

        # ── Check 7.8: Dead-End & Orphan Data Paths ─────────────────
        findings.extend(self._check_dead_end_paths(system_source_code, _files))

        # Build metrics
        source_systems_found = sum(
            1 for pat in SOURCE_SYSTEM_PATTERNS.values()
            if re.search(pat, system_source_code)
        )
        fields_traced = sum(
            1 for field in CRITICAL_LINEAGE_FIELDS
            if re.search(rf"(?i){field}", system_source_code)
        )

        metrics = {
            "total_checks": 8,
            "source_systems_detected": source_systems_found,
            "source_systems_required": len(SOURCE_SYSTEM_PATTERNS),
            "critical_fields_traced": fields_traced,
            "critical_fields_required": len(CRITICAL_LINEAGE_FIELDS),
            "lineage_coverage_pct": round(
                fields_traced / len(CRITICAL_LINEAGE_FIELDS) * 100, 1
            ) if CRITICAL_LINEAGE_FIELDS else 0,
            "files_analyzed": len(_files),
            "findings_count": len(findings),
        }

        return LayerScanResult(
            layer=AnalyzerLayer.LAYER7_DATA_LINEAGE,
            findings=findings,
            passed=not any(f.severity in (Severity.CRITICAL, Severity.HIGH) for f in findings),
            metrics=metrics,
            summary=(
                f"Data Lineage Analysis: {len(findings)} findings | "
                f"{source_systems_found}/{len(SOURCE_SYSTEM_PATTERNS)} source systems detected | "
                f"{fields_traced}/{len(CRITICAL_LINEAGE_FIELDS)} critical fields traced | "
                f"Lineage coverage: {metrics['lineage_coverage_pct']}%"
            ),
        )

    # ───────────────────────────────────────────────────────────────────────
    # Check 7.1: Source System Coverage
    # ───────────────────────────────────────────────────────────────────────

    def _check_source_system_coverage(
        self, source_code: str, file_names: list[str]
    ) -> list[ComplianceFinding]:
        findings = []
        detected = {}
        missing = []

        for sys_name, pattern in SOURCE_SYSTEM_PATTERNS.items():
            if re.search(pattern, source_code):
                detected[sys_name] = True
            else:
                missing.append(sys_name)

        if missing:
            findings.append(ComplianceFinding(
                finding_id=f"L7-SRC-{_seq()}",
                layer=AnalyzerLayer.LAYER7_DATA_LINEAGE,
                severity=Severity.CRITICAL if len(missing) > 2 else Severity.HIGH,
                title="Incomplete Source System Coverage",
                description=(
                    f"Data lineage cannot be established for {len(missing)} of "
                    f"{len(SOURCE_SYSTEM_PATTERNS)} required source system categories. "
                    f"Missing: {', '.join(missing)}. Per IT Guide §2.1, all upstream "
                    f"systems feeding depositor data must be identified and mapped."
                ),
                cfr_reference="12 CFR 370.3(b)",
                it_guide_reference="IT Guide §2.1 - Source System Identification",
                expected_behavior=(
                    f"All {len(SOURCE_SYSTEM_PATTERNS)} source system categories must "
                    f"be represented in the processing chain"
                ),
                observed_behavior=(
                    f"Only {len(detected)}/{len(SOURCE_SYSTEM_PATTERNS)} source systems "
                    f"detected. Missing: {', '.join(missing)}"
                ),
                remediation_recommendation=(
                    "Add explicit source system integration for each missing category. "
                    "Document data feeds in the system architecture and ensure each "
                    "upstream system has a defined interface specification."
                ),
                evidence={"detected_systems": list(detected.keys()), "missing_systems": missing},
            ))

        # Check for hardcoded file paths (sign of fragile lineage)
        hardcoded_paths = re.findall(
            r'(?:"/(?:opt|home|usr|var|tmp|data|export)/[^"]+"|'
            r"'/(?:opt|home|usr|var|tmp|data|export)/[^']+')",
            source_code,
        )
        if hardcoded_paths:
            findings.append(ComplianceFinding(
                finding_id=f"L7-SRC-{_seq()}",
                layer=AnalyzerLayer.LAYER7_DATA_LINEAGE,
                severity=Severity.HIGH,
                title="Hardcoded Data Source Paths Detected",
                description=(
                    f"Found {len(hardcoded_paths)} hardcoded file system paths in source "
                    f"code. Hardcoded paths create brittle data lineage that can silently "
                    f"break during system migrations, DR failover, or environment changes."
                ),
                cfr_reference="12 CFR 370.3(b)",
                it_guide_reference="IT Guide §2.1 - Source System Configuration",
                expected_behavior="Data source paths should be externalized to configuration",
                observed_behavior=f"Found {len(hardcoded_paths)} hardcoded paths",
                remediation_recommendation=(
                    "Externalize all data source paths to configuration files or "
                    "environment variables. Use a service registry pattern for "
                    "source system endpoints."
                ),
                evidence={"hardcoded_paths": hardcoded_paths[:5]},
            ))

        return findings

    # ───────────────────────────────────────────────────────────────────────
    # Check 7.2: Field-Level Lineage Completeness
    # ───────────────────────────────────────────────────────────────────────

    def _check_field_lineage(self, source_code: str) -> list[ComplianceFinding]:
        findings = []
        traced_fields = {}
        untraced_fields = []

        for field, description in CRITICAL_LINEAGE_FIELDS.items():
            # Look for the field being read, transformed, and written
            read_pattern = rf"(?i)(select|read|get|fetch|load|extract|input).*{field}"
            write_pattern = rf"(?i)(insert|write|set|store|output|update|move).*{field}"
            direct_ref = rf"(?i){field}"

            has_read = bool(re.search(read_pattern, source_code))
            has_write = bool(re.search(write_pattern, source_code))
            has_ref = bool(re.search(direct_ref, source_code))

            if has_ref:
                traced_fields[field] = {
                    "has_read": has_read,
                    "has_write": has_write,
                    "full_lineage": has_read and has_write,
                }
                if not (has_read and has_write):
                    findings.append(ComplianceFinding(
                        finding_id=f"L7-FLD-{_seq()}",
                        layer=AnalyzerLayer.LAYER7_DATA_LINEAGE,
                        severity=Severity.MEDIUM,
                        title=f"Incomplete Lineage for Field: {field}",
                        description=(
                            f"Field '{field}' ({description}) is referenced in code but "
                            f"lacks {'read/input' if not has_read else 'write/output'} "
                            f"traceability. Complete lineage requires both source "
                            f"extraction and target persistence for every critical field."
                        ),
                        cfr_reference="12 CFR 370.3(b)",
                        it_guide_reference="IT Guide §2.3 - Data Field Requirements",
                        expected_behavior=f"Field '{field}' must be traceable from source to output",
                        observed_behavior=(
                            f"Field '{field}' found with "
                            f"{'read' if has_read else 'NO read'} and "
                            f"{'write' if has_write else 'NO write'} operations"
                        ),
                        remediation_recommendation=(
                            f"Ensure '{field}' has documented read from source system "
                            f"and write to output/intermediate store."
                        ),
                        evidence={"field": field, "has_read": has_read, "has_write": has_write},
                    ))
            else:
                untraced_fields.append(field)

        if untraced_fields:
            # Group into severity based on how many are missing
            severity = Severity.CRITICAL if len(untraced_fields) > 5 else Severity.HIGH
            findings.append(ComplianceFinding(
                finding_id=f"L7-FLD-{_seq()}",
                layer=AnalyzerLayer.LAYER7_DATA_LINEAGE,
                severity=severity,
                title="Critical Data Fields Missing from Lineage",
                description=(
                    f"{len(untraced_fields)} of {len(CRITICAL_LINEAGE_FIELDS)} critical "
                    f"fields required by IT Guide §2.3 have no presence in the analyzed "
                    f"code. These fields are essential for deposit insurance calculation "
                    f"and must be traceable end-to-end. Missing: "
                    f"{', '.join(untraced_fields[:8])}"
                    f"{'...' if len(untraced_fields) > 8 else ''}"
                ),
                cfr_reference="12 CFR 370.3(b)",
                it_guide_reference="IT Guide §2.3 - Required Data Elements",
                expected_behavior="All critical fields must appear in the data processing chain",
                observed_behavior=f"{len(untraced_fields)} fields have zero references in code",
                remediation_recommendation=(
                    "Add processing logic for each missing field. Ensure fields are "
                    "extracted from source systems, validated, transformed if needed, "
                    "and persisted to output files."
                ),
                evidence={
                    "untraced_fields": untraced_fields,
                    "traced_count": len(traced_fields),
                    "total_required": len(CRITICAL_LINEAGE_FIELDS),
                },
            ))

        return findings

    # ───────────────────────────────────────────────────────────────────────
    # Check 7.3: Transformation Chain Integrity
    # ───────────────────────────────────────────────────────────────────────

    def _check_transformation_chain(
        self, source_code: str, file_names: list[str]
    ) -> list[ComplianceFinding]:
        findings = []

        # Detect ETL/transformation patterns
        etl_patterns = {
            "extract": r"(?i)(extract|pull|read|select\s+.*\s+from|MOVE\s+\w+\s+TO)",
            "transform": r"(?i)(transform|convert|map|calculate|compute|COMPUTE|MULTIPLY|ADD)",
            "load": r"(?i)(load|insert|write|output|WRITE\s+\w+\s+FROM|store|persist)",
        }

        etl_phases_found = {}
        for phase, pattern in etl_patterns.items():
            matches = re.findall(pattern, source_code)
            etl_phases_found[phase] = len(matches)

        missing_phases = [p for p, count in etl_phases_found.items() if count == 0]
        if missing_phases:
            findings.append(ComplianceFinding(
                finding_id=f"L7-ETL-{_seq()}",
                layer=AnalyzerLayer.LAYER7_DATA_LINEAGE,
                severity=Severity.HIGH,
                title="Incomplete ETL Transformation Chain",
                description=(
                    f"ETL processing chain is missing {', '.join(missing_phases)} "
                    f"phase(s). A complete Extract-Transform-Load chain is required "
                    f"to establish data lineage from source systems to output files."
                ),
                cfr_reference="12 CFR 370.3(b)",
                it_guide_reference="IT Guide §5.1 - Data Processing Pipeline",
                expected_behavior="Complete ETL chain with extract, transform, and load phases",
                observed_behavior=f"Missing phases: {', '.join(missing_phases)}",
                remediation_recommendation=(
                    "Implement the missing ETL phases with proper logging, "
                    "error handling, and reconciliation at each stage."
                ),
                evidence={"etl_phases": etl_phases_found, "missing": missing_phases},
            ))

        # Check for data type coercion without validation
        unsafe_casts = re.findall(
            r"(?i)(cast|convert|to_number|to_char|atoi|parseInt|REDEFINES|"
            r"PIC\s+9.*REDEFINES\s+PIC\s+X)",
            source_code,
        )
        if unsafe_casts:
            findings.append(ComplianceFinding(
                finding_id=f"L7-ETL-{_seq()}",
                layer=AnalyzerLayer.LAYER7_DATA_LINEAGE,
                severity=Severity.MEDIUM,
                title="Unvalidated Data Type Coercion in Pipeline",
                description=(
                    f"Found {len(unsafe_casts)} type coercion/cast operations that "
                    f"may silently truncate or corrupt data during transformation. "
                    f"Each type conversion must be guarded with validation to prevent "
                    f"data loss in the insurance calculation pipeline."
                ),
                cfr_reference="12 CFR 370.3(b)",
                it_guide_reference="IT Guide §2.3 - Data Integrity",
                expected_behavior="All type conversions validated with error handling",
                observed_behavior=f"Found {len(unsafe_casts)} unguarded type coercions",
                remediation_recommendation=(
                    "Add validation logic around each type conversion. Log conversion "
                    "failures and route affected records to the Pending File."
                ),
                evidence={"cast_operations": [str(c) for c in unsafe_casts[:5]]},
            ))

        # Check for silent data drops (WHERE clauses that filter out records)
        filter_patterns = re.findall(
            r"(?i)(WHERE\s+.*(?:NOT\s+IN|<>|!=|NOT\s+LIKE|EXCLUDE|OMIT|SKIP)"
            r"|IF\s+.*(?:SKIP|NEXT\s+SENTENCE|CONTINUE)"
            r"|\.filter\(|\.reject\()",
            source_code,
        )
        if filter_patterns:
            findings.append(ComplianceFinding(
                finding_id=f"L7-ETL-{_seq()}",
                layer=AnalyzerLayer.LAYER7_DATA_LINEAGE,
                severity=Severity.HIGH,
                title="Potential Silent Data Drops in Pipeline",
                description=(
                    f"Found {len(filter_patterns)} filtering operations that may "
                    f"silently exclude depositor records from insurance calculation. "
                    f"Any record exclusion must be documented and the excluded records "
                    f"must be routed to the Pending File with appropriate reason codes."
                ),
                cfr_reference="12 CFR 370.3(b)",
                it_guide_reference="IT Guide §5.2 - Record Completeness",
                expected_behavior="All excluded records routed to Pending File with reason codes",
                observed_behavior=f"Found {len(filter_patterns)} filtering operations",
                remediation_recommendation=(
                    "Audit each filter/exclusion to ensure no depositor records are "
                    "silently dropped. Route excluded records to Pending File."
                ),
                evidence={"filter_count": len(filter_patterns)},
            ))

        return findings

    # ───────────────────────────────────────────────────────────────────────
    # Check 7.4: Audit Trail Completeness
    # ───────────────────────────────────────────────────────────────────────

    def _check_audit_trail(self, source_code: str) -> list[ComplianceFinding]:
        findings = []
        present = []
        missing_elements = []

        audit_patterns = {
            "timestamp": r"(?i)(timestamp|datetime|CURRENT[_-]DATE|CURRENT[_-]TIMESTAMP|now\(\)|getTime|DATE\-COMPILED)",
            "source_system": r"(?i)(source[_-]?system|data[_-]?source|origin|feed[_-]?id)",
            "record_count": r"(?i)(record[_-]?count|row[_-]?count|@@ROWCOUNT|WS-RECORD-COUNT|counter|tally)",
            "checksum": r"(?i)(checksum|hash|digest|md5|sha[_-]?256|crc|verify)",
            "batch_id": r"(?i)(batch[_-]?id|job[_-]?id|run[_-]?id|JOB\s+\w+|JOBNAME|execution[_-]?id)",
            "reconciliation": r"(?i)(reconcil|balance[_-]?check|cross[_-]?check|validate[_-]?total|control[_-]?total)",
            "exception_log": r"(?i)(exception|error[_-]?log|error[_-]?report|reject|discard|DISPLAY\s+.*ERROR)",
        }

        for element, pattern in audit_patterns.items():
            if re.search(pattern, source_code):
                present.append(element)
            else:
                missing_elements.append(element)

        if missing_elements:
            severity = Severity.CRITICAL if len(missing_elements) > 3 else Severity.HIGH
            findings.append(ComplianceFinding(
                finding_id=f"L7-AUD-{_seq()}",
                layer=AnalyzerLayer.LAYER7_DATA_LINEAGE,
                severity=severity,
                title="Incomplete Audit Trail for Data Lineage",
                description=(
                    f"The data processing pipeline is missing {len(missing_elements)} of "
                    f"{len(AUDIT_TRAIL_REQUIREMENTS)} required audit trail elements: "
                    f"{', '.join(missing_elements)}. Per IT Guide §5.3, every data "
                    f"transformation must maintain a complete audit trail."
                ),
                cfr_reference="12 CFR 370.10(a)",
                it_guide_reference="IT Guide §5.3 - Audit Trail Requirements",
                expected_behavior="All audit trail elements present in processing pipeline",
                observed_behavior=(
                    f"Only {len(present)}/{len(AUDIT_TRAIL_REQUIREMENTS)} elements found. "
                    f"Missing: {', '.join(missing_elements)}"
                ),
                remediation_recommendation=(
                    "Implement the missing audit trail elements at each processing "
                    "stage. Each batch run must record timestamps, source identification, "
                    "record counts, checksums, and exception logs."
                ),
                evidence={"present": present, "missing": missing_elements},
            ))

        return findings

    # ───────────────────────────────────────────────────────────────────────
    # Check 7.5: Cross-System Reconciliation
    # ───────────────────────────────────────────────────────────────────────

    def _check_reconciliation(self, source_code: str) -> list[ComplianceFinding]:
        findings = []

        # Check for balance reconciliation
        balance_recon = re.search(
            r"(?i)(sum.*balance.*=|total.*balance.*compare|reconcil.*balance|"
            r"COMPUTE\s+WS-TOTAL|control.?total.*balance)",
            source_code,
        )

        # Check for record count reconciliation
        count_recon = re.search(
            r"(?i)(count.*=.*count|record.?count.*match|reconcil.*count|"
            r"WS-RECORD-COUNT|@@ROWCOUNT.*=|total.?records.*compare)",
            source_code,
        )

        if not balance_recon:
            findings.append(ComplianceFinding(
                finding_id=f"L7-REC-{_seq()}",
                layer=AnalyzerLayer.LAYER7_DATA_LINEAGE,
                severity=Severity.CRITICAL,
                title="No Balance Reconciliation Between Processing Stages",
                description=(
                    "No evidence of aggregate balance reconciliation between data "
                    "processing stages. Without balance reconciliation, the system "
                    "cannot detect silent data loss or corruption that would cause "
                    "incorrect deposit insurance calculations."
                ),
                cfr_reference="12 CFR 370.3(b)",
                it_guide_reference="IT Guide §5.4 - Reconciliation Controls",
                expected_behavior=(
                    "Aggregate deposit balances must reconcile between source extraction, "
                    "transformation, and output generation stages"
                ),
                observed_behavior="No balance reconciliation logic detected",
                remediation_recommendation=(
                    "Implement control totals for aggregate balances at each processing "
                    "stage. Compare totals between stages and halt processing if "
                    "discrepancies exceed tolerance thresholds."
                ),
                evidence={"balance_reconciliation_found": False},
            ))

        if not count_recon:
            findings.append(ComplianceFinding(
                finding_id=f"L7-REC-{_seq()}",
                layer=AnalyzerLayer.LAYER7_DATA_LINEAGE,
                severity=Severity.HIGH,
                title="No Record Count Reconciliation in Data Pipeline",
                description=(
                    "No evidence of record count reconciliation between processing "
                    "stages. Records may be silently dropped without detection."
                ),
                cfr_reference="12 CFR 370.3(b)",
                it_guide_reference="IT Guide §5.4 - Reconciliation Controls",
                expected_behavior="Record counts must match between processing stages",
                observed_behavior="No record count reconciliation logic detected",
                remediation_recommendation=(
                    "Add record count validation at each processing boundary. "
                    "Log expected vs. actual counts and alert on mismatches."
                ),
                evidence={"count_reconciliation_found": False},
            ))

        return findings

    # ───────────────────────────────────────────────────────────────────────
    # Check 7.6: ORC-Specific Lineage Gaps
    # ───────────────────────────────────────────────────────────────────────

    def _check_orc_lineage_gaps(self, source_code: str) -> list[ComplianceFinding]:
        findings = []

        # For each ORC type, check that its specific data requirements
        # appear in the lineage
        orc_data_requirements = {
            ORCType.SGL: ["depositor_id", "ssn", "account_balance"],
            ORCType.JNT: ["joint", "signature_card", "co_owner", "split"],
            ORCType.REV: ["beneficiary", "trust", "revocable", "grantor"],
            ORCType.IRR: ["irrevocable", "beneficiary_interest", "trust_allocation"],
            ORCType.BUS: ["entity", "ein", "tax_id", "organization"],
            ORCType.CRA: ["retirement", "ira", "keogh"],
            ORCType.EBP: ["participant", "employee_benefit", "vested", "plan"],
            ORCType.ANC: ["annuity", "contract", "insurance_company"],
            ORCType.GOV1: ["federal", "government", "collateral"],
            ORCType.GOV2: ["state", "municipal", "collateral"],
            ORCType.GOV3: ["tribal", "government", "collateral"],
        }

        missing_orc_lineage = []
        for orc_type, required_terms in orc_data_requirements.items():
            found_terms = [
                term for term in required_terms
                if re.search(rf"(?i){term}", source_code)
            ]
            if len(found_terms) < len(required_terms) * 0.5:
                missing_orc_lineage.append({
                    "orc": orc_type.value,
                    "terms_found": len(found_terms),
                    "terms_required": len(required_terms),
                    "missing": [t for t in required_terms if t not in found_terms],
                })

        if missing_orc_lineage:
            orc_names = [m["orc"] for m in missing_orc_lineage]
            findings.append(ComplianceFinding(
                finding_id=f"L7-ORC-{_seq()}",
                layer=AnalyzerLayer.LAYER7_DATA_LINEAGE,
                severity=Severity.CRITICAL if len(missing_orc_lineage) > 3 else Severity.HIGH,
                title=f"Data Lineage Gaps for {len(missing_orc_lineage)} ORC Types",
                description=(
                    f"Insufficient data lineage evidence for ORC types: "
                    f"{', '.join(orc_names)}. Each ORC category requires specific "
                    f"data elements to flow from source systems through to output "
                    f"files. Without complete lineage, insurance coverage calculations "
                    f"for these ORC types cannot be verified."
                ),
                cfr_reference="12 CFR 370.3(b), 12 CFR Part 330",
                it_guide_reference="IT Guide §4 - ORC Data Requirements",
                expected_behavior="Complete data lineage for all 11 ORC types",
                observed_behavior=(
                    f"{len(missing_orc_lineage)} ORC types have insufficient "
                    f"data lineage: {', '.join(orc_names)}"
                ),
                remediation_recommendation=(
                    "For each affected ORC type, ensure the required data elements "
                    "are extracted from source systems, properly transformed, and "
                    "included in output files."
                ),
                evidence={"orc_lineage_gaps": missing_orc_lineage},
            ))

        return findings

    # ───────────────────────────────────────────────────────────────────────
    # Check 7.7: Data Flow Documentation
    # ───────────────────────────────────────────────────────────────────────

    def _check_data_flow_documentation(
        self, source_code: str, file_names: list[str]
    ) -> list[ComplianceFinding]:
        findings = []

        # Check for inline documentation of data flows
        doc_patterns = [
            r"(?i)(data\s+flow|data\s+lineage|source\s+system|upstream|downstream)",
            r"(?i)(input.*:.*output|from\s+system|feeds?\s+into|produces?)",
            r"(?:\*{3,}|={3,}|-{3,})",  # Section dividers indicating documentation
        ]

        doc_score = sum(
            1 for pat in doc_patterns
            if re.search(pat, source_code)
        )

        # Check for data dictionary or field mapping documentation
        has_data_dict = bool(re.search(
            r"(?i)(data\s+dictionary|field\s+mapping|column\s+definition|schema|"
            r"COPYBOOK|copybook|record\s+layout)",
            source_code,
        ))

        if doc_score < 2 and not has_data_dict:
            findings.append(ComplianceFinding(
                finding_id=f"L7-DOC-{_seq()}",
                layer=AnalyzerLayer.LAYER7_DATA_LINEAGE,
                severity=Severity.MEDIUM,
                title="Insufficient Data Flow Documentation",
                description=(
                    "The source code lacks adequate data flow documentation. "
                    "IT Guide §2.1 requires that data flows between source systems "
                    "and the deposit insurance calculation system be documented "
                    "including field mappings, transformation rules, and system "
                    "interfaces."
                ),
                cfr_reference="12 CFR 370.10(a)",
                it_guide_reference="IT Guide §2.1 - System Documentation",
                expected_behavior="Comprehensive data flow documentation with field mappings",
                observed_behavior=f"Documentation score: {doc_score}/3, data dictionary: {'Yes' if has_data_dict else 'No'}",
                remediation_recommendation=(
                    "Add data flow documentation including: source-to-target field "
                    "mappings, transformation rules, interface specifications, and "
                    "a data dictionary for all critical fields."
                ),
                evidence={"doc_score": doc_score, "has_data_dict": has_data_dict},
            ))

        return findings

    # ───────────────────────────────────────────────────────────────────────
    # Check 7.8: Dead-End & Orphan Data Paths
    # ───────────────────────────────────────────────────────────────────────

    def _check_dead_end_paths(
        self, source_code: str, file_names: list[str]
    ) -> list[ComplianceFinding]:
        findings = []

        # Detect tables/files referenced but never used downstream
        # Look for table references in SQL
        tables_created = set(re.findall(
            r"(?i)(?:CREATE\s+TABLE|INSERT\s+INTO|INTO\s+TABLE)\s+[`\[\"]?(\w+)",
            source_code,
        ))
        tables_read = set(re.findall(
            r"(?i)(?:FROM|JOIN)\s+[`\[\"]?(\w+)",
            source_code,
        ))

        # Tables that are written to but never read from (potential dead ends)
        dead_end_tables = tables_created - tables_read
        # Remove common temp/staging patterns
        dead_end_tables = {
            t for t in dead_end_tables
            if not re.match(r"(?i)(tmp|temp|#|staging)", t)
        }

        if dead_end_tables:
            findings.append(ComplianceFinding(
                finding_id=f"L7-DEP-{_seq()}",
                layer=AnalyzerLayer.LAYER7_DATA_LINEAGE,
                severity=Severity.MEDIUM,
                title="Dead-End Data Paths Detected",
                description=(
                    f"Found {len(dead_end_tables)} data stores that are written to "
                    f"but never read from in the analyzed code: "
                    f"{', '.join(list(dead_end_tables)[:5])}. These may represent "
                    f"abandoned processing paths or missing downstream consumers."
                ),
                cfr_reference="12 CFR 370.3(b)",
                it_guide_reference="IT Guide §5.1 - Data Processing Pipeline",
                expected_behavior="All data stores should have both write and read operations",
                observed_behavior=f"{len(dead_end_tables)} tables have no downstream consumers",
                remediation_recommendation=(
                    "Review each dead-end table. If no longer needed, remove the "
                    "write operations. If needed, add downstream consumption or "
                    "document the external consumer."
                ),
                evidence={"dead_end_tables": list(dead_end_tables)},
            ))

        # Check for orphan files (referenced in code but not in file list)
        file_refs = re.findall(
            r"""(?:['"])([^'"]+\.(?:csv|dat|txt|xml|json|qdf|are))(?:['"])""",
            source_code,
        )
        if file_refs and file_names:
            orphan_refs = [
                ref for ref in file_refs
                if not any(ref.lower() in fn.lower() for fn in file_names)
            ]
            if orphan_refs:
                findings.append(ComplianceFinding(
                    finding_id=f"L7-DEP-{_seq()}",
                    layer=AnalyzerLayer.LAYER7_DATA_LINEAGE,
                    severity=Severity.HIGH,
                    title="Orphan File References in Processing Code",
                    description=(
                        f"Found {len(orphan_refs)} file references in code that do not "
                        f"correspond to any known system file: "
                        f"{', '.join(orphan_refs[:5])}. These broken references can "
                        f"cause silent failures in the data pipeline."
                    ),
                    cfr_reference="12 CFR 370.3(b)",
                    it_guide_reference="IT Guide §5.1 - File Integrity",
                    expected_behavior="All file references resolve to actual system files",
                    observed_behavior=f"{len(orphan_refs)} orphan file references found",
                    remediation_recommendation=(
                        "Verify each file reference. Remove stale references or "
                        "add the missing files to the system."
                    ),
                    evidence={"orphan_file_refs": orphan_refs},
                ))

        return findings


# ── Sequence Counter ───────────────────────────────────────────────────────────

_counter = 0

def _seq() -> str:
    global _counter
    _counter += 1
    return f"{_counter:03d}"
