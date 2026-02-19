from pydantic import BaseModel
from typing import List, Optional, Dict


class InlineControl(BaseModel):
    regulation: str
    section: str
    title: str
    description: str
    evidence_snippet: str
    confidence: str


class NarrativeSection(BaseModel):
    heading: str
    explanation: str


class FileAnalysis(BaseModel):
    filename: str
    language: str
    lines_of_code: int
    regulatory_focus: List[str]
    summary: str
    narrative_sections: List[NarrativeSection]
    inline_controls: List[InlineControl]
    qualitative_risk: str
    reasoning_trace: List[str]
    analysis_duration_ms: int


class RepoAnalysis(BaseModel):
    repo: str
    branch: str
    files_analyzed: int
    total_loc: int
    qualitative_risk: str
    overall_summary: str
    per_file: List[FileAnalysis]
    language_counts: Dict[str, int]
    category_counts: Dict[str, int]
