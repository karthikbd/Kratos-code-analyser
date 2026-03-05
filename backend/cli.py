"""
Kratos Code Analyzer - CLI
============================
Typer-based CLI for the FDIC Part 370 Deep Code Analyzer.

Commands:
  analyze        Run all 6 layers with sample data
  scan           Run a single layer (1-6)
  certify        Run only Layer 6 -- certification artifact generation
  full-pipeline  Run all 6 layers with GPT-enhanced remediation advice
  report         Display a formatted compliance report from prior results
  benchmark      Run Layer 5 behavioral benchmarks only
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from backend.core.models import (
    AnalyzerLayer,
    Severity,
)

app = typer.Typer(
    name="kratos",
    help="Kratos Code Analyzer -- FDIC Part 370 Deep Compliance Scanner",
    add_completion=False,
    no_args_is_help=True,
)
console = Console()


# ── Helper ─────────────────────────────────────────────────────────────────────

def _severity_color(severity: str) -> str:
    return {
        "CRITICAL": "bold red",
        "HIGH": "red",
        "MEDIUM": "yellow",
        "LOW": "cyan",
        "INFO": "dim",
    }.get(severity, "white")


def _render_layer_result(raw: dict, layer_num: int) -> None:
    """Pretty-print one layer's findings."""
    layer_name = raw.get("layer", f"Layer {layer_num}")
    findings = raw.get("findings", [])

    table = Table(
        title=f"Layer {layer_num}: {layer_name}",
        show_lines=True,
        expand=True,
    )
    table.add_column("#", width=4, justify="right")
    table.add_column("Severity", width=10)
    table.add_column("Rule ID", width=14)
    table.add_column("Description", ratio=3)
    table.add_column("Regulation", width=20)
    table.add_column("Status", width=14)

    if not findings:
        console.print(f"  [green]No findings for {layer_name}.[/green]")
        return

    for i, f in enumerate(findings, 1):
        sev = f.get("severity", "INFO")
        table.add_row(
            str(i),
            Text(sev, style=_severity_color(sev)),
            f.get("rule_id", ""),
            f.get("description", ""),
            f.get("regulation_reference", ""),
            f.get("status", "OPEN"),
        )

    console.print(table)

    critical = sum(1 for f in findings if f.get("severity") == "CRITICAL")
    high = sum(1 for f in findings if f.get("severity") == "HIGH")
    medium = sum(1 for f in findings if f.get("severity") == "MEDIUM")
    low = sum(1 for f in findings if f.get("severity") == "LOW")
    info = sum(1 for f in findings if f.get("severity") == "INFO")

    console.print(
        f"  [bold]Summary[/bold]: "
        f"[red]{critical} CRITICAL[/red] | "
        f"[red]{high} HIGH[/red] | "
        f"[yellow]{medium} MEDIUM[/yellow] | "
        f"[cyan]{low} LOW[/cyan] | "
        f"[dim]{info} INFO[/dim]"
    )
    console.print()


def _render_full_report(state: dict) -> None:
    """Render all layer results from a pipeline state dict."""
    layer_results = state.get("layer_results", [])

    console.print()
    console.print(Panel.fit(
        "[bold blue]KRATOS CODE ANALYZER[/bold blue]\n"
        "[dim]FDIC Part 370 Deep Compliance Report[/dim]",
        border_style="blue",
    ))
    console.print()

    for i, lr in enumerate(layer_results, 1):
        _render_layer_result(lr, i)

    # Overall summary
    all_findings = []
    for lr in layer_results:
        all_findings.extend(lr.get("findings", []))

    total = len(all_findings)
    critical = sum(1 for f in all_findings if f.get("severity") == "CRITICAL")
    high = sum(1 for f in all_findings if f.get("severity") == "HIGH")

    verdict_color = "red" if critical > 0 else ("yellow" if high > 0 else "green")
    verdict = "FAIL" if critical > 0 else ("REVIEW" if high > 0 else "PASS")

    console.print(Panel(
        f"[bold]Total Findings: {total}  |  "
        f"Critical: {critical}  |  High: {high}[/bold]\n\n"
        f"[{verdict_color}]Compliance Verdict: {verdict}[/{verdict_color}]",
        title="[bold]Pipeline Summary[/bold]",
        border_style=verdict_color,
    ))


