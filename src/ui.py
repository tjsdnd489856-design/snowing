from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from datetime import datetime
from typing import List, Dict, Any

class LensUI:
    """
    사용자에게 정보를 보여주고 입력을 받는 화면 관련 클래스입니다.
    """

    def __init__(self):
        self.console = Console()

    def display_menu(self):
        """프로그램의 주 메뉴를 출력합니다."""
        menu_text = (
            "[bold cyan]1.[/bold cyan] 바코드 스캔 (USB/이미지 경로)\n"
            "[bold cyan]2.[/bold cyan] 전체 제품 목록 보기\n"
            "[bold cyan]3.[/bold cyan] 유통기한 만료/임박 확인\n"
            "[bold cyan]4.[/bold cyan] 제품 검색 (이름/UDI/LOT)\n"
            "[bold cyan]5.[/bold cyan] 제품 삭제 (ID 입력)\n"
            "[bold cyan]0.[/bold cyan] 프로그램 종료"
        )
        self.console.print(Panel(menu_text, title="👓 콘택트렌즈 관리 시스템", subtitle="v1.1", border_style="bright_blue"))

    def show_products(self, products: List[Dict[str, Any]], title: str = "제품 목록"):
        """제품 목록을 표 형식으로 예쁘게 출력합니다."""
        if not products:
            self.show_message(f"'{title}'에 해당하는 데이터가 없습니다.", "warning")
            return

        table = Table(title=title, show_header=True, header_style="bold magenta", border_style="dim")
        table.add_column("ID", style="dim", width=4, justify="right")
        table.add_column("제품명", width=25)
        table.add_column("도수", justify="center")
        table.add_column("유통기한", justify="center")
        table.add_column("상태", justify="center")
        table.add_column("수량", justify="right")

        today = datetime.now().date()

        for p in products:
            status_text, row_style = self._get_status_and_style(p.get('expire_date'), today)
            
            table.add_row(
                str(p['id']),
                p['name'] or "이름 없음",
                p['power'] or "N/A",
                p.get('expire_date', 'N/A'),
                status_text,
                str(p.get('qty', 1)),
                style=row_style
            )

        self.console.print(table)

    def _get_status_and_style(self, expire_str: str, today) -> tuple:
        """유통기한에 따른 상태 메시지와 행 스타일(색상)을 결정합니다."""
        if not expire_str:
            return "[white]정보없음[/white]", ""
            
        try:
            expire_date = datetime.strptime(expire_str, "%Y-%m-%d").date()
            if expire_date < today:
                return "[bold red]만료됨[/bold red]", "on red"
            elif (expire_date - today).days <= 30:
                return "[bold yellow]임박[/bold yellow]", "yellow"
            else:
                return "[green]정상[/green]", ""
        except (ValueError, TypeError):
            return "[white]날짜오류[/white]", ""

    def get_input(self, prompt: str) -> str:
        """사용자로부터 문자열 입력을 받습니다."""
        return self.console.input(f"\n[bold green]?[/bold green] {prompt}: ").strip()

    def show_message(self, message: str, style: str = "info"):
        """중요한 메시지를 사용자에게 알립니다."""
        styles = {
            "info": "cyan",
            "success": "bold green",
            "error": "bold red",
            "warning": "bold yellow"
        }
        color = styles.get(style, "white")
        self.console.print(f"[{color}]> {message}[/{color}]")
