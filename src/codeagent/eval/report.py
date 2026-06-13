"""评测报告生成"""

from rich.console import Console
from rich.table import Table

from .types import BenchmarkReport, ScenarioResult


def print_report(report: BenchmarkReport, console: Console | None = None) -> None:
    """打印评测报告"""
    if console is None:
        console = Console()
    
    # 标题
    console.print("\n[bold blue]═══════════════════════════════════════════════════════[/bold blue]")
    console.print("[bold blue]              Benchmark Evaluation Report              [/bold blue]")
    console.print("[bold blue]═══════════════════════════════════════════════════════[/bold blue]\n")
    
    # 总览
    console.print(f"[bold]Model:[/bold] {report.model}")
    console.print(f"[bold]Timestamp:[/bold] {report.timestamp}")
    console.print(f"[bold]Total Scenarios:[/bold] {report.total_scenarios}")
    console.print(f"[bold]Passed:[/bold] [green]{report.passed}[/green]")
    console.print(f"[bold]Failed:[/bold] [red]{report.failed}[/red]")
    console.print(f"[bold]Average Score:[/bold] {report.average_score:.2%}")
    console.print(f"[bold]Total Duration:[/bold] {report.total_duration_sec:.1f}s\n")
    
    # 详细结果表格
    table = Table(title="Scenario Results")
    table.add_column("Scenario", style="cyan")
    table.add_column("Score", justify="right")
    table.add_column("Status", justify="center")
    table.add_column("Duration", justify="right")
    table.add_column("Error", style="red")
    
    for result in report.results:
        status = "✓" if result.success else "✗"
        status_style = "green" if result.success else "red"
        
        table.add_row(
            result.scenario_name,
            f"{result.score:.2%}",
            f"[{status_style}]{status}[/{status_style}]",
            f"{result.duration_sec:.1f}s",
            result.error or "",
        )
    
    console.print(table)
    console.print()


def export_report_markdown(report: BenchmarkReport, output_path: str) -> None:
    """导出报告为 Markdown"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# Benchmark Evaluation Report\n\n")
        
        # 总览
        f.write("## Summary\n\n")
        f.write(f"- **Model**: {report.model}\n")
        f.write(f"- **Timestamp**: {report.timestamp}\n")
        f.write(f"- **Total Scenarios**: {report.total_scenarios}\n")
        f.write(f"- **Passed**: {report.passed}\n")
        f.write(f"- **Failed**: {report.failed}\n")
        f.write(f"- **Average Score**: {report.average_score:.2%}\n")
        f.write(f"- **Total Duration**: {report.total_duration_sec:.1f}s\n\n")
        
        # 详细结果
        f.write("## Detailed Results\n\n")
        f.write("| Scenario | Score | Status | Duration | Error |\n")
        f.write("|----------|-------|--------|----------|-------|\n")
        
        for result in report.results:
            status = "✓" if result.success else "✗"
            error = result.error or "-"
            
            f.write(f"| {result.scenario_name} | ")
            f.write(f"{result.score:.2%} | ")
            f.write(f"{status} | ")
            f.write(f"{result.duration_sec:.1f}s | ")
            f.write(f"{error} |\n")
        
        f.write("\n")


def export_report_json(report: BenchmarkReport, output_path: str) -> None:
    """导出报告为 JSON"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report.model_dump_json(indent=2))
