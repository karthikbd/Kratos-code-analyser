from typing import TypedDict, List, Dict, Any


class AgentState(TypedDict):
    filename: str
    language: str
    source_code: str

    question: str
    regulation_context: List[str]

    ast_summary: Dict[str, Any]
    heuristics: Dict[str, Any]

    narrative: str
    narrative_sections: List[Dict[str, Any]]
    inline_controls: List[Dict[str, Any]]
    qualitative_risk: str
    reasoning_trace: List[str]
