"""
LangGraph Orchestrator -- 6-Layer FDIC Part 370 Compliance Pipeline
====================================================================

    [START]
       |
       v
    layer1_orc_static        -- ORC Assignment Logic Analysis
       |
       v
    layer2_data_completeness -- Orphan + ORC-Conditional Validation
       |
       v
    layer3_calc_engine       -- Calculation Engine Verification
       |
       v
    layer4_output_pipeline   -- Output File Integrity
       |
       v
    layer5_behavioral        -- Runtime / Throughput Testing
       |
       v
    layer6_certification     -- Certification Artifact Generation
       |
       v
    [END]

State flows through each node accumulating findings and metrics.
"""
from __future__ import annotations

import os
from datetime import date, datetime
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from backend.core.models import (
    DepositAccount,
    AccountParticipant,
    AREFileRecord,
    CustomerRecord,
    FullPipelineResult,
    InsuranceCalculationResult,
    LayerScanResult,
)
from backend.layers.layer1_orc_static import Layer1ORCStaticAnalyzer
from backend.layers.layer2_data_completeness import Layer2DataCompletenessAnalyzer
from backend.layers.layer3_calc_engine import Layer3CalcEngineAnalyzer
from backend.layers.layer4_output_pipeline import Layer4OutputPipelineAnalyzer
from backend.layers.layer5_behavioral import Layer5BehavioralAnalyzer
from backend.layers.layer6_certification import Layer6CertificationGenerator


# ── Pipeline State ─────────────────────────────────────────────────────────────

class PipelineState(TypedDict, total=False):
    # Input data
    accounts: list[DepositAccount]
    customers: list[CustomerRecord]
    participants: list[AccountParticipant]
    are_files: list[AREFileRecord]
    orc_assignment_code: str
    pending_routing_code: str
    calc_engine_code: str
    output_generation_code: str
    analysis_date: str  # ISO format
    institution_name: str

    # Accumulated results
    layer_results: list[dict[str, Any]]
    calc_results: list[dict[str, Any]]

    # Control
    error: str


# ── Node Functions ─────────────────────────────────────────────────────────────

def _node_layer1(state: PipelineState) -> PipelineState:
    print("\n" + "=" * 60)
    print(" LAYER 1/6 -- ORC Assignment Logic Static Analysis")
    print("=" * 60)

    analyzer = Layer1ORCStaticAnalyzer()
    result = analyzer.scan(
        orc_assignment_code=state.get("orc_assignment_code", ""),
        pending_routing_code=state.get("pending_routing_code", ""),
    )

    print(f" -> {len(result.findings)} findings ({result.critical_count} critical)")

    results = list(state.get("layer_results", []))
    results.append(result.model_dump())
    return {**state, "layer_results": results}


def _node_layer2(state: PipelineState) -> PipelineState:
    print("\n" + "=" * 60)
    print(" LAYER 2/6 -- Data Completeness and Validation")
    print("=" * 60)

    accounts = state.get("accounts", [])
    customers = state.get("customers", [])
    participants = state.get("participants", [])
    analysis_date = None
    if state.get("analysis_date"):
        analysis_date = date.fromisoformat(state["analysis_date"])

    analyzer = Layer2DataCompletenessAnalyzer()
    result = analyzer.scan(
        accounts=accounts,
        customers=customers,
        participants=participants,
        analysis_date=analysis_date,
    )

    print(f" -> {len(result.findings)} findings ({result.critical_count} critical)")

    results = list(state.get("layer_results", []))
    results.append(result.model_dump())
    return {**state, "layer_results": results}


