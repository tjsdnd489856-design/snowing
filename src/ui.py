from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from rich import box
from datetime import datetime
from typing import List, Dict, Any, Tuple

class LensUI:
    """
    모던하고 세련된 CLI 사용자 인터페이스를 제공하는 클래스입니다.
    Rich 라이브러리를 활용하여 시각적인 만족도를 높였습니다.
    """

    def __init__(self):
        self.console = Console()
        self.app_title = "[bold cyan]LENS MANAGER[/bold cyan] [dim]v2.0[/dim]"

    def clear_screen(self):
        """화면을 깨끗하게 지웁니다."""
        self.console.clear()

    def display_menu(self):
        """메인 메뉴를 세련된 패널 형태로 출력합니다."""
        self.clear_screen()
        
        # '제품 검색' 항목을 삭제하고 번호를 재조정했습니다.
        menu_content = (
            "\n[bold white]1.[/bold white]  [cyan]바코드 스캔 & 등록[/cyan]    [dim](Barcode Scan)[/dim]\n"
            "[bold white]2.[/bold white]  [cyan]전체 제품 목록[/cyan]        [dim](List All)[/dim]\n"
            "[bold white]3.[/bold white]  [cyan]유통기한 점검[/cyan]         [dim](Check Expiry)[/dim]\n"
            "[bold white]4.[/bold white]  [cyan]제품 삭제[/cyan]             [dim](Delete)[/dim]\n"
            "\n[dim]──────────────────────────────────────────[/dim]\n"
            "[bold white]0.[/bold white]  [red]종료[/red]                  [dim](Exit)[/dim]"
        )

        panel = Panel(
            Align.center(menu_content),
            title=self.app_title,
            subtitle="[dim]Select an option[/dim]",
            border_style="bright_blue",
            box=box.ROUNDED,
            padding=(1, 4),
            width=50
        )
        self.console.print(Align.center(panel))

    def show_products(self, products: List[Dict[str, Any]], title: str = "Product List"):
        """제품 목록을 깔끔한 모던 테이블로 출력합니다."""
        self.clear_screen()

        if not products:
            self.show_message(f"'{title}'에 해당하는 데이터가 없습니다.", "warning")
            self.console.input("\n[dim]Press Enter to continue...[/dim]")
            return

        table = Table(
            title=f"[bold]{title}[/bold] ({len(products)} items)",
            box=box.SIMPLE_HEAD,
            header_style="bold cyan",
            border_style="dim",
            show_lines=False,
            width=100
        )

        table.add_column("ID", style="dim", justify="right", width=4)
        table.add_column("제품명 (Product Name)", style="bold white", width=30)
        table.add_column("도수", justify="center", width=8)
        table.add_column("유통기한", justify="center", width=12)
        table.add_column("상태", justify="center", width=10)
        table.add_column("수량", justify="right", width=6)

        today = datetime.now().date()

        for p in products:
            status_text, row_style = self._get_status_style(p.get('expire_date'), today)
            
            qty_style = "dim" if p.get('qty', 0) == 0 else "bold"
            
            table.add_row(
                str(p['id']),
                p['name'] or "[dim]Unknown[/dim]",
                p['power'] or "-",
                p.get('expire_date', '-'),
                status_text,
                f"[{qty_style}]{p.get('qty', 1)}[/{qty_style}]",
                style=row_style
            )

        self.console.print(Align.center(table))
        self.console.print("\n[dim]목록을 다 보셨으면 엔터를 누르세요...[/dim]", justify="center")
        self.console.input()

    def _get_status_style(self, expire_str: str, today) -> Tuple[str, str]:
        """유통기한 상태에 따른 스타일을 반환합니다."""
        if not expire_str:
            return "[dim]-[/dim]", ""
            
        try:
            expire_date = datetime.strptime(expire_str, "%Y-%m-%d").date()
            days_left = (expire_date - today).days

            if days_left < 0:
                return "[bold red]EXPIRED[/bold red]", "dim red"
            elif days_left <= 30:
                return f"[bold yellow]D-{days_left}[/bold yellow]", ""
            elif days_left <= 90:
                return "[green]GOOD[/green]", ""
            else:
                return "[blue]FRESH[/blue]", ""
        except:
            return "[dim]ERROR[/dim]", ""

    def get_input(self, prompt: str) -> str:
        """심플한 입력 프롬프트를 제공합니다."""
        return self.console.input(f"\n[bold cyan]?[/bold cyan] {prompt}: ").strip()

    def show_message(self, message: str, style: str = "info"):
        """메시지를 깔끔한 박스 형태로 보여줍니다."""
        styles = {
            "info": ("blue", "ℹ️ INFO"),
            "success": ("green", "✅ SUCCESS"),
            "error": ("red", "❌ ERROR"),
            "warning": ("yellow", "⚠️ WARNING")
        }
        color, icon = styles.get(style, ("white", "INFO"))
        
        panel = Panel(
            f"[{color}]{message}[/{color}]",
            title=f"[bold {color}]{icon}[/bold {color}]",
            border_style=color,
            box=box.ROUNDED,
            width=60
        )
        self.console.print(Align.center(panel))
