"""CLI 主程序 - Typer 应用"""

import typer
from rich.console import Console

app = typer.Typer(
    name="codeagent",
    help="本地优先的 CLI 编码助手（Python 版）",
    add_completion=False,
)

console = Console()


@app.command()
def version():
    """显示版本信息"""
    from ..version import __version__
    console.print(f"[bold green]codeagent[/bold green] version {__version__}")


@app.command()
def ask(
    prompt: str = typer.Argument(..., help="问题或任务描述"),
    mode: str = typer.Option("workspace-write", help="审批模式: readonly/suggest/workspace-write/auto"),
    print_mode: bool = typer.Option(False, "-p", "--print", help="只打印输出，不交互"),
):
    """执行 AI 助手任务"""
    from .commands.ask import run_ask
    
    run_ask(prompt, mode, print_mode)


@app.command()
def init(
    force: bool = typer.Option(False, "--force", help="强制重新初始化"),
):
    """初始化项目配置"""
    from .commands.init import run_init
    
    run_init(force)


@app.command()
def mcp(
    action: str = typer.Argument(..., help="操作: list/add/remove"),
    server_name: str = typer.Argument(None, help="服务器名称"),
):
    """管理 MCP 工具服务器"""
    from .commands.mcp import run_mcp
    
    run_mcp(action, server_name)


@app.command()
def eval(
    benchmark: str = typer.Option(None, "--benchmark", "-b", help="内置 benchmark 名称（或 'all'）"),
    scenario_file: str = typer.Option(None, "--scenario-file", "-f", help="场景文件路径（YAML）"),
    model: str = typer.Option("claude-sonnet-4-6", "--model", "-m", help="使用的模型"),
    output: str = typer.Option(None, "--output", "-o", help="导出报告路径"),
    format: str = typer.Option("markdown", "--format", help="报告格式: markdown/json"),
):
    """运行评测基准测试"""
    from .commands.eval import run_eval

    run_eval(benchmark, scenario_file, model, output, format)


@app.command()
def sessions(
    session_id: str = typer.Argument(None, help="Session ID to inspect (optional)"),
):
    """List or inspect session traces"""
    from .commands.sessions import run_sessions

    run_sessions(session_id)


if __name__ == "__main__":
    app()
