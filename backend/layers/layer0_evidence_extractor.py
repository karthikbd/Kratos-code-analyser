"""
Layer 0 -- Source Code Evidence Extraction & Regulatory Comparison
===================================================================

This layer does the REAL compliance work:

  Step 1 — EXTRACT
    Scan every source file in the operational system (COBOL, Java, SQL,
    Python, config, JCL, shell scripts) and pull out every
    compliance-relevant value: numeric limits, ORC type lists, pending
    codes, flags, config settings.

  Step 2 — CLARIFY (via FDIC docs)
    For each extracted parameter, look up the regulatory requirement from
    the FDIC document knowledge base (12 CFR 330 / 360 / 370 / IT Guide).

  Step 3 — COMPARE
    Diff the extracted code value against the regulatory requirement.
    Any mismatch produces an EvidenceFinding with:
      - exact file path + line number where the value was found
      - the value found in the code
      - the FDIC-required value
      - severity + CFR citation

This approach replaces pure keyword-scanning with value-level
compliance verification — the same logic an FDIC examiner applies
when reviewing source code on-site.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from backend.core.models import (
    AnalyzerLayer,
    ComplianceFinding,
    LayerScanResult,
    Severity,
)


# ============================================================================
# FDIC Regulatory Requirements — sourced from the actual FDIC documents
# (12 CFR 330, 12 CFR 360.8, 12 CFR 370, FDIC IT Guide v3.0 June 2023)
# ============================================================================

FDIC_REQUIREMENTS: dict[str, dict[str, Any]] = {

    # ── 12 CFR 330 ────────────────────────────────────────────────────────
    "smdia_limit": {
        "description": "Standard Maximum Deposit Insurance Amount per depositor per ORC",
        "required_value": 250_000.00,
        "unit": "USD",
        "regulation": "12 CFR 330.1(o)",
        "severity": Severity.CRITICAL,
        "allowed_operators": ["==", "<="],   # code must not cap BELOW 250k
        "notes": "Exact value — $250,000. Not $100k, $50k, or any other value.",
    },
    "ebp_coverage_mode": {
        "description": "Employee Benefit Plan coverage must be per-participant pass-through",
        "required_value": "PER_PARTICIPANT",
        "regulation": "12 CFR 330.14",
        "severity": Severity.CRITICAL,
        "notes": "Pass-through coverage: each participant's share insured up to $250k. "
                 "PER_PLAN means all participants share one $250k limit — non-compliant.",
    },
    "supported_orc_types": {
        "description": "All 11 ORC types must be implemented",
        "required_value": {"SGL", "JNT", "REV", "IRR", "BUS", "EBP", "CRA",
                           "GOV1", "GOV2", "GOV3", "ANC"},
        "regulation": "12 CFR Part 330 + IT Guide Section 4",
        "severity": Severity.CRITICAL,
        "notes": "All 11 Ownership Right and Capacity categories must be handled. "
                 "IRR (Irrevocable Trust) is frequently missing from legacy systems.",
    },
    "pending_reason_codes": {
        "description": "All 10 pending reason codes must be defined",
        "required_value": {"RAC", "BEN", "ORC", "DUP", "GOV", "LNK", "MRG", "TIM", "DAT", "ARE"},
        "regulation": "FDIC IT Guide v3.0 Section 5.2",
        "severity": Severity.HIGH,
        "notes": "Incomplete pending code definitions mean some accounts cannot be "
                 "correctly routed to the Pending File.",
    },

    # ── 12 CFR 360.8 ──────────────────────────────────────────────────────
    "close_of_business_balance": {
        "description": "Balance used for insurance must be close-of-business, not real-time",
        "required_value": True,
        "regulation": "12 CFR 360.8",
        "severity": Severity.HIGH,
        "detection_keywords": ["close_of_business", "cob_balance", "end_of_day",
                               "CLOSE-OF-BUSINESS", "COB-BALANCE", "EOD"],
        "notes": "Insurance calculations must use posted close-of-business balance. "
                 "Real-time or intraday balances are non-compliant.",
    },

    # ── 12 CFR 370.3(b) ───────────────────────────────────────────────────
    "processing_deadline_hours": {
        "description": "Maximum hours to complete insurance determination after failure",
        "required_value": 24,
        "unit": "hours",
        "regulation": "12 CFR 370.3(b)",
        "severity": Severity.CRITICAL,
        "notes": "The institution must be able to produce deposit insurance "
                 "determinations within 24 hours of a bank closing.",
    },
    "processing_target_hours": {
        "description": "Target processing time (best-practice per IT Guide)",
        "required_value": 8,
        "unit": "hours",
        "regulation": "FDIC IT Guide v3.0 Section 2.1",
        "severity": Severity.MEDIUM,
        "notes": "While the hard deadline is 24 hours, the IT Guide recommends "
                 "targeting 8 hours to provide a safety margin.",
    },

    # ── FDIC IT Guide Section 6.1 ─────────────────────────────────────────
    "output_delimiter": {
        "description": "Output file field delimiter must be pipe character",
        "required_value": "|",
        "regulation": "FDIC IT Guide v3.0 Section 6.1.2",
        "severity": Severity.HIGH,
        "notes": "FDIC specifies pipe-delimited output files. Comma or other "
                 "delimiters require FDIC approval and are non-standard.",
    },
    "output_checksum": {
        "description": "Output files must include record count and checksum",
        "required_value": True,
        "regulation": "FDIC IT Guide v3.0 Section 6.1.3",
        "severity": Severity.HIGH,
        "notes": "Checksums allow the FDIC to verify file integrity and detect "
                 "truncation or corruption during transmission.",
    },
    "output_encrypt_pii": {
        "description": "PII fields in output files must be encrypted",
        "required_value": True,
        "regulation": "FDIC IT Guide v3.0 Section 7.3",
        "severity": Severity.CRITICAL,
        "notes": "Customer PII (SSN, account numbers) must be encrypted in all "
                 "output files transmitted to the FDIC.",
    },

    # ── 12 CFR 370.5(c) ───────────────────────────────────────────────────
    "data_retention_years": {
        "description": "Minimum data retention period for deposit insurance records",
        "required_value": 5,
        "unit": "years",
        "regulation": "12 CFR 370.5(c)",
        "severity": Severity.HIGH,
        "notes": "Records used in insurance determination must be retained for "
                 "at least 5 years to support post-failure audits.",
    },

    # ── Manual/Auto data refresh ──────────────────────────────────────────
    "government_data_refresh": {
        "description": "Government deposit data must be refreshed automatically (no manual processes)",
        "required_value": "AUTO",
        "regulation": "12 CFR 370.4(b) + IT Guide Section 3.2",
        "severity": Severity.HIGH,
        "notes": "Manual data refresh introduces delay risk. Government deposit "
                 "data must be auto-refreshed from authoritative source systems.",
    },

    # ── Debt/offset logic ─────────────────────────────────────────────────
    "debt_offset_excludes_credit_cards": {
        "description": "Debt offset must exclude credit card balances",
        "required_value": True,
        "regulation": "12 CFR 330 + FDIC Compliance Review Manual Section 8",
        "severity": Severity.HIGH,
        "detection_keywords": ["credit_card", "CREDIT-CARD", "creditcard",
                               "CARD-BALANCE", "card_balance"],
        "notes": "Only loan balances (not credit cards) may be offset against "
                 "deposit balances when calculating net insured amount.",
    },

    # ── Aggregation ───────────────────────────────────────────────────────
    "aggregation_before_smdia": {
        "description": "Deposits must be aggregated per depositor per ORC before applying SMDIA",
        "required_value": True,
        "regulation": "12 CFR 330.3(b)",
        "severity": Severity.CRITICAL,
        "detection_keywords": ["aggregate", "AGGREGATE", "total_per_depositor",
                               "TOTAL-DEPOSITOR", "sum_by_orc", "GROUP BY"],
        "notes": "Applying the $250k limit per account instead of per depositor/ORC "
                 "combination is the most common critical FDIC compliance failure.",
    },
}


# ============================================================================
# Evidence Items — a single value found in code
# ============================================================================

@dataclass
class EvidenceItem:
    """A compliance-relevant value extracted from a source file."""
    parameter: str          # e.g. "smdia_limit"
    file_path: str          # relative file path
    line_number: int        # 1-based
    raw_text: str           # the matching line/block of code
    extracted_value: Any    # parsed value (float, str, set, bool)
    extraction_method: str  # "regex", "config_parser", "ast", etc.
    confidence: str         # "HIGH", "MEDIUM", "LOW"


@dataclass
class EvidenceFinding:
    """Result of comparing an extracted code value against FDIC requirement."""
    parameter: str
    requirement_description: str
    regulation: str
    severity: Severity

    # What was found in the code
    code_value: Any
    code_file: str
    code_line: int
    code_context: str

    # What FDIC requires
    required_value: Any

    # Gap analysis
    is_compliant: bool
    gap_description: str
    remediation: str


# ============================================================================
# File-type extractors
# ============================================================================

class _FileExtractor:
    """Base — extracts evidence items from a single source file."""

    def __init__(self, file_path: str, content: str) -> None:
        self.file_path = file_path
        self.content = content
        self.lines = content.splitlines()

    def _find_lines(self, pattern: str, flags: int = re.IGNORECASE) -> list[tuple[int, str]]:
        """Return (1-based line number, full line) for every line matching pattern."""
        compiled = re.compile(pattern, flags)
        return [(i + 1, line) for i, line in enumerate(self.lines) if compiled.search(line)]

    def extract(self) -> list[EvidenceItem]:
        raise NotImplementedError


class ConfigPropertiesExtractor(_FileExtractor):
    """Extracts from .properties / .xml / .yaml config files."""

    def extract(self) -> list[EvidenceItem]:
        items: list[EvidenceItem] = []

        # ── SMDIA limit ─────────────────────────────────────────────────
        for lineno, line in self._find_lines(
            r"(?:smdia|insurance[\._-]limit|max[\._-]insured|coverage[\._-]limit)\s*[=:]\s*([\d,\.]+)",
        ):
            m = re.search(r"([\d,]+\.?\d*)", line)
            if m:
                val = float(m.group(1).replace(",", ""))
                items.append(EvidenceItem(
                    parameter="smdia_limit", file_path=self.file_path,
                    line_number=lineno, raw_text=line.strip(),
                    extracted_value=val, extraction_method="config_regex",
                    confidence="HIGH",
                ))

        # ── EBP mode ────────────────────────────────────────────────────
        for lineno, line in self._find_lines(r"(?:ebp|employee[\._-]benefit)[\._-]?mode\s*[=:]"):
            m = re.search(r"=\s*(\S+)", line)
            if m:
                items.append(EvidenceItem(
                    parameter="ebp_coverage_mode", file_path=self.file_path,
                    line_number=lineno, raw_text=line.strip(),
                    extracted_value=m.group(1).strip(), extraction_method="config_regex",
                    confidence="HIGH",
                ))

        # ── Supported ORC types ─────────────────────────────────────────
        for lineno, line in self._find_lines(r"(?:supported[\._-]orc[\._-]types|orc[\._-]types)\s*[=:]"):
            m = re.search(r"=\s*(.+)", line)
            if m:
                found_types = {t.strip().upper() for t in m.group(1).split(",") if t.strip()}
                items.append(EvidenceItem(
                    parameter="supported_orc_types", file_path=self.file_path,
                    line_number=lineno, raw_text=line.strip(),
                    extracted_value=found_types, extraction_method="config_regex",
                    confidence="HIGH",
                ))

        # ── Processing deadline ─────────────────────────────────────────
        for lineno, line in self._find_lines(r"(?:processing[\._-]max[\._-]hours|max[\._-]processing[\._-]hours)\s*[=:]"):
            m = re.search(r"=\s*(\d+)", line)
            if m:
                items.append(EvidenceItem(
                    parameter="processing_deadline_hours", file_path=self.file_path,
                    line_number=lineno, raw_text=line.strip(),
                    extracted_value=int(m.group(1)), extraction_method="config_regex",
                    confidence="HIGH",
                ))

        # ── Processing target ───────────────────────────────────────────
        for lineno, line in self._find_lines(r"(?:processing[\._-]target[\._-]hours|target[\._-]hours)\s*[=:]"):
            m = re.search(r"=\s*(\d+)", line)
            if m:
                items.append(EvidenceItem(
                    parameter="processing_target_hours", file_path=self.file_path,
                    line_number=lineno, raw_text=line.strip(),
                    extracted_value=int(m.group(1)), extraction_method="config_regex",
                    confidence="HIGH",
                ))

        # ── Output delimiter ─────────────────────────────────────────────
        for lineno, line in self._find_lines(r"(?:output[\._-]delimiter|field[\._-]delimiter|delimiter)\s*[=:]"):
            m = re.search(r"=\s*(.+)", line)
            if m:
                val = m.group(1).strip().strip('"').strip("'")
                items.append(EvidenceItem(
                    parameter="output_delimiter", file_path=self.file_path,
                    line_number=lineno, raw_text=line.strip(),
                    extracted_value=val, extraction_method="config_regex",
                    confidence="HIGH",
                ))

        # ── Checksum flag ────────────────────────────────────────────────
        for lineno, line in self._find_lines(r"(?:generate[\._-]checksum|enable[\._-]checksum|checksum)\s*[=:]"):
            m = re.search(r"=\s*(\S+)", line)
            if m:
                val = m.group(1).strip().lower()
                items.append(EvidenceItem(
                    parameter="output_checksum", file_path=self.file_path,
                    line_number=lineno, raw_text=line.strip(),
                    extracted_value=val not in ("false", "0", "no", "off"),
                    extraction_method="config_regex",
                    confidence="HIGH",
                ))

        # ── PII encryption ───────────────────────────────────────────────
        for lineno, line in self._find_lines(r"(?:encrypt[\._-]pii|pii[\._-]encrypt|encrypt)\s*[=:]"):
            m = re.search(r"=\s*(\S+)", line)
            if m:
                val = m.group(1).strip().lower()
                items.append(EvidenceItem(
                    parameter="output_encrypt_pii", file_path=self.file_path,
                    line_number=lineno, raw_text=line.strip(),
                    extracted_value=val not in ("false", "0", "no", "off"),
                    extraction_method="config_regex",
                    confidence="HIGH",
                ))

        # ── Government data refresh mode ────────────────────────────────
        for lineno, line in self._find_lines(r"(?:government[\._-]refresh[\._-]mode|gov[\._-]refresh)\s*[=:]"):
            m = re.search(r"=\s*(\S+)", line)
            if m:
                items.append(EvidenceItem(
                    parameter="government_data_refresh", file_path=self.file_path,
                    line_number=lineno, raw_text=line.strip(),
                    extracted_value=m.group(1).strip().upper(),
                    extraction_method="config_regex",
                    confidence="HIGH",
                ))

        # ── Pending codes count ─────────────────────────────────────────
        pending_codes: set[str] = set()
        pending_lineno = 0
        pending_line = ""
        for lineno, line in self._find_lines(r"pending[\._-]code[\._-](P\d+|[A-Z]+)\s*="):
            code_m = re.search(r"pending[\._-]code[\._-]([A-Za-z0-9]+)\s*=", line, re.IGNORECASE)
            if code_m:
                pending_codes.add(code_m.group(1).upper())
                if not pending_lineno:
                    pending_lineno = lineno
                    pending_line = line.strip()
        if pending_codes:
            items.append(EvidenceItem(
                parameter="pending_reason_codes", file_path=self.file_path,
                line_number=pending_lineno, raw_text=f"Codes found: {sorted(pending_codes)} (first at: {pending_line})",
                extracted_value=pending_codes, extraction_method="config_scan",
                confidence="HIGH",
            ))

        # ── Data retention ──────────────────────────────────────────────
        for lineno, line in self._find_lines(r"(?:retention[\._-]years?|data[\._-]retention|archive[\._-]years?)\s*[=:]"):
            m = re.search(r"=\s*(\d+)", line)
            if m:
                items.append(EvidenceItem(
                    parameter="data_retention_years", file_path=self.file_path,
                    line_number=lineno, raw_text=line.strip(),
                    extracted_value=int(m.group(1)), extraction_method="config_regex",
                    confidence="HIGH",
                ))

        return items


class CobolExtractor(_FileExtractor):
    """Extracts from COBOL source (.cob, .cpy) files."""

    def extract(self) -> list[EvidenceItem]:
        items: list[EvidenceItem] = []

        # ── SMDIA / insurance limit constants ───────────────────────────
        for lineno, line in self._find_lines(
            r"(?:SMDIA|INSURANCE[-\s]LIMIT|MAX[-\s]INSURED|COVERAGE[-\s]LIMIT|WS-SMDIA|WS-MAX)"
        ):
            m = re.search(r"(?:PIC\s+S?9+V?9*|VALUE\s+)([\d,\.]+)", line, re.IGNORECASE)
            if m:
                val_str = m.group(1).replace(",", "")
                try:
                    val = float(val_str)
                    items.append(EvidenceItem(
                        parameter="smdia_limit", file_path=self.file_path,
                        line_number=lineno, raw_text=line.strip(),
                        extracted_value=val, extraction_method="cobol_data_item",
                        confidence="HIGH",
                    ))
                except ValueError:
                    pass

        # ── ORC type literals ────────────────────────────────────────────
        orc_found: set[str] = set()
        orc_lineno = 0
        orc_line_text = ""
        known_orcs = {"SGL", "JNT", "REV", "IRR", "BUS", "EBP", "CRA",
                      "GOV1", "GOV2", "GOV3", "ANC"}
        for lineno, line in self._find_lines(r"'\s*(?:SGL|JNT|REV|IRR|BUS|EBP|CRA|GOV1|GOV2|GOV3|ANC)\s*'"):
            for orc in known_orcs:
                if f"'{orc}'" in line or f'"{orc}"' in line:
                    orc_found.add(orc)
            if not orc_lineno:
                orc_lineno = lineno
                orc_line_text = line.strip()
        if orc_found:
            items.append(EvidenceItem(
                parameter="supported_orc_types", file_path=self.file_path,
                line_number=orc_lineno, raw_text=f"ORC literals found: {sorted(orc_found)}",
                extracted_value=orc_found, extraction_method="cobol_literal_scan",
                confidence="MEDIUM",  # may not be exhaustive
            ))

        # ── Aggregation check ────────────────────────────────────────────
        agg_hits = self._find_lines(r"(?:AGGREG|TOTAL[-\s]BY|SUM[-\s]DEPOSITOR|TOTAL-DEPOSITOR|GROUP[-\s]BY[-\s]ORC)")
        if agg_hits:
            agg_lineno, agg_line = agg_hits[0]
            items.append(EvidenceItem(
                parameter="aggregation_before_smdia", file_path=self.file_path,
                line_number=agg_lineno, raw_text=agg_line.strip(),
                extracted_value=True, extraction_method="cobol_keyword",
                confidence="MEDIUM",
            ))
        else:
            # No aggregation found — this is itself a finding
            items.append(EvidenceItem(
                parameter="aggregation_before_smdia", file_path=self.file_path,
                line_number=0, raw_text="(no aggregation-by-depositor pattern found in file)",
                extracted_value=False, extraction_method="cobol_keyword_absence",
                confidence="MEDIUM",
            ))

        # ── Close-of-business balance ────────────────────────────────────
        cob_hits = self._find_lines(r"(?:CLOSE-OF-BUSINESS|COB-BAL|END-OF-DAY|EOD-BAL)")
        items.append(EvidenceItem(
            parameter="close_of_business_balance", file_path=self.file_path,
            line_number=cob_hits[0][0] if cob_hits else 0,
            raw_text=cob_hits[0][1].strip() if cob_hits else "(no COB balance pattern found)",
            extracted_value=bool(cob_hits), extraction_method="cobol_keyword",
            confidence="MEDIUM",
        ))

        # ── Debt offset: credit card exclusion ──────────────────────────
        cc_hits = self._find_lines(r"(?:CREDIT-CARD|CARD-BAL|CC-BAL|CARD-DEBT)")
        items.append(EvidenceItem(
            parameter="debt_offset_excludes_credit_cards", file_path=self.file_path,
            line_number=cc_hits[0][0] if cc_hits else 0,
            raw_text=cc_hits[0][1].strip() if cc_hits else "(no credit-card exclusion pattern found)",
            extracted_value=bool(cc_hits), extraction_method="cobol_keyword",
            confidence="LOW",
        ))

        return items


class JavaExtractor(_FileExtractor):
    """Extracts from Java source files."""

    def extract(self) -> list[EvidenceItem]:
        items: list[EvidenceItem] = []

        # ── SMDIA / insurance limit constants ───────────────────────────
        for lineno, line in self._find_lines(
            r"(?:SMDIA|INSURANCE_LIMIT|MAX_INSURED|COVERAGE_LIMIT|smdiaLimit|maxInsured)"
        ):
            m = re.search(r"=\s*([\d_]+\.?\d*)[Lf]?\s*;", line)
            if m:
                val_str = m.group(1).replace("_", "")
                try:
                    items.append(EvidenceItem(
                        parameter="smdia_limit", file_path=self.file_path,
                        line_number=lineno, raw_text=line.strip(),
                        extracted_value=float(val_str),
                        extraction_method="java_constant",
                        confidence="HIGH",
                    ))
                except ValueError:
                    pass

        # ── ORC type handling in switch/if blocks ────────────────────────
        orc_found: set[str] = set()
        orc_lineno = 0
        known_orcs = {"SGL", "JNT", "REV", "IRR", "BUS", "EBP", "CRA",
                      "GOV1", "GOV2", "GOV3", "ANC"}
        for lineno, line in self._find_lines(
            r'"(?:SGL|JNT|REV|IRR|BUS|EBP|CRA|GOV1|GOV2|GOV3|ANC)"'
        ):
            for orc in known_orcs:
                if f'"{orc}"' in line:
                    orc_found.add(orc)
            if not orc_lineno:
                orc_lineno = lineno
        if orc_found:
            items.append(EvidenceItem(
                parameter="supported_orc_types", file_path=self.file_path,
                line_number=orc_lineno,
                raw_text=f"ORC literals in Java: {sorted(orc_found)}",
                extracted_value=orc_found, extraction_method="java_literal_scan",
                confidence="MEDIUM",
            ))

        # ── Aggregation ──────────────────────────────────────────────────
        agg_hits = self._find_lines(
            r"(?:aggregateByDepositor|groupByOrc|totalPerDepositor|sumByOrc|"
            r"aggregate\s*\(|GROUP\s+BY\s+depositor)"
        )
        items.append(EvidenceItem(
            parameter="aggregation_before_smdia", file_path=self.file_path,
            line_number=agg_hits[0][0] if agg_hits else 0,
            raw_text=agg_hits[0][1].strip() if agg_hits else "(no per-depositor aggregation found)",
            extracted_value=bool(agg_hits), extraction_method="java_method_scan",
            confidence="MEDIUM",
        ))

        # ── PII encryption ───────────────────────────────────────────────
        enc_hits = self._find_lines(
            r"(?:encrypt|AES|RSA|cipher|Cipher|encryptPii|maskPii|hashSsn)"
        )
        items.append(EvidenceItem(
            parameter="output_encrypt_pii", file_path=self.file_path,
            line_number=enc_hits[0][0] if enc_hits else 0,
            raw_text=enc_hits[0][1].strip() if enc_hits else "(no PII encryption found in Java)",
            extracted_value=bool(enc_hits), extraction_method="java_keyword",
            confidence="LOW",
        ))

        return items


class SqlExtractor(_FileExtractor):
    """Extracts from SQL stored procedures and schema files."""

    def extract(self) -> list[EvidenceItem]:
        items: list[EvidenceItem] = []

        # ── SMDIA in SQL constant/declare ───────────────────────────────
        for lineno, line in self._find_lines(
            r"(?:@SMDIA|@max_insured|@insurance_limit|v_smdia|v_max_insured|SMDIA|250000)",
        ):
            m = re.search(r"(?:=|:=)\s*([\d,]+\.?\d*)", line)
            if m:
                val_str = m.group(1).replace(",", "")
                try:
                    items.append(EvidenceItem(
                        parameter="smdia_limit", file_path=self.file_path,
                        line_number=lineno, raw_text=line.strip(),
                        extracted_value=float(val_str),
                        extraction_method="sql_variable",
                        confidence="HIGH",
                    ))
                except ValueError:
                    pass

        # ── Aggregation in SQL (GROUP BY depositor) ──────────────────────
        agg_hits = self._find_lines(
            r"(?:GROUP\s+BY\s+.*(depositor|customer|owner)|SUM\s*\(|aggregate)"
        )
        items.append(EvidenceItem(
            parameter="aggregation_before_smdia", file_path=self.file_path,
            line_number=agg_hits[0][0] if agg_hits else 0,
            raw_text=agg_hits[0][1].strip() if agg_hits else "(no GROUP BY depositor found in SQL)",
            extracted_value=bool(agg_hits), extraction_method="sql_keyword",
            confidence="MEDIUM",
        ))

        # ── Data retention (in years, months) ───────────────────────────
        for lineno, line in self._find_lines(r"retention|archive|purge|expire"):
            m = re.search(r"(\d+)\s*(?:YEAR|MONTH|YR|MO)", line, re.IGNORECASE)
            if m:
                val = int(m.group(1))
                if "MONTH" in line.upper() or "MO" in line.upper():
                    val = round(val / 12, 1)
                items.append(EvidenceItem(
                    parameter="data_retention_years", file_path=self.file_path,
                    line_number=lineno, raw_text=line.strip(),
                    extracted_value=val, extraction_method="sql_retention",
                    confidence="MEDIUM",
                ))

        return items


class PythonExtractor(_FileExtractor):
    """Extracts from Python source files."""

    def extract(self) -> list[EvidenceItem]:
        items: list[EvidenceItem] = []

        # ── SMDIA constant ───────────────────────────────────────────────
        for lineno, line in self._find_lines(r"(?:SMDIA|smdia|max_insured|insurance_limit)\s*="):
            m = re.search(r"=\s*([\d_,]+\.?\d*)", line)
            if m:
                try:
                    val = float(m.group(1).replace("_", "").replace(",", ""))
                    items.append(EvidenceItem(
                        parameter="smdia_limit", file_path=self.file_path,
                        line_number=lineno, raw_text=line.strip(),
                        extracted_value=val, extraction_method="python_constant",
                        confidence="HIGH",
                    ))
                except ValueError:
                    pass

        # ── ORC types in lists/sets/dicts ────────────────────────────────
        orc_found: set[str] = set()
        orc_lineno = 0
        known_orcs = {"SGL", "JNT", "REV", "IRR", "BUS", "EBP", "CRA",
                      "GOV1", "GOV2", "GOV3", "ANC"}
        for lineno, line in self._find_lines(
            r'"(?:SGL|JNT|REV|IRR|BUS|EBP|CRA|GOV1|GOV2|GOV3|ANC)"'
        ):
            for orc in known_orcs:
                if f'"{orc}"' in line or f"'{orc}'" in line:
                    orc_found.add(orc)
            if not orc_lineno:
                orc_lineno = lineno
        if orc_found:
            items.append(EvidenceItem(
                parameter="supported_orc_types", file_path=self.file_path,
                line_number=orc_lineno,
                raw_text=f"ORC values found: {sorted(orc_found)}",
                extracted_value=orc_found, extraction_method="python_literal_scan",
                confidence="MEDIUM",
            ))

        # ── Encryption ───────────────────────────────────────────────────
        enc_hits = self._find_lines(r"(?:encrypt|AES|Fernet|hashlib|bcrypt|mask_pii|encrypt_pii)")
        items.append(EvidenceItem(
            parameter="output_encrypt_pii", file_path=self.file_path,
            line_number=enc_hits[0][0] if enc_hits else 0,
            raw_text=enc_hits[0][1].strip() if enc_hits else "(no encryption found in Python file)",
            extracted_value=bool(enc_hits), extraction_method="python_keyword",
            confidence="LOW",
        ))

        # ── Aggregation  ─────────────────────────────────────────────────
        agg_hits = self._find_lines(r"(?:groupby|group_by|aggregate|sum_by_orc|total_per_depositor)")
        items.append(EvidenceItem(
            parameter="aggregation_before_smdia", file_path=self.file_path,
            line_number=agg_hits[0][0] if agg_hits else 0,
            raw_text=agg_hits[0][1].strip() if agg_hits else "(no aggregation pattern in Python)",
            extracted_value=bool(agg_hits), extraction_method="python_keyword",
            confidence="MEDIUM",
        ))

        return items


# ============================================================================
# Dispatch — pick the right extractor by file extension
# ============================================================================

_EXTRACTOR_MAP: dict[str, type[_FileExtractor]] = {
    ".properties": ConfigPropertiesExtractor,
    ".xml": ConfigPropertiesExtractor,
    ".yaml": ConfigPropertiesExtractor,
    ".yml": ConfigPropertiesExtractor,
    ".ini": ConfigPropertiesExtractor,
    ".cob": CobolExtractor,
    ".cpy": CobolExtractor,
    ".java": JavaExtractor,
    ".sql": SqlExtractor,
    ".py": PythonExtractor,
}


def _get_extractor(file_path: str, content: str) -> _FileExtractor | None:
    ext = Path(file_path).suffix.lower()
    cls = _EXTRACTOR_MAP.get(ext)
    if cls:
        return cls(file_path, content)
    return None


# ============================================================================
# Comparator — diff extracted value against FDIC requirement
# ============================================================================

def _compare(item: EvidenceItem, requirement: dict[str, Any]) -> EvidenceFinding:
    req_val = requirement["required_value"]
    code_val = item.extracted_value
    severity = requirement["severity"]
    regulation = requirement["regulation"]
    description = requirement["description"]

    is_compliant = False
    gap = ""
    remediation = ""

    # --- numeric comparison -----------------------------------------------
    if isinstance(req_val, (int, float)) and isinstance(code_val, (int, float)):
        is_compliant = abs(float(code_val) - float(req_val)) < 0.01
        if not is_compliant:
            direction = "higher" if float(code_val) > float(req_val) else "lower"
            unit = requirement.get("unit", "")
            gap = (
                f"Code value {code_val:,}{' ' + unit if unit else ''} "
                f"≠ required {req_val:,}{' ' + unit if unit else ''}. "
                f"Code is {direction} than the regulatory requirement."
            )
            if "smdia" in item.parameter:
                remediation = (
                    f"Update the insurance limit constant to $250,000 per "
                    f"{regulation}. Search for the literal value {code_val:,} "
                    f"in {item.file_path} and replace with 250000."
                )
            else:
                remediation = (
                    f"Update the value to match the {regulation} requirement of "
                    f"{req_val}. Review {item.file_path} line {item.line_number}."
                )

    # --- boolean comparison -----------------------------------------------
    elif isinstance(req_val, bool):
        is_compliant = bool(code_val) == req_val
        if not is_compliant:
            neg = "disabled" if not code_val else "unexpectedly enabled"
            gap = f"{description} is {neg} in {item.file_path}."
            remediation = (
                f"Enable the required feature per {regulation}. "
                f"Update {item.file_path} line {item.line_number}."
            )

    # --- string comparison ------------------------------------------------
    elif isinstance(req_val, str) and isinstance(code_val, str):
        is_compliant = code_val.strip().upper() == req_val.strip().upper()
        if not is_compliant:
            gap = (
                f"Code uses '{code_val}' but {regulation} requires '{req_val}'."
            )
            remediation = (
                f"Change the value from '{code_val}' to '{req_val}' "
                f"in {item.file_path} line {item.line_number}."
            )

    # --- set comparison (ORC types, pending codes) ------------------------
    elif isinstance(req_val, set) and isinstance(code_val, set):
        missing = req_val - code_val
        is_compliant = len(missing) == 0
        if not is_compliant:
            gap = (
                f"{len(missing)} required value(s) are missing from the code: "
                f"{sorted(missing)}. Only {sorted(code_val)} found."
            )
            remediation = (
                f"Implement the missing values {sorted(missing)} per {regulation}. "
                f"See {item.file_path} line {item.line_number} for existing implementation."
            )

    else:
        # Type mismatch or unknown — flag for manual review
        is_compliant = False
        gap = f"Unable to automatically compare code value '{code_val}' against required '{req_val}'."
        remediation = f"Manually review {item.file_path} line {item.line_number} against {regulation}."

    return EvidenceFinding(
        parameter=item.parameter,
        requirement_description=description,
        regulation=regulation,
        severity=severity,
        code_value=code_val,
        code_file=item.file_path,
        code_line=item.line_number,
        code_context=item.raw_text,
        required_value=req_val,
        is_compliant=is_compliant,
        gap_description=gap,
        remediation=remediation,
    )


# ============================================================================
# Main Analyzer Class
# ============================================================================

class Layer0EvidenceExtractor:
    """
    Scans operational system source files, extracts compliance-relevant
    values, and compares them directly against FDIC regulatory requirements.

    Returns a LayerScanResult whose findings contain:
      - file + line where the value was found
      - what value was found
      - what FDIC requires
      - the gap / remediation
    """

    def scan(
        self,
        source_files: dict[str, str],  # {relative_path: file_content}
    ) -> LayerScanResult:
        """
        source_files: dict mapping relative file path → full file content.
        Typically loaded by the pipeline from operational_systems/{system}/
        """
        all_evidence: list[EvidenceItem] = []

        # ── Step 1: Extract evidence from every source file ──────────────
        for file_path, content in source_files.items():
            extractor = _get_extractor(file_path, content)
            if extractor:
                try:
                    items = extractor.extract()
                    all_evidence.extend(items)
                except Exception:
                    pass

        # ── Step 2: Pick the most specific evidence per parameter ─────────
        # When multiple files define the same parameter (e.g. SMDIA in both
        # COBOL and config), prefer HIGH confidence; prefer config > cobol > java
        # for numeric values (config is most authoritative).
        best_evidence: dict[str, EvidenceItem] = {}
        for item in all_evidence:
            existing = best_evidence.get(item.parameter)
            if existing is None:
                best_evidence[item.parameter] = item
            else:
                # Prefer set > numeric > bool (more specific)
                if isinstance(item.extracted_value, set) and not isinstance(existing.extracted_value, set):
                    best_evidence[item.parameter] = item
                elif item.confidence == "HIGH" and existing.confidence != "HIGH":
                    best_evidence[item.parameter] = item
                elif isinstance(item.extracted_value, (int, float)) and \
                     isinstance(existing.extracted_value, (int, float)):
                    # Take the one from config files as more authoritative
                    if ".properties" in item.file_path or ".xml" in item.file_path:
                        best_evidence[item.parameter] = item

        # ── Step 3: Compare every extracted value against FDIC requirement ─
        evidence_findings: list[EvidenceFinding] = []
        for param, item in best_evidence.items():
            req = FDIC_REQUIREMENTS.get(param)
            if req:
                finding = _compare(item, req)
                evidence_findings.append(finding)

        # ── Step 4: Flag parameters with NO code evidence at all ──────────
        for param, req in FDIC_REQUIREMENTS.items():
            if param not in best_evidence:
                evidence_findings.append(EvidenceFinding(
                    parameter=param,
                    requirement_description=req["description"],
                    regulation=req["regulation"],
                    severity=req["severity"],
                    code_value=None,
                    code_file="(not found)",
                    code_line=0,
                    code_context="No code evidence found for this parameter in any scanned file.",
                    required_value=req["required_value"],
                    is_compliant=False,
                    gap_description=(
                        f"No implementation of '{req['description']}' found in "
                        f"the scanned source files. Either the feature is absent "
                        f"or uses non-standard naming patterns."
                    ),
                    remediation=(
                        f"Implement '{req['description']}' per {req['regulation']}. "
                        f"{req.get('notes', '')}"
                    ),
                ))

        # ── Step 5: Convert EvidenceFindings to ComplianceFinding objects ──
        findings: list[ComplianceFinding] = []
        for ef in evidence_findings:
            if ef.is_compliant:
                continue  # only emit findings for non-compliant items

            sev_map = {
                Severity.CRITICAL: "CRITICAL",
                Severity.HIGH: "HIGH",
                Severity.MEDIUM: "MEDIUM",
                Severity.LOW: "LOW",
                Severity.INFO: "INFO",
            }

            code_val_display = (
                f"${ef.code_value:,.2f}" if isinstance(ef.code_value, float) and "smdia" in ef.parameter
                else (str(sorted(ef.code_value)) if isinstance(ef.code_value, set) else str(ef.code_value))
            )
            req_val_display = (
                f"${ef.required_value:,.2f}" if isinstance(ef.required_value, float) and "smdia" in ef.parameter
                else (str(sorted(ef.required_value)) if isinstance(ef.required_value, set) else str(ef.required_value))
            )

            title = f"[{ef.parameter.upper()}] {ef.requirement_description}"
            description = (
                f"REGULATION: {ef.regulation}\n"
                f"FILE: {ef.code_file}"
                + (f"  LINE: {ef.code_line}" if ef.code_line else "") + "\n"
                f"CODE VALUE: {code_val_display}\n"
                f"REQUIRED:   {req_val_display}\n"
                f"GAP: {ef.gap_description}\n"
                f"CODE EVIDENCE: {ef.code_context}"
            )

            findings.append(ComplianceFinding(
                layer=AnalyzerLayer.LAYER1_ORC_STATIC,  # reuse existing enum; Layer 0 pre-analysis
                finding_id=f"L0-{ef.parameter.upper().replace('_', '-')}",
                title=title,
                description=description,
                cfr_reference=ef.regulation,
                severity=Severity[sev_map[ef.severity]],
                remediation_recommendation=ef.remediation,
                source_file=ef.code_file if ef.code_file != "(not found)" else "",
                line_number=ef.code_line,
                code_snippet=ef.code_context[:200] if ef.code_context else "",
                evidence={
                    "parameter": ef.parameter,
                    "code_value": str(ef.code_value),
                    "required_value": str(ef.required_value),
                    "code_file": ef.code_file,
                    "code_line": ef.code_line,
                    "code_context": ef.code_context,
                    "gap": ef.gap_description,
                    "all_evidence_items": [
                        {
                            "file": e.file_path,
                            "line": e.line_number,
                            "value": str(e.extracted_value),
                            "method": e.extraction_method,
                            "context": e.raw_text,
                        }
                        for e in all_evidence if e.parameter == ef.parameter
                    ],
                },
            ))

        # ── Step 6: Build summary ─────────────────────────────────────────
        scanned_types: dict[str, int] = {}
        for fp in source_files:
            ext = Path(fp).suffix.lower().lstrip(".")
            scanned_types[ext] = scanned_types.get(ext, 0) + 1

        total_parameters = len(FDIC_REQUIREMENTS)
        compliant_count = total_parameters - len(findings)
        params_found = len(best_evidence)

        return LayerScanResult(
            layer=AnalyzerLayer.LAYER1_ORC_STATIC,
            findings=findings,
            summary=(
                f"Scanned {len(source_files)} files ({', '.join(f'{v} .{k}' for k, v in scanned_types.items())}). "
                f"Checked {total_parameters} FDIC regulatory parameters: "
                f"{compliant_count} compliant, {len(findings)} with findings. "
                f"{len(all_evidence)} evidence items extracted from source code."
            ),
            metrics={
                "files_scanned": len(source_files),
                "evidence_items": len(all_evidence),
                "compliance_rate_pct": round(compliant_count / total_parameters * 100, 1),
            },
        )


# ── CLI entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import pathlib, json

    repo_root = pathlib.Path(__file__).resolve().parents[2]
    systems_root = repo_root / "operational_systems"

    # Collect every source file under operational_systems/ as {str_path: content}
    source_files: dict[str, str] = {}
    for p in sorted(
        q for q in systems_root.rglob("*")
        if q.is_file() and q.suffix in {
            ".cob", ".cpy", ".java", ".py", ".sql", ".sh", ".jcl",
            ".properties", ".xml", ".csv",
        }
    ):
        try:
            source_files[str(p)] = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            pass

    print("=" * 70)
    print("  Layer 0 — Evidence Extractor")
    print(f"  Scanning {len(source_files)} files under operational_systems/")
    print("=" * 70)

    analyzer = Layer0EvidenceExtractor()
    result = analyzer.scan(source_files=source_files)

    # ── Summary line ──────────────────────────────────────────────────────────
    status_label = "PASS" if result.passed else "FINDINGS"
    print(f"\nStatus  : {status_label}")
    print(f"Files   : {result.metrics.get('files_scanned', 0)}")
    print(f"Evidence: {result.metrics.get('evidence_items', 0)} parameters extracted")
    print(f"Coverage: {result.metrics.get('compliance_rate_pct', 0):.1f}% compliant")
    print(f"Findings: {len(result.findings)}")

    if not result.findings:
        print("\nNo findings.")
    else:
        # ── Per-finding table ─────────────────────────────────────────────────
        SEV_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        sorted_findings = sorted(
            result.findings,
            key=lambda f: (SEV_ORDER.get(f.severity.value, 9), f.title),
        )

        print(f"\n{'#':<4} {'SEV':<10} {'TITLE':<42} {'CODE VALUE':<20} {'FILE'}")
        print("-" * 115)
        for i, f in enumerate(sorted_findings, 1):
            ev = f.evidence or {}
            code_val = str(ev.get("code_value", "—"))[:18]
            loc = f.source_file or ev.get("code_file") or "—"
            line = f.line_number or ev.get("code_line")
            loc = f"{loc}:{line}" if line else loc
            loc = loc[-40:]  # keep rightmost chars for long paths
            title = f.title[:40]
            print(f"{i:<4} {f.severity.value:<10} {title:<42} {code_val:<20} {loc}")

        # ── Gaps only ─────────────────────────────────────────────────────────
        gaps = [f for f in sorted_findings if (f.evidence or {}).get("gap")]
        if gaps:
            print(f"\n── {len(gaps)} Parameters with FDIC gaps ────────────────────────────")
            for f in gaps:
                ev = f.evidence or {}
                print(f"  • {f.title}")
                print(f"      Found   : {ev.get('code_value', '—')}")
                print(f"      Required: {ev.get('required_value', '—')}")
                print(f"      Gap     : {ev.get('gap', '')}")