# ── Commands ───────────────────────────────────────────────────────────────────

@app.command()
def analyze(
    institution: str = typer.Option("Covered Institution", help="Institution name"),
    output: Optional[Path] = typer.Option(None, help="Save results JSON to file"),
):
    """Run all 6 compliance layers with sample data."""
    console.print("[bold blue]Starting 6-layer FDIC Part 370 analysis...[/bold blue]")

    from backend.agents.orchestrator import run_full_pipeline
    state = run_full_pipeline(institution_name=institution)

    _render_full_report(state)

    if output:
        output.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")
        console.print(f"\n[green]Results saved to {output}[/green]")


@app.command()
def scan(
    layer: int = typer.Argument(..., min=1, max=6, help="Layer number (1-6)"),
    institution: str = typer.Option("Covered Institution", help="Institution name"),
):
    """Run a single analysis layer (1-6)."""
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
    customers = build_sample_customers()
    participants = build_sample_participants()
    are_files = build_sample_are_files()

    console.print(f"[bold blue]Running Layer {layer} only...[/bold blue]")

    if layer == 1:
        from backend.layers.layer1_orc_static import Layer1ORCStaticAnalyzer
        result = Layer1ORCStaticAnalyzer().scan(
            SAMPLE_ORC_ASSIGNMENT_CODE, SAMPLE_PENDING_ROUTING_CODE
        )
    elif layer == 2:
        from backend.layers.layer2_data_completeness import Layer2DataCompletenessAnalyzer
        result = Layer2DataCompletenessAnalyzer().scan(
            accounts, customers, participants, date.today()
        )
    elif layer == 3:
        from backend.layers.layer3_calc_engine import Layer3CalcEngineAnalyzer
        result = Layer3CalcEngineAnalyzer().scan(
            accounts, date.today(), SAMPLE_CALCULATION_CODE
        )
    elif layer == 4:
        from backend.layers.layer4_output_pipeline import Layer4OutputPipelineAnalyzer
        result = Layer4OutputPipelineAnalyzer().scan(
            accounts, customers, participants, None, are_files,
            SAMPLE_OUTPUT_GENERATION_CODE,
        )
    elif layer == 5:
        from backend.layers.layer5_behavioral import Layer5BehavioralAnalyzer
        result = Layer5BehavioralAnalyzer().scan(
            accounts=accounts,
            estimated_restriction_seconds=45.0,
            estimated_output_gen_seconds=3600.0,
            failover_available=True,
            failover_snapshot_age_seconds=120.0,
        )
    elif layer == 6:
        from backend.layers.layer6_certification import Layer6CertificationGenerator
        result = Layer6CertificationGenerator(institution_name=institution).scan(
            accounts, customers, None, [],
        )
    else:
        console.print("[red]Invalid layer number.[/red]")
        raise typer.Exit(1)

    _render_layer_result(result.model_dump(), layer)


@app.command()
def certify(
    institution: str = typer.Option("Covered Institution", help="Institution name"),
    output: Optional[Path] = typer.Option(None, help="Save certification JSON"),
):
    """Generate compliance certification artifacts (Layer 6)."""
    console.print(f"[bold blue]Generating certification for {institution}...[/bold blue]")

    from backend.core.sample_data import (
        build_sample_accounts,
        build_sample_customers,
    )
    from backend.layers.layer6_certification import Layer6CertificationGenerator

    accounts = build_sample_accounts()
    customers = build_sample_customers()

    gen = Layer6CertificationGenerator(institution_name=institution)
    result = gen.scan(accounts, customers, None, [])

    _render_layer_result(result.model_dump(), 6)

    # Show certification report if available
    if gen._certification_report:
        report = gen._certification_report
        console.print(Panel(
            f"[bold]Institution:[/bold] {report.institution_name}\n"
            f"[bold]Analysis Date:[/bold] {report.analysis_date}\n"
            f"[bold]Total Accounts:[/bold] {report.total_accounts_analyzed}\n"
            f"[bold]Pending Count:[/bold] {report.pending_count}",
            title="[bold]Certification Report[/bold]",
            border_style="blue",
        ))

        if report.orc_completeness_scores:
            orc_table = Table(title="ORC Completeness Scores")
            orc_table.add_column("ORC Type")
            orc_table.add_column("Total")
            orc_table.add_column("Complete")
            orc_table.add_column("Score", justify="right")
            for score in report.orc_completeness_scores:
                pct = (
                    f"{score.complete_count / score.total_accounts * 100:.1f}%"
                    if score.total_accounts > 0
                    else "N/A"
                )
                orc_table.add_row(
                    score.orc_type, str(score.total_accounts),
                    str(score.complete_count), pct,
                )
            console.print(orc_table)

    if output:
        output.write_text(
            json.dumps(result.model_dump(), indent=2, default=str),
            encoding="utf-8",
        )
        console.print(f"\n[green]Certification saved to {output}[/green]")


