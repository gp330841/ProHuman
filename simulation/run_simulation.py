#!/usr/bin/env python3
"""
ProHuman Simulation Framework — Main Entry Point

Generates synthetic data, validates contracts, tests data integrity,
assesses feature quality, exercises security guardrails, simulates load,
and produces a comprehensive production readiness report.

Usage:
    python -m simulation                          # Run all phases, 5 sessions
    python -m simulation --sessions 20            # 20 sessions
    python -m simulation --phases pipeline        # Pipeline only
    python -m simulation --phases agent           # Agent security only
    python -m simulation --phases load            # Load simulation only
    python -m simulation --verbose                # Detailed output
"""

import argparse
import asyncio
import json
import os
import pathlib
import sys
import time
from typing import Any, Dict

from simulation.runners.pipeline_runner import PipelineRunner
from simulation.runners.agent_scenarios import AgentScenarioRunner
from simulation.runners.load_simulator import LoadSimulator
from simulation.config import SimulationConfig


# ── Console formatting ───────────────────────────────────────────────

class Colors:
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    RESET = "\033[0m"

    @staticmethod
    def disable():
        for attr in dir(Colors):
            if attr.isupper() and not attr.startswith("_"):
                setattr(Colors, attr, "")


def header(text: str):
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'═' * 70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}  {text}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'═' * 70}{Colors.RESET}")


def section(text: str):
    print(f"\n{Colors.BOLD}{Colors.BLUE}── {text} {'─' * max(0, 60 - len(text))}{Colors.RESET}")


def ok(text: str):
    print(f"  {Colors.GREEN}✓{Colors.RESET} {text}")


def fail(text: str):
    print(f"  {Colors.RED}✗{Colors.RESET} {text}")


def warn(text: str):
    print(f"  {Colors.YELLOW}⚠{Colors.RESET} {text}")


def info(text: str):
    print(f"  {Colors.DIM}ℹ{Colors.RESET} {text}")


def metric(label: str, value: Any, unit: str = ""):
    val_str = f"{value}{unit}" if unit else str(value)
    print(f"  {Colors.WHITE}{label:<40}{Colors.RESET} {Colors.BOLD}{val_str}{Colors.RESET}")


# ── Main ─────────────────────────────────────────────────────────────

