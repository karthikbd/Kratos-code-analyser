# from pydantic import BaseModel
# from typing import List, Optional, Dict


# class InlineControl(BaseModel):
#     regulation: str
#     section: str
#     title: str
#     description: str
#     evidence_snippet: str
#     confidence: str


# class NarrativeSection(BaseModel):
#     heading: str
#     explanation: str


# class FileAnalysis(BaseModel):
#     filename: str
#     language: str
#     lines_of_code: int
#     regulatory_focus: List[str]
#     summary: str
#     narrative_sections: List[NarrativeSection]
#     inline_controls: List[InlineControl]
#     qualitative_risk: str
#     reasoning_trace: List[str]
#     analysis_duration_ms: int


# class RepoAnalysis(BaseModel):
#     repo: str
#     branch: str
#     files_analyzed: int
#     total_loc: int
#     qualitative_risk: str
#     overall_summary: str
#     per_file: List[FileAnalysis]
#     language_counts: Dict[str, int]
#     category_counts: Dict[str, int]

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Dict, List


# ---------------------------------------------------------------------------
# Legacy inline-control models (used by original per-file descriptive analysis)
# ---------------------------------------------------------------------------

class InlineControl(BaseModel):
    regulation: str
    section: str
    title: str
    control_statement: str
    code_excerpt: str
    line_start: int
    line_end: int


class NarrativeSection(BaseModel):
    heading: str
    explanation: str


class FileAnalysis(BaseModel):
    filename: str
    language: str
    lines_of_code: int
    regulatory_focus: List[str]
    technical_findings_count: int
    inline_controls_count: int
    summary: str
    narrative_sections: List[NarrativeSection]
    reasoning_trace: List[str]
    inline_controls: List[InlineControl]
    missing_controls: List[str]
    qualitative_risk: str = "Moderate"
    analysis_duration_ms: int


class RepoAnalysis(BaseModel):
    repo: str
    branch: str
    files_analyzed: int
    total_loc: int
    total_inline_controls: int
    total_regulations_referenced: int
    overall_summary: str
    per_file: List[FileAnalysis]
    language_counts: Dict[str, int]
    category_counts: Dict[str, int]
    lineage: List[Dict[str, str]]
    missing_controls_summary: Dict[str, List[str]]


# ---------------------------------------------------------------------------
# FDIC 12 CFR Part 370 Compliance Analysis models
# ---------------------------------------------------------------------------

class FDICEvidenceItem(BaseModel):
    signal: str
    file: str
    start_line: int
    end_line: int
    snippet: str
    explanation: str


class FDICControlFinding(BaseModel):
    control_id: str
    section: str                        # rule_type formatted e.g. "Control Requirement"
    title: str
    intent: str
    control_type: str = ""              # Preventive | Detective | Corrective
    applicable_fields: List[str] = Field(default_factory=list)
    status: str                         # PASS | PARTIAL | FAIL
    severity: str                       # Severe | High | Medium | Low
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: List[FDICEvidenceItem] = Field(default_factory=list)
    gap: str = ""
    remediation: str = ""


class FDICCoverageStats(BaseModel):
    total_controls: int
    pass_count: int
    partial_count: int
    fail_count: int
    compliance_pct: float               # 0-100


class FDICExecutiveSummary(BaseModel):
    posture: str                        # Severe | High | Medium | Low
    top_critical_gaps: List[str]
    immediate_priorities: List[str]


class FDICCodeLineageEdge(BaseModel):
    source: str                         # module:function
    target: str
    description: str


class FDICDataLineageNode(BaseModel):
    id: str
    label: str
    type: str                           # source | transform | target
    details: str = ""


class FDICDataLineageEdge(BaseModel):
    from_node: str = Field(alias="from")
    to_node: str   = Field(alias="to")
    label: str = ""

    model_config = {"populate_by_name": True}


class FDICDataLineage(BaseModel):
    nodes: List[FDICDataLineageNode] = Field(default_factory=list)
    edges: List[FDICDataLineageEdge] = Field(default_factory=list)


class FDICRemediationItem(BaseModel):
    priority: int
    action: str
    control_ids: List[str] = Field(default_factory=list)
    rationale: str = ""


class FDICRemediationPlan(BaseModel):
    phase1_critical: List[FDICRemediationItem]
    phase2_structural: List[FDICRemediationItem]
    phase3_governance: List[FDICRemediationItem]


class FDIC370Analysis(BaseModel):
    # Input metadata
    files_analyzed: int
    total_loc: int
    languages: List[str]

    # Analysis outputs
    executive_summary: FDICExecutiveSummary
    coverage_stats: FDICCoverageStats
    control_findings: List[FDICControlFinding]
    code_lineage: List[FDICCodeLineageEdge]
    data_lineage: FDICDataLineage
    remediation_plan: FDICRemediationPlan

    # Timing
    analysis_duration_ms: int
