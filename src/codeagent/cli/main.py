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


if __name__ == "__main__":
    app()