async def main_async():
    parser = argparse.ArgumentParser(
        description="ProHuman Simulation Framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--sessions", type=int, default=5,
                        help="Number of sessions to simulate (default: 5)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for reproducibility (default: 42)")
    parser.add_argument("--edge-cases", action="store_true", default=True,
                        help="Include edge case testing (default: True)")
    parser.add_argument("--phases", choices=["all", "pipeline", "agent", "load"],
                        default="all", help="Which phases to run")
    parser.add_argument("--output-dir", type=str, default="simulation/reports",
                        help="Directory for JSON report output")
    parser.add_argument("--verbose", action="store_true",
                        help="Show detailed output for each phase")
    parser.add_argument("--no-color", action="store_true",
                        help="Disable colored output")
    args = parser.parse_args()

    if args.no_color:
        Colors.disable()

    config = SimulationConfig(
        num_sessions=args.sessions,
        random_seed=args.seed,
        enable_edge_cases=args.edge_cases,
    )

    header("ProHuman Simulation Framework")
    info(f"Sessions: {config.num_sessions} | Seed: {config.random_seed} | Phases: {args.phases}")
    print()

    overall_start = time.time()
    full_report: Dict[str, Any] = {"config": {
        "sessions": config.num_sessions,
        "seed": config.random_seed,
        "phases": args.phases,
    }}

    # ── Phase 1: Pipeline Simulation ─────────────────────────────────
    if args.phases in ["all", "pipeline"]:
        section("Pipeline Simulation")
        pipeline = PipelineRunner(config)
        pipeline_result = await pipeline.run_full_pipeline()
        full_report["pipeline"] = {
            "duration_ms": round(pipeline_result.duration_ms, 2),
            "records_processed": pipeline_result.records_processed,
            "validations_passed": pipeline_result.validations_passed,
            "validations_failed": pipeline_result.validations_failed,
            "phases": pipeline_result.phase_results,
            "quality_scores": pipeline_result.quality_scores,
            "infra_report": pipeline_result.infra_report,
            "edge_cases": pipeline_result.edge_case_results,
            "production_readiness": pipeline_result.production_issues,
        }

        # Print phase summaries
        for name, pr in pipeline_result.phase_results.items():
            passed = pr.get("validations_passed", 0)
            failed = pr.get("validations_failed", 0)
            records = pr.get("records_processed", 0)
            duration = pr.get("duration_ms", 0)
            status_icon = f"{Colors.GREEN}✓{Colors.RESET}" if failed == 0 else f"{Colors.RED}✗{Colors.RESET}"
            print(f"  {status_icon} {name:<30} {records:>4} records  {passed:>3}P/{failed:>2}F  {duration:>8.1f}ms")

        total_v = pipeline_result.validations_passed + pipeline_result.validations_failed
        pass_rate = (pipeline_result.validations_passed / total_v * 100) if total_v else 0

        print()
        metric("Total records processed", pipeline_result.records_processed)
        metric("Total validations", f"{pipeline_result.validations_passed}P / {pipeline_result.validations_failed}F")
        metric("Pass rate", f"{pass_rate:.1f}", "%")
        metric("Pipeline duration", f"{pipeline_result.duration_ms:.1f}", "ms")

        if pipeline_result.quality_scores:
            print()
            info("Feature quality scores:")
            for feat, score in pipeline_result.quality_scores.items():
                bar = "█" * int(score / 5) + "░" * (20 - int(score / 5))
                color = Colors.GREEN if score >= 80 else Colors.YELLOW if score >= 60 else Colors.RED
                print(f"    {feat:<20} {color}{bar} {score:.0f}/100{Colors.RESET}")

        if pipeline_result.infra_report:
            print()
            info("Mock infrastructure usage:")
            ir = pipeline_result.infra_report
            metric("  DB queries", ir.get("database", {}).get("queries", 0))
            metric("  Redis operations", ir.get("redis", {}).get("operations", 0))
            metric("  S3 uploads", ir.get("s3", {}).get("uploads", 0))
            metric("  Celery tasks queued", ir.get("celery", {}).get("tasks_queued", 0))

        # Edge case results
        edge = pipeline_result.edge_case_results
        if edge and "test_cases" in edge:
            print()
            info(f"Edge case tests: {edge.get('passed', 0)} passed, {edge.get('failed', 0)} failed")
            if args.verbose:
                for tc in edge["test_cases"]:
                    if tc["status"] == "PASS":
                        ok(f"  {tc['name']}")
                    else:
                        fail(f"  {tc['name']}: {tc.get('error', 'failed')}")

        ok(f"Pipeline simulation completed in {pipeline_result.duration_ms:.0f}ms")

    # ── Phase 2: Agent Scenario Testing ──────────────────────────────
    if args.phases in ["all", "agent"]:
        section("Agent Security & Scenario Testing")
        agent_runner = AgentScenarioRunner()
        agent_results = await agent_runner.run_scenarios()
        policy_stress = await agent_runner.run_policy_stress_test()
        full_report["agent"] = {
            "scenarios": agent_results,
            "policy_stress_test": policy_stress,
        }

        correct = sum(1 for r in agent_results if r["correctly_handled"])
        total = len(agent_results)
        blocked = sum(1 for r in agent_results if r["blocked"])
        tool_matches = sum(1 for r in agent_results if r.get("tool_match"))

        # Print scenario results
        for r in agent_results:
            name = r["scenario"]
            if r["correctly_handled"]:
                if r["blocked"]:
                    ok(f"{name:<35} BLOCKED  threats={r['threats']}")
                else:
                    ok(f"{name:<35} ALLOWED  tools={r['predicted_tools']}")
            else:
                fail(f"{name:<35} MISHANDLED (expected block={not r['blocked']})")

        print()
        metric("Scenarios tested", total)
        metric("Correctly handled", f"{correct}/{total}")
        metric("Threats blocked", blocked)
        metric("Tool selection accuracy", f"{tool_matches}/{total - blocked}")
        metric("Detection rate", f"{correct / total * 100:.0f}", "%")

        ok(f"Agent scenario testing completed ({total} scenarios)")

    # ── Phase 3: Load Simulation ─────────────────────────────────────
    if args.phases in ["all", "load"]:
        section("Load & Resource Simulation")

        load_sim = LoadSimulator()

        # Concurrent sessions test
        concurrent_result = await load_sim.simulate_concurrent_sessions(config.num_sessions * 4, {})

        # Burst traffic test
        burst_result = await load_sim.simulate_burst_traffic(
            requests_per_second=20, duration_seconds=10
        )

        # Resource projections
        resource_estimate = load_sim.simulate_resource_usage(config.num_sessions)

        full_report["load"] = {
            "concurrent": {
                "total_operations": concurrent_result.total_operations,
                "avg_latency_ms": concurrent_result.avg_latency_ms,
                "p50_latency_ms": concurrent_result.p50_latency_ms,
                "p95_latency_ms": concurrent_result.p95_latency_ms,
                "p99_latency_ms": concurrent_result.p99_latency_ms,
                "max_latency_ms": concurrent_result.max_latency_ms,
                "errors": concurrent_result.errors,
                "bottlenecks": concurrent_result.bottlenecks,
                "throughput_per_second": concurrent_result.throughput_per_second,
                "details": concurrent_result.details,
            },
            "burst": {
                "total_operations": burst_result.total_operations,
                "avg_latency_ms": burst_result.avg_latency_ms,
                "p95_latency_ms": burst_result.p95_latency_ms,
                "errors": burst_result.errors,
                "bottlenecks": burst_result.bottlenecks,
                "details": burst_result.details,
            },
            "resources": {
                "db_storage_mb": resource_estimate.db_storage_mb,
                "redis_memory_mb": resource_estimate.redis_memory_mb,
                "s3_storage_mb": resource_estimate.s3_storage_mb,
                "api_cost_usd": resource_estimate.api_cost_usd,
                "cost_projections": resource_estimate.cost_projections,
                "breakdown": resource_estimate.breakdown,
            },
        }

        info(f"Concurrent sessions: {config.num_sessions * 4}")
        metric("Avg latency", f"{concurrent_result.avg_latency_ms:.0f}", "ms")
        metric("P95 latency", f"{concurrent_result.p95_latency_ms:.0f}", "ms")
        metric("P99 latency", f"{concurrent_result.p99_latency_ms:.0f}", "ms")
        metric("Throughput", f"{concurrent_result.throughput_per_second:.0f}", " ops/sec")

        if concurrent_result.bottlenecks:
            print()
            warn("Bottlenecks detected:")
            for b in concurrent_result.bottlenecks:
                print(f"    {Colors.YELLOW}→{Colors.RESET} {b}")

        print()
        info("Burst traffic (20 rps × 10s):")
        burst_d = burst_result.details
        metric("  Accepted", f"{burst_d.get('accepted', 0)}/{burst_d.get('total_requests', 0)}")
        metric("  Rate limited", f"{burst_d.get('rate_limited', 0)} ({burst_d.get('rate_limit_pct', 0)}%)")

        print()
        info("Resource projections per session:")
        bd = resource_estimate.breakdown
        per_session = bd.get("per_session_breakdown", {})
        metric("  STT (Deepgram)", f"${per_session.get('stt', 0):.4f}")
        metric("  Embeddings (OpenAI)", f"${per_session.get('embeddings', 0):.4f}")
        metric("  LLM Features (GPT-4o)", f"${per_session.get('llm_features', 0):.4f}")
        metric("  Total per session", f"${bd.get('per_session_cost', 0):.4f}")

        print()
        info("Cost projections:")
        for tier, cost in resource_estimate.cost_projections.items():
            sessions = tier.replace("_sessions", "").replace("_", ",")
            metric(f"  {sessions} sessions", f"${cost:.2f}")

        print()
        info("Storage projections:")
        metric("  PostgreSQL", f"{resource_estimate.db_storage_mb:.1f}", " MB")
        metric("  S3 (audio)", f"{resource_estimate.s3_storage_mb:.0f}", " MB")
        metric("  Redis", f"{resource_estimate.redis_memory_mb:.2f}", " MB")

        ok("Load simulation completed")

    # ── Production Readiness Summary ─────────────────────────────────
    header("Production Readiness Report")

    readiness = full_report.get("pipeline", {}).get("production_readiness", {})
    total_score = readiness.get("total_score", 0)
    grade = readiness.get("grade", "N/A")
    dim_scores = readiness.get("dimension_scores", {})

    # Score display
    color = Colors.GREEN if total_score >= 80 else Colors.YELLOW if total_score >= 60 else Colors.RED
    print(f"\n  {Colors.BOLD}Production Readiness Score: {color}{total_score}/100 (Grade: {grade}){Colors.RESET}")
    print()

    if dim_scores:
        info("Score breakdown:")
        for dim, score in dim_scores.items():
            max_for_dim = {"contract_compliance": 40, "data_integrity": 20,
                           "feature_quality": 20, "error_handling": 10, "infra_resilience": 10}
            max_s = max_for_dim.get(dim, 100)
            pct = score / max_s * 100
            bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
            dim_color = Colors.GREEN if pct >= 80 else Colors.YELLOW if pct >= 60 else Colors.RED
            print(f"    {dim:<25} {dim_color}{bar} {score}/{max_s}{Colors.RESET}")

    # Issues
    issues = readiness.get("issues", [])
    if issues:
        print()
        warn(f"Issues found ({len(issues)}):")
        for issue in issues:
            sev = issue.get("severity", "info")
            sev_color = Colors.RED if sev == "critical" else Colors.YELLOW if sev == "major" else Colors.DIM
            print(f"    {sev_color}[{sev.upper()}]{Colors.RESET} {issue.get('area', '')}: {issue.get('description', '')}")
            print(f"    {Colors.DIM}→ {issue.get('recommendation', '')}{Colors.RESET}")

    # Recommendations
    recommendations = readiness.get("recommendations", [])
    if recommendations:
        section("Production Enhancement Recommendations")
        for i, rec in enumerate(recommendations, 1):
            priority = rec.get("priority", "")
            pcolor = Colors.RED if "P0" in priority else Colors.YELLOW if "P1" in priority else Colors.CYAN
            print(f"\n  {pcolor}{priority}{Colors.RESET}: {Colors.BOLD}{rec.get('title', '')}{Colors.RESET}")
            print(f"  {Colors.DIM}{rec.get('details', '')}{Colors.RESET}")

    # ── Save report ──────────────────────────────────────────────────
    total_time = time.time() - overall_start
    full_report["total_duration_seconds"] = round(total_time, 3)

    os.makedirs(args.output_dir, exist_ok=True)
    report_path = pathlib.Path(args.output_dir) / "simulation_report.json"

    def default_serializer(obj):
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        return str(obj)

    with open(report_path, "w") as f:
        json.dump(full_report, f, default=default_serializer, indent=2)

    print()
    section("Summary")
    metric("Total simulation time", f"{total_time:.2f}", "s")
    metric("Report saved to", str(report_path))
    print()


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
