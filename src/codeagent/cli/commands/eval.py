"""eval 命令实现 - 运行评测"""

import asyncio
import os
from pathlib import Path

from rich.console import Console

from ...eval.harness import EvalHarness
from ...eval.loader import load_all_benchmarks, load_scenarios_from_yaml
from ...eval.report import export_report_json, export_report_markdown, print_report

console = Console()


def run_eval(
    benchmark: str | None,
    scenario_file: str | None,
    model: str,
    output: str | None,
    format: str,
):
    """运行评测命令"""
    # 检查 API 密钥
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        console.print("[red]Error:[/red] ANTHROPIC_API_KEY not set")
        console.print("Evaluation requires API key. Set it with:")
        console.print("  export ANTHROPIC_API_KEY=your-key-here")
        return
    
    # 加载场景
    scenarios = []
    
    if scenario_file:
        # 从指定文件加载
        scenarios = load_scenarios_from_yaml(scenario_file)
        console.print(f"Loaded {len(scenarios)} scenarios from {scenario_file}")
    
    elif benchmark:
        # 从内置 benchmark 加载
        benchmarks_dir = Path(__file__).parent.parent.parent / "eval" / "benchmarks"
        
        if benchmark == "all":
            # 加载所有
            all_benchmarks = load_all_benchmarks(str(benchmarks_dir))
            for bench_name, bench_scenarios in all_benchmarks.items():
                scenarios.extend(bench_scenarios)
            console.print(f"Loaded {len(scenarios)} scenarios from all benchmarks")
        else:
            # 加载指定 benchmark
            benchmark_file = benchmarks_dir / f"{benchmark}.yaml"
            if not benchmark_file.exists():
                console.print(f"[red]Error:[/red] Benchmark '{benchmark}' not found")
                console.print(f"Available benchmarks:")
                for yaml_file in benchmarks_dir.glob("*.yaml"):
                    console.print(f"  - {yaml_file.stem}")
                return
            
            scenarios = load_scenarios_from_yaml(str(benchmark_file))
            console.print(f"Loaded {len(scenarios)} scenarios from benchmark '{benchmark}'")
    
    else:
        console.print("[red]Error:[/red] Must specify --benchmark or --scenario-file")
        return
    
    if not scenarios:
        console.print("[yellow]Warning:[/yellow] No scenarios to run")
        return
    
    # 运行评测
    console.print(f"\n[bold blue]Running evaluation with model:[/bold blue] {model}\n")
    
    harness = EvalHarness(api_key=api_key)
    report = asyncio.run(harness.run_benchmark(scenarios, model))
    
    # 打印报告
    print_report(report)
    
    # 导出报告
    if output:
        if format == "markdown":
            export_report_markdown(report, output)
            console.print(f"[green]Report exported to:[/green] {output}")
        elif format == "json":
            export_report_json(report, output)
            console.print(f"[green]Report exported to:[/green] {output}")
