"""
Analytics Readiness & Data Quality Analyzer - CLI Entry Point

Usage:
    python -m src.main analyze data/file.csv --rules config/rules.yaml --output output/
    python -m src.main analyze data/file.xlsx --output output/
    python -m src.main --help
"""

import sys
from pathlib import Path
from typing import Optional

import typer
from loguru import logger
from rich.console import Console
from rich.table import Table

from .ingestion import load_dataset, DatasetProfile
from .profiler import profile_dataset
from .type_detector import detect_semantic_types
from .quality_engine import run_quality_checks
from .rules import load_rules, RuleEngine
from .issue_manager import IssueManager
from .scoring import calculate_readiness_score
from .kpi_engine import KPIEngine
from .dax_generator import DAXGenerator
from .report_generator import ReportGenerator

app = typer.Typer(
    name="analytics-readiness-analyzer",
    help="Analyze dataset quality, detect types, validate rules, score readiness, recommend KPIs/DAX.",
    add_completion=False,
)
console = Console()


@app.command()
def analyze(
    file_path: Path = typer.Argument(..., help="Path to CSV or XLSX file", exists=True, readable=True),
    rules_path: Optional[Path] = typer.Option(None, "--rules", "-r", help="Path to business rules YAML"),
    output_dir: Path = typer.Option(Path("output"), "--output", "-o", help="Output directory for reports"),
    sample_size: Optional[int] = typer.Option(None, "--sample", "-s", help="Sample rows for large datasets"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
):
    """Analyze a dataset and generate quality reports."""
    # Configure logging
    logger.remove()
    logger.add(sys.stderr, level="DEBUG" if verbose else "INFO")

    console.print(f"[bold cyan]Analytics Readiness & Data Quality Analyzer[/bold cyan]")
    console.print(f"[dim]Version 0.1.0[/dim]\n")

    try:
        # Phase 1: Ingestion
        console.print("[yellow]Phase 1:[/yellow] Loading dataset...")
        df, profile = load_dataset(file_path, sample_size=sample_size)
        _print_dataset_profile(profile)

        # Phase 2: Profiling
        console.print("\n[yellow]Phase 2:[/yellow] Profiling columns...")
        column_profiles = profile_dataset(df)
        _print_column_summary(column_profiles)

        # Phase 3: Semantic Type Detection
        console.print("\n[yellow]Phase 3:[/yellow] Detecting semantic types...")
        type_results = detect_semantic_types(df, column_profiles)
        _print_type_detection(type_results)

        # Phase 4: Quality Checks
        console.print("\n[yellow]Phase 4:[/yellow] Running data quality checks...")
        quality_issues = run_quality_checks(df, column_profiles, type_results)
        console.print(f"  Found {len(quality_issues)} quality issues")

        # Phase 5: Business Rules
        rule_issues = []
        if rules_path and rules_path.exists():
            console.print("\n[yellow]Phase 5:[/yellow] Validating business rules...")
            rules = load_rules(rules_path)
            engine = RuleEngine(rules)
            rule_issues = engine.run(df)
            console.print(f"  Found {len(rule_issues)} rule violations")
        else:
            console.print("\n[yellow]Phase 5:[/yellow] Skipping business rules (no rules file provided)")

        # Phase 6: Issue Management
        console.print("\n[yellow]Phase 6:[/yellow] Consolidating issues...")
        issue_manager = IssueManager()
        all_issues = issue_manager.consolidate(quality_issues + rule_issues)
        console.print(f"  Total issues: {len(all_issues)}")
        _print_severity_summary(all_issues)

        # Phase 7: Readiness Score
        console.print("\n[yellow]Phase 7:[/yellow] Calculating readiness score...")
        rules_configured = bool(rules_path and rules_path.exists())
        readiness = calculate_readiness_score(df, column_profiles, all_issues, rules_configured=rules_configured)
        _print_readiness_score(readiness)

        # Phase 10: KPI Recommendations
        console.print("\n[yellow]Phase 10:[/yellow] Recommending KPIs...")
        kpi_engine = KPIEngine()
        kpi_recommendations = kpi_engine.recommend_kpis(len(df), type_results, all_issues)
        console.print(f"  Recommended {len(kpi_recommendations)} KPIs")

        # Phase 11: DAX Generation
        console.print("\n[yellow]Phase 11:[/yellow] Generating DAX measures...")
        dax_gen = DAXGenerator(table_name="Dataset")
        dax_measures = dax_gen.generate_measures(kpi_recommendations)
        console.print(f"  Generated {len(dax_measures)} DAX measures")

        # Phase 13: Report Generation
        console.print("\n[yellow]Phase 13:[/yellow] Generating Power BI-ready reports...")
        output_dir.mkdir(parents=True, exist_ok=True)
        report_gen = ReportGenerator(output_dir=str(output_dir))
        dataset_name = file_path.stem
        report_gen.export_all(
            dataset_name=dataset_name,
            row_count=profile.row_count,
            column_count=profile.column_count,
            col_profiles=column_profiles,
            type_results=type_results,
            issues=all_issues,
            score=readiness,
            kpis=kpi_recommendations,
            dax=dax_measures,
        )
        console.print(f"  Reports saved to: [green]{output_dir}[/green]")

        console.print("\n[bold green]Analysis complete![/bold green]")

    except Exception as e:
        logger.exception("Analysis failed")
        console.print(f"\n[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command()
def version():
    """Show version information."""
    console.print("Analytics Readiness & Data Quality Analyzer v0.1.0")


# ─── Helper Functions ──────────────────────────────────────────────

def _print_dataset_profile(profile: DatasetProfile):
    table = Table(title="Dataset Profile", show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Rows", f"{profile.row_count:,}")
    table.add_row("Columns", str(profile.column_count))
    table.add_row("File", str(profile.file_path))
    table.add_row("Format", profile.file_format)
    table.add_row("Memory Usage", f"{profile.memory_usage_mb:.2f} MB")
    console.print(table)


def _print_column_summary(column_profiles):
    table = Table(title="Column Summary", show_header=True, header_style="bold magenta")
    table.add_column("Column", style="cyan")
    table.add_column("Storage Type", style="yellow")
    table.add_column("Null %", style="red")
    table.add_column("Unique %", style="blue")
    table.add_column("Sample Values", style="dim")
    for cp in column_profiles:
        table.add_row(
            cp.name,
            cp.storage_type,
            f"{cp.null_percentage:.1f}%",
            f"{cp.unique_percentage:.1f}%",
            ", ".join(map(str, cp.sample_values[:3])),
        )
    console.print(table)


def _print_type_detection(type_results):
    table = Table(title="Semantic Type Detection", show_header=True, header_style="bold magenta")
    table.add_column("Column", style="cyan")
    table.add_column("Storage Type", style="yellow")
    table.add_column("Detected Type", style="green")
    table.add_column("Confidence", style="blue")
    table.add_column("Status", style="bold")
    for tr in type_results:
        status_style = "green" if tr.status == "OK" else "yellow" if tr.status == "MISMATCH" else "red"
        table.add_row(
            tr.column_name,
            tr.storage_type,
            tr.detected_type,
            f"{tr.confidence:.0%}",
            f"[{status_style}]{tr.status}[/{status_style}]",
        )
    console.print(table)


def _print_severity_summary(issues):
    from collections import Counter
    severity_counts = Counter(i.severity for i in issues)
    table = Table(title="Issue Severity Summary", show_header=True, header_style="bold magenta")
    table.add_column("Severity", style="bold")
    table.add_column("Count", style="green")
    for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]:
        count = severity_counts.get(sev, 0)
        color = {"CRITICAL": "red", "HIGH": "orange3", "MEDIUM": "yellow", "LOW": "blue", "INFO": "cyan"}[sev]
        table.add_row(f"[{color}]{sev}[/{color}]", str(count))
    console.print(table)


def _print_readiness_score(readiness):
    table = Table(title="Data Readiness Score", show_header=True, header_style="bold magenta")
    table.add_column("Dimension", style="cyan")
    table.add_column("Score", style="green")
    table.add_column("Weight", style="yellow")
    for dim, score in readiness.dimension_scores.items():
        table.add_row(dim.replace("_", " ").title(), f"{score:.1f}%", f"{readiness.weights.get(dim, 0):.0%}")
    table.add_row("[bold]OVERALL[/bold]", f"[bold]{readiness.overall_score:.1f}%[/bold]", "")
    console.print(table)


if __name__ == "__main__":
    app()