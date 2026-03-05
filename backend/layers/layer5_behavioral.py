"""
Layer 5 -- Behavioral / Runtime Compliance Analyzer
=====================================================
Regulatory Source: Compliance Review Manual Sections 4 and 5

The FDIC's Compliance Review Manual explicitly asks: "Describe the
IT system's projected and maximum throughput capabilities for processing
during the initial 24-hour period."

Sub-checks:

1. **Account Restriction Speed Test** -- measure how long a full hold
   on all deposit accounts takes; it must freeze state before the
   calculation engine starts.

2. **Output File Generation Time Benchmark** -- measure output file
   generation time vs. the 24-hour wall clock.

3. **Iterative Recalculation Throughput** -- simulate multiple ARE file
   submissions of increasing size and measure degradation.

4. **Failover Path Integrity** -- verify DR failover can run the
   complete pipeline from a point-in-time consistent snapshot.
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Callable

from backend.core.models import (
    AnalyzerLayer,
    AREFileRecord,
    ComplianceFinding,
    DepositAccount,
    LayerScanResult,
    Severity,
)


# 24-hour deadline in seconds
_24_HOURS_SEC = 86_400


class Layer5BehavioralAnalyzer:
    """
    Load testing + failover simulation for FDIC Part 370 runtime
    compliance.  Measures real timing of operations against the
    24-hour regulatory window.
    """

    def __init__(self) -> None:
        self._findings: list[ComplianceFinding] = []

    def scan(
        self,
        accounts: list[DepositAccount],
        restriction_fn: Callable[[list[DepositAccount]], None] | None = None,
        output_gen_fn: Callable[[list[DepositAccount]], str] | None = None,
        are_recalc_fn: Callable[[list[AREFileRecord]], None] | None = None,
        failover_available: bool = False,
        failover_snapshot_age_seconds: float | None = None,
        estimated_restriction_seconds: float | None = None,
        estimated_output_gen_seconds: float | None = None,
    ) -> LayerScanResult:
        self._findings = []
        account_count = len(accounts)

        # Sub-check 1: Account Restriction Speed
        self._check_restriction_speed(
            accounts, restriction_fn, estimated_restriction_seconds
        )

        # Sub-check 2: Output File Generation Time
        self._check_output_gen_time(
            accounts, output_gen_fn, estimated_output_gen_seconds
        )

        # Sub-check 3: Iterative ARE Recalculation
        self._check_iterative_recalc(are_recalc_fn, account_count)

        # Sub-check 4: Failover Path Integrity
        self._check_failover(failover_available, failover_snapshot_age_seconds)

        passed = all(f.severity not in (Severity.CRITICAL, Severity.HIGH) for f in self._findings)

        return LayerScanResult(
            layer=AnalyzerLayer.LAYER5_BEHAVIORAL,
            findings=self._findings,
            passed=passed,
            metrics={
                "account_count": account_count,
                "estimated_restriction_sec": estimated_restriction_seconds,
                "estimated_output_gen_sec": estimated_output_gen_seconds,
                "failover_available": failover_available,
            },
            summary=f"Layer 5: {len(self._findings)} behavioral/runtime findings",
        )

    # ------------------------------------------------------------------
    # Sub-check 1: Account Restriction Speed
    # ------------------------------------------------------------------

    def _check_restriction_speed(
        self,
        accounts: list[DepositAccount],
        restriction_fn: Callable | None,
        estimated_seconds: float | None,
    ) -> None:
        """
        Step 1 of the FDIC failure process: apply a full hold to all
        deposit accounts.  Must be fast enough to freeze state before
        the calculation engine begins.
        """
        if restriction_fn is not None:
            t0 = time.perf_counter()
            try:
                restriction_fn(accounts)
            except Exception as exc:
                self._findings.append(ComplianceFinding(
                    layer=AnalyzerLayer.LAYER5_BEHAVIORAL,
                    severity=Severity.CRITICAL,
                    title="Account restriction function failed",
                    description=f"The restriction function raised an error: {exc}",
                    cfr_reference="12 CFR Part 370",
                    it_guide_reference="Compliance Manual Section 4",
                ))
                return
            elapsed = time.perf_counter() - t0
            self._evaluate_restriction_time(elapsed, len(accounts))
        elif estimated_seconds is not None:
            self._evaluate_restriction_time(estimated_seconds, len(accounts))
        else:
            self._findings.append(ComplianceFinding(
                layer=AnalyzerLayer.LAYER5_BEHAVIORAL,
                severity=Severity.HIGH,
                title="Account restriction speed not measured",
                description=(
                    "No restriction function or estimated time was provided.  "
                    "The FDIC Compliance Review Manual requires documented "
                    "throughput capabilities for the restriction step."
                ),
                it_guide_reference="Compliance Manual Section 4",
            ))

    def _evaluate_restriction_time(self, seconds: float, num_accounts: int) -> None:
        """Evaluate whether restriction time is acceptable."""
        # Restriction should be < 1% of the 24-hour window (< ~14.4 minutes)
        max_restriction = _24_HOURS_SEC * 0.01  # ~864 seconds
        if seconds > max_restriction:
            self._findings.append(ComplianceFinding(
                layer=AnalyzerLayer.LAYER5_BEHAVIORAL,
                severity=Severity.CRITICAL,
                title=f"Account restriction too slow: {seconds:.1f}s",
                description=(
                    f"Restriction of {num_accounts:,} accounts took {seconds:.1f}s, "
                    f"exceeding 1%% of the 24-hour window ({max_restriction:.0f}s).  "
                    f"Balances may be modified during calculation."
                ),
                evidence={"elapsed_seconds": seconds, "accounts": num_accounts},
            ))
        elif seconds > max_restriction * 0.5:
            self._findings.append(ComplianceFinding(
                layer=AnalyzerLayer.LAYER5_BEHAVIORAL,
                severity=Severity.MEDIUM,
                title=f"Account restriction approaching limit: {seconds:.1f}s",
                description=f"Restriction took {seconds:.1f}s ({seconds/max_restriction*100:.0f}%% of limit).",
                evidence={"elapsed_seconds": seconds},
            ))

    # ------------------------------------------------------------------
    # Sub-check 2: Output File Generation Time
    # ------------------------------------------------------------------

    def _check_output_gen_time(
        self,
        accounts: list[DepositAccount],
        output_gen_fn: Callable | None,
        estimated_seconds: float | None,
    ) -> None:
        """Verify output file generation completes within 24 hours."""
        if output_gen_fn is not None:
            t0 = time.perf_counter()
            try:
                output_gen_fn(accounts)
            except Exception as exc:
                self._findings.append(ComplianceFinding(
                    layer=AnalyzerLayer.LAYER5_BEHAVIORAL,
                    severity=Severity.CRITICAL,
                    title="Output file generation failed",
                    description=f"The generation function raised an error: {exc}",
                ))
                return
            elapsed = time.perf_counter() - t0
            self._evaluate_output_gen_time(elapsed, len(accounts))
        elif estimated_seconds is not None:
            self._evaluate_output_gen_time(estimated_seconds, len(accounts))
        else:
            self._findings.append(ComplianceFinding(
                layer=AnalyzerLayer.LAYER5_BEHAVIORAL,
                severity=Severity.HIGH,
                title="Output file generation time not measured",
                description=(
                    "No generation function or estimated time provided.  "
                    "The Compliance Review Manual asks the CI to state the "
                    "estimated time and whether initiation is automatic or manual."
                ),
                it_guide_reference="Compliance Manual Section 5",
            ))

    def _evaluate_output_gen_time(self, seconds: float, num_accounts: int) -> None:
        if seconds > _24_HOURS_SEC:
            self._findings.append(ComplianceFinding(
                layer=AnalyzerLayer.LAYER5_BEHAVIORAL,
                severity=Severity.CRITICAL,
                title=f"Output generation exceeds 24-hour window: {seconds:.0f}s",
                description=(
                    f"Projected generation time for {num_accounts:,} accounts "
                    f"is {seconds:.0f}s ({seconds / 3600:.1f} hours), exceeding "
                    f"the 24-hour regulatory deadline."
                ),
                cfr_reference="12 CFR 370.3(b)",
                evidence={"elapsed_seconds": seconds, "hours": seconds / 3600},
            ))
        elif seconds > _24_HOURS_SEC * 0.75:
            self._findings.append(ComplianceFinding(
                layer=AnalyzerLayer.LAYER5_BEHAVIORAL,
                severity=Severity.HIGH,
                title=f"Output generation uses >{seconds/_24_HOURS_SEC*100:.0f}%% of window",
                description=f"Generation time {seconds:.0f}s leaves limited buffer for retries.",
                evidence={"elapsed_seconds": seconds},
            ))

    # ------------------------------------------------------------------
    # Sub-check 3: Iterative ARE Recalculation
    # ------------------------------------------------------------------

    def _check_iterative_recalc(
        self, recalc_fn: Callable | None, base_count: int
    ) -> None:
        """
        Simulate multiple ARE file submissions and measure degradation.
        The system must recalculate without a full restart.
        """
        if recalc_fn is None:
            self._findings.append(ComplianceFinding(
                layer=AnalyzerLayer.LAYER5_BEHAVIORAL,
                severity=Severity.MEDIUM,
                title="Iterative ARE recalculation not tested",
                description=(
                    "No recalculation function provided for stress testing.  "
                    "ARE files can arrive in multiple sequential batches; the "
                    "system must recalculate iteratively without full restart."
                ),
                it_guide_reference="IT Guide Section 5",
            ))
            return

        batch_sizes = [10, 100, 500]
        times: list[float] = []
        for size in batch_sizes:
            test_records = [
                AREFileRecord(
                    are_submission_id=f"STRESS-{size}",
                    account_number=f"STRESS-ACCT-{i}",
                    beneficial_owner_id=f"BO-{i}",
                    beneficial_owner_name=f"Stress Test Owner {i}",
                    balance=float(i * 1000),
                    submission_sequence=batch_sizes.index(size) + 1,
                )
                for i in range(size)
            ]
            t0 = time.perf_counter()
            try:
                recalc_fn(test_records)
            except Exception as exc:
                self._findings.append(ComplianceFinding(
                    layer=AnalyzerLayer.LAYER5_BEHAVIORAL,
                    severity=Severity.HIGH,
                    title=f"ARE recalc failed at batch size {size}",
                    description=f"Error: {exc}",
                ))
                return
            times.append(time.perf_counter() - t0)

        # Check for degradation (> 3x slowdown from batch 1 to batch 3)
        if len(times) >= 3 and times[2] > times[0] * 3:
            self._findings.append(ComplianceFinding(
                layer=AnalyzerLayer.LAYER5_BEHAVIORAL,
                severity=Severity.HIGH,
                title="ARE recalculation shows significant degradation",
                description=(
                    f"Batch 1 ({batch_sizes[0]} records): {times[0]:.3f}s, "
                    f"Batch 3 ({batch_sizes[2]} records): {times[2]:.3f}s.  "
                    f"Degradation factor: {times[2]/max(times[0], 0.001):.1f}x."
                ),
                evidence={"batch_times": dict(zip(batch_sizes, times))},
            ))

    # ------------------------------------------------------------------
    # Sub-check 4: Failover Path Integrity
    # ------------------------------------------------------------------

    def _check_failover(
        self, available: bool, snapshot_age_seconds: float | None
    ) -> None:
        """
        Verify DR failover environment can run the full pipeline from
        a point-in-time consistent snapshot (not a lag-affected replica).
        """
        if not available:
            self._findings.append(ComplianceFinding(
                layer=AnalyzerLayer.LAYER5_BEHAVIORAL,
                severity=Severity.CRITICAL,
                title="No DR failover path available",
                description=(
                    "The institution has not documented a failover environment "
                    "capable of running the complete calculation and output "
                    "generation pipeline.  Part 370 calculations must be based "
                    "on the close-of-business state at the exact moment of failure."
                ),
                cfr_reference="12 CFR Part 370",
                it_guide_reference="Compliance Manual Section 5",
            ))
            return

        if snapshot_age_seconds is not None:
            # Snapshot should be near-zero lag (< 60 seconds)
            if snapshot_age_seconds > 60:
                self._findings.append(ComplianceFinding(
                    layer=AnalyzerLayer.LAYER5_BEHAVIORAL,
                    severity=Severity.HIGH,
                    title=f"DR snapshot lag: {snapshot_age_seconds:.0f}s",
                    description=(
                        f"The DR environment's data snapshot is {snapshot_age_seconds:.0f}s "
                        f"behind primary.  Part 370 requires a point-in-time consistent "
                        f"snapshot, not a replication-lag-affected replica."
                    ),
                    evidence={"snapshot_age_seconds": snapshot_age_seconds},
                ))
        else:
            self._findings.append(ComplianceFinding(
                layer=AnalyzerLayer.LAYER5_BEHAVIORAL,
                severity=Severity.MEDIUM,
                title="DR snapshot consistency not verified",
                description=(
                    "Failover is marked available but snapshot age/consistency "
                    "has not been measured.  Provide snapshot_age_seconds to verify."
                ),
            ))