def _node_layer3(state: PipelineState) -> PipelineState:
    print("\n" + "=" * 60)
    print(" LAYER 3/6 -- Calculation Engine Verification")
    print("=" * 60)

    accounts = state.get("accounts", [])
    analysis_date = None
    if state.get("analysis_date"):
        analysis_date = date.fromisoformat(state["analysis_date"])

    analyzer = Layer3CalcEngineAnalyzer()
    result = analyzer.scan(
        accounts=accounts,
        analysis_date=analysis_date,
        calc_engine_code=state.get("calc_engine_code", ""),
    )

    # Store the correct calculation results for downstream layers
    calc_results = []
    if hasattr(analyzer, '_perform_correct_aggregation'):
        from backend.layers.layer3_calc_engine import Layer3CalcEngineAnalyzer as L3
        calc = L3()
        correct = calc._perform_correct_aggregation(accounts, analysis_date or date.today())
        calc_results = [r.model_dump() for r in correct]

    print(f" -> {len(result.findings)} findings ({result.critical_count} critical)")

    results = list(state.get("layer_results", []))
    results.append(result.model_dump())
    return {**state, "layer_results": results, "calc_results": calc_results}


def _node_layer4(state: PipelineState) -> PipelineState:
    print("\n" + "=" * 60)
    print(" LAYER 4/6 -- Output File Pipeline Integrity")
    print("=" * 60)

    accounts = state.get("accounts", [])
    customers = state.get("customers", [])
    participants = state.get("participants", [])
    are_files = state.get("are_files", [])

    # Reconstruct calc results
    calc_results_raw = state.get("calc_results", [])
    calc_results = [InsuranceCalculationResult(**r) for r in calc_results_raw] if calc_results_raw else None

    analyzer = Layer4OutputPipelineAnalyzer()
    result = analyzer.scan(
        accounts=accounts,
        customers=customers,
        participants=participants,
        calc_results=calc_results,
        are_files=are_files if are_files else None,
        output_generation_code=state.get("output_generation_code", ""),
    )

    print(f" -> {len(result.findings)} findings ({result.critical_count} critical)")

    results = list(state.get("layer_results", []))
    results.append(result.model_dump())
    return {**state, "layer_results": results}


def _node_layer5(state: PipelineState) -> PipelineState:
    print("\n" + "=" * 60)
    print(" LAYER 5/6 -- Behavioral / Runtime Compliance")
    print("=" * 60)

    accounts = state.get("accounts", [])

    analyzer = Layer5BehavioralAnalyzer()
    result = analyzer.scan(
        accounts=accounts,
        # In demo mode, provide estimated times for a large institution
        estimated_restriction_seconds=45.0,
        estimated_output_gen_seconds=3600.0,
        failover_available=True,
        failover_snapshot_age_seconds=120.0,
    )

    print(f" -> {len(result.findings)} findings ({result.critical_count} critical)")

    results = list(state.get("layer_results", []))
    results.append(result.model_dump())
    return {**state, "layer_results": results}


def _node_layer6(state: PipelineState) -> PipelineState:
    print("\n" + "=" * 60)
    print(" LAYER 6/6 -- Certification Artifact Generation")
    print("=" * 60)

    accounts = state.get("accounts", [])
    customers = state.get("customers", [])
    institution = state.get("institution_name", "Covered Institution")

    # Reconstruct prior LayerScanResults for the test log
    prior_results: list[LayerScanResult] = []
    for raw in state.get("layer_results", []):
        try:
            prior_results.append(LayerScanResult(**raw))
        except Exception:
            pass

    # Reconstruct calc results
    calc_results_raw = state.get("calc_results", [])
    calc_results = [InsuranceCalculationResult(**r) for r in calc_results_raw] if calc_results_raw else None

    generator = Layer6CertificationGenerator(institution_name=institution)
    result = generator.scan(
        accounts=accounts,
        customers=customers,
        calc_results=calc_results,
        prior_layer_results=prior_results,
    )

    print(f" -> {len(result.findings)} findings ({result.critical_count} critical)")

    results = list(state.get("layer_results", []))
    results.append(result.model_dump())
    return {**state, "layer_results": results}


# ── Build Graph ────────────────────────────────────────────────────────────────

