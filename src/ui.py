from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from datetime import datetime
from typing import List, Dict

class LensUI:
    """콘솔 기반 사용자 인터페이스 클래스"""

    def __init__(self):
        self.console = Console()

    def display_menu(self):
        menu_text = (
            "[bold cyan]1.[/bold cyan] 바코드 스캔 (USB/이미지)\n"
            "[bold cyan]2.[/bold cyan] 전체 제품 목록 조회\n"
            "[bold cyan]3.[/bold cyan] 만료 및 임박 제품 확인\n"
            "[bold cyan]4.[/bold cyan] 제품 검색\n"
            "[bold cyan]5.[/bold cyan] 제품 삭제\n"
            "[bold cyan]0.[/bold cyan] 종료"
        )
        self.console.print(Panel(menu_text, title="콘택트렌즈 관리 시스템", subtitle="v1.0"))

    def show_products(self, products: List[Dict], title: str = "제품 목록"):
        table = Table(title=title, show_header=True, header_style="bold magenta")
        table.add_column("ID", style="dim", width=4)
        table.add_column("제품명", width=25)
        table.add_column("도수", justify="center")
        table.add_column("유통기한", justify="center")
        table.add_column("상태", justify="center")
        table.add_column("수량", justify="right")

        now = datetime.now().date()

        for p in products:
            status = ""
            row_style = ""
            expire_str = p.get('expire_date', '9999-12-31')

            try:
                expire_date = datetime.strptime(expire_str, "%Y-%m-%d").date()
                if expire_date < now:
                    status = "[bold red]만료됨[/bold red]"
                    row_style = "on red"
                elif (expire_date - now).days <= 30:
                    status = "[bold yellow]임박[/bold yellow]"
                    row_style = "yellow"
                else:
                    status = "[green]정상[/green]"
            except Exception:
                status = "[white]날짜오류[/white]"
                expire_str = "N/A"

            table.add_row(
                str(p['id']),
                p['name'] if p['name'] else "이름 없음",
                p['power'] if p['power'] else "N/A",
                expire_str,
                status,
                str(p['qty']),
                style=row_style
            )

        self.console.print(table)

    def get_input(self, prompt: str) -> str:
        return self.console.input(f"[bold green]>[/bold green] {prompt}: ")

    def show_message(self, message: str, style: str = "info"):
        styles = {"info": "blue", "success": "green", "error": "bold red", "warning": "yellow"}
        self.console.print(f"[{styles.get(style, 'white')}] {message} [/{styles.get(style, 'white')}]")