@app.command(name="full-pipeline")
def full_pipeline(
    institution: str = typer.Option("Covered Institution", help="Institution name"),
    output: Optional[Path] = typer.Option(None, help="Save full results JSON"),
    gpt_enhance: bool = typer.Option(False, "--gpt", help="Add GPT remediation advice"),
):
    """Run all 6 layers with optional GPT-enhanced remediation advice."""
    console.print("[bold blue]Starting full pipeline...[/bold blue]")

    from backend.agents.orchestrator import run_full_pipeline
    state = run_full_pipeline(institution_name=institution)

    if gpt_enhance:
        console.print("\n[bold magenta]Requesting GPT-4.1-mini remediation advice...[/bold magenta]")
        try:
            from backend.agents.base import get_llm, SYSTEM_PERSONA

            # Collect all critical/high findings
            critical_findings = []
            for lr in state.get("layer_results", []):
                for f in lr.get("findings", []):
                    if f.get("severity") in ("CRITICAL", "HIGH"):
                        critical_findings.append(f)

            if critical_findings:
                summary = json.dumps(critical_findings[:20], indent=2, default=str)
                llm = get_llm()
                response = llm.invoke([
                    {"role": "system", "content": SYSTEM_PERSONA},
                    {"role": "user", "content": (
                        f"The following FDIC Part 370 compliance findings were identified "
                        f"for institution '{institution}'.\n\n"
                        f"Provide specific remediation steps for each finding, citing the "
                        f"relevant regulation section.\n\n{summary}"
                    )},
                ])
                console.print(Panel(
                    response.content,
                    title="[bold magenta]GPT Remediation Advice[/bold magenta]",
                    border_style="magenta",
                ))
            else:
                console.print("[green]No critical/high findings -- no remediation needed.[/green]")
        except Exception as e:
            console.print(f"[yellow]GPT enhancement unavailable: {e}[/yellow]")

    _render_full_report(state)

    if output:
        output.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")
        console.print(f"\n[green]Results saved to {output}[/green]")


@app.command()
def report(
    input_file: Path = typer.Argument(..., help="JSON results file to display"),
):
    """Display a formatted compliance report from a saved JSON file."""
    if not input_file.exists():
        console.print(f"[red]File not found: {input_file}[/red]")
        raise typer.Exit(1)

    state = json.loads(input_file.read_text(encoding="utf-8"))
    _render_full_report(state)


@app.command()
def benchmark(
    accounts_count: int = typer.Option(16, help="Number of sample accounts"),
):
    """Run Layer 5 behavioral benchmarks only."""
    console.print("[bold blue]Running Layer 5 behavioral benchmarks...[/bold blue]")

    from backend.core.sample_data import build_sample_accounts
    from backend.layers.layer5_behavioral import Layer5BehavioralAnalyzer

    accounts = build_sample_accounts()[:accounts_count]
    analyzer = Layer5BehavioralAnalyzer()
    result = analyzer.scan(
        accounts=accounts,
        estimated_restriction_seconds=45.0,
        estimated_output_gen_seconds=3600.0,
        failover_available=True,
        failover_snapshot_age_seconds=120.0,
    )

    _render_layer_result(result.model_dump(), 5)


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    app()


if __name__ == "__main__":
    main()