def _build_graph() -> StateGraph:
    g = StateGraph(PipelineState)

    g.add_node("layer1_orc_static",        _node_layer1)
    g.add_node("layer2_data_completeness", _node_layer2)
    g.add_node("layer3_calc_engine",       _node_layer3)
    g.add_node("layer4_output_pipeline",   _node_layer4)
    g.add_node("layer5_behavioral",        _node_layer5)
    g.add_node("layer6_certification",     _node_layer6)

    g.add_edge(START,                      "layer1_orc_static")
    g.add_edge("layer1_orc_static",        "layer2_data_completeness")
    g.add_edge("layer2_data_completeness", "layer3_calc_engine")
    g.add_edge("layer3_calc_engine",       "layer4_output_pipeline")
    g.add_edge("layer4_output_pipeline",   "layer5_behavioral")
    g.add_edge("layer5_behavioral",        "layer6_certification")
    g.add_edge("layer6_certification",     END)

    return g


# ── Public API ─────────────────────────────────────────────────────────────────

def run_full_pipeline(
    accounts: list[DepositAccount] | None = None,
    customers: list[CustomerRecord] | None = None,
    participants: list[AccountParticipant] | None = None,
    are_files: list[AREFileRecord] | None = None,
    orc_assignment_code: str = "",
    pending_routing_code: str = "",
    calc_engine_code: str = "",
    output_generation_code: str = "",
    institution_name: str = "Covered Institution",
) -> dict[str, Any]:
    """
    Execute the complete 6-layer FDIC Part 370 compliance pipeline.

    If no data is provided, uses built-in sample data with intentional
    compliance gaps for demonstration.
    """
    from dotenv import load_dotenv
    load_dotenv()

    # Use sample data if nothing provided
    if accounts is None:
        from backend.core.sample_data import (
            build_sample_accounts,
            build_sample_customers,
            build_sample_participants,
            build_sample_are_files,
            SAMPLE_ORC_ASSIGNMENT_CODE,
            SAMPLE_CALCULATION_CODE,
            SAMPLE_PENDING_ROUTING_CODE,
            SAMPLE_OUTPUT_GENERATION_CODE,
        )
        accounts = build_sample_accounts()
        customers = customers or build_sample_customers()
        participants = participants or build_sample_participants()
        are_files = are_files or build_sample_are_files()
        orc_assignment_code = orc_assignment_code or SAMPLE_ORC_ASSIGNMENT_CODE
        pending_routing_code = pending_routing_code or SAMPLE_PENDING_ROUTING_CODE
        calc_engine_code = calc_engine_code or SAMPLE_CALCULATION_CODE
        output_generation_code = output_generation_code or SAMPLE_OUTPUT_GENERATION_CODE

    initial_state: PipelineState = {
        "accounts": accounts,
        "customers": customers or [],
        "participants": participants or [],
        "are_files": are_files or [],
        "orc_assignment_code": orc_assignment_code,
        "pending_routing_code": pending_routing_code,
        "calc_engine_code": calc_engine_code,
        "output_generation_code": output_generation_code,
        "analysis_date": date.today().isoformat(),
        "institution_name": institution_name,
        "layer_results": [],
        "calc_results": [],
        "error": "",
    }

    print("\n")
    print("+" + "=" * 62 + "+")
    print("|  KRATOS CODE ANALYZER -- FDIC Part 370 Compliance Pipeline  |")
    print("|  6-Layer Deep Analysis per 12 CFR Part 330 / IT Guide v3.0 |")
    print("+" + "=" * 62 + "+")
    print(f"|  Institution: {institution_name:<47} |")
    print(f"|  Accounts:    {len(accounts):<47} |")
    print(f"|  Date:        {date.today().isoformat():<47} |")
    print("+" + "=" * 62 + "+")

    graph = _build_graph()
    app = graph.compile()
    final_state: PipelineState = app.invoke(initial_state)

    # Compute summary
    all_findings = []
    for lr in final_state.get("layer_results", []):
        all_findings.extend(lr.get("findings", []))

    total = len(all_findings)
    critical = sum(1 for f in all_findings if f.get("severity") == "CRITICAL")
    high = sum(1 for f in all_findings if f.get("severity") == "HIGH")

    print("\n")
    print("+" + "=" * 62 + "+")
    print(f"|  PIPELINE COMPLETE                                         |")
    print(f"|  Total findings: {total:<44} |")
    print(f"|  Critical:       {critical:<44} |")
    print(f"|  High:           {high:<44} |")
    print("+" + "=" * 62 + "+")

    return final_state
