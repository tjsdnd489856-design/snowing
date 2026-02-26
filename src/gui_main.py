import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
import threading
import time
import sys
import ctypes
import pystray
from datetime import datetime
from PIL import Image
from pystray import MenuItem as item
import keyboard
from src.db import Database
from src.barcode_parser import BarcodeParser
from src.api_client import APIClient

class LensManagerApp:
    def __init__(self):
        # 1. 핵심 모듈 초기화
        self.db = Database()
        self.parser = BarcodeParser()
        self.api = APIClient()
        self.running = True
        
        # 2. 메인 윈도우 (항상 위에 떠 있는 알림 및 퀵 버튼 창)
        self.root = tk.Tk()
        self.root.overrideredirect(True) # 타이틀바 제거
        self.root.attributes('-topmost', True) # 항상 위에 표시
        # 레이아웃 변경: 좌측(알림, 세로로 긴 형태) / 우측(입고 및 판매 버튼)
        self.root.geometry("380x120+10+10") 
        self.root.configure(bg='black')

        # 그리드 가중치 설정 (버튼들이 영역을 꽉 채우도록 함)
        self.root.columnconfigure(0, weight=1)
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        # --- 버튼 스타일 및 배치 ---
        
        # [1] 유통기한 알림 버튼 (좌측 - 2개의 행을 합쳐서 세로 길이를 2배로 만듦)
        self.alert_btn = tk.Button(
            self.root, 
            text="⏳ 로딩 중...", 
            font=("Malgun Gothic", 11, "bold"),
            bg="gray", fg="white",
            activebackground="darkgray", activeforeground="white",
            relief="flat",
            command=self.show_expiring_list
        )
        self.alert_btn.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=2, pady=2)

        # [2] 입고(Insert) 버튼 (우측 상단)
        self.insert_btn = tk.Button(
            self.root,
            text="📥 입고 (Insert)",
            font=("Malgun Gothic", 10, "bold"),
            bg="#2e7d32", fg="white", # 녹색 계열
            activebackground="#1b5e20", activeforeground="white",
            relief="flat",
            command=self.open_scan_window
        )
        self.insert_btn.grid(row=0, column=1, sticky="nsew", padx=2, pady=(2, 1))

        # [3] 판매(Home) 버튼 (우측 하단 - 입고 버튼과 같은 열)
        self.home_btn = tk.Button(
            self.root,
            text="📤 판매 (Home)",
            font=("Malgun Gothic", 10, "bold"),
            bg="#1565c0", fg="white", # 청색 계열
            activebackground="#0d47a1", activeforeground="white",
            relief="flat",
            command=self.open_delete_window
        )
        self.home_btn.grid(row=1, column=1, sticky="nsew", padx=2, pady=(1, 2))

        # 3. 시스템 트레이 아이콘
        try:
            self.icon_image = Image.open("icon.png")
            self.menu = (
                item('열기 (Open)', self.show_main_window),
                item('종료 (Exit)', self.quit_app)
            )
            self.icon = pystray.Icon("LensManager", self.icon_image, "렌즈 관리자", self.menu)
        except Exception as e:
            print(f"아이콘 로드 오류: {e}")
            self.icon = None
        
        # 4. 글로벌 단축키 설정 (강력한 글로벌 반응성 확보)
        # suppress=True를 설정하여 다른 앱에 키가 입력되는 것을 방지합니다.
        try:
            keyboard.add_hotkey('insert', self.open_scan_window, suppress=True)
            keyboard.add_hotkey('home', self.open_delete_window, suppress=True)
        except Exception as e:
            print(f"단축키 등록 오류: {e}")
        
        # 5. 주기적 작업 시작
        self.check_expiry()

    def _force_english_ime(self, widget):
        """해당 위젯의 입력 모드를 영문으로 강제 전환합니다 (Windows 전용)."""
        if sys.platform == 'win32':
            try:
                hwnd = widget.winfo_id()
                imm32 = ctypes.windll.imm32
                himc = imm32.ImmGetContext(hwnd)
                if himc:
                    # IME_CMODE_ALPHANUMERIC = 0x0
                    imm32.ImmSetConversionStatus(himc, 0, 0)
                    imm32.ImmReleaseContext(hwnd, himc)
            except Exception:
                pass

    def run(self):
        # 트레이 아이콘 실행 (별도 스레드)
        if self.icon:
            threading.Thread(target=self.icon.run, daemon=True).start()
        
        # GUI 메인 루프
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self.quit_app()

    def center_window(self, win, width, height):
        """윈도우를 화면 중앙에 배치하고 최상단으로 올립니다."""
        screen_width = win.winfo_screenwidth()
        screen_height = win.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        win.geometry(f"{width}x{height}+{x}+{y}")
        win.deiconify()
        win.lift()
        win.focus_force()

    def check_expiry(self):
        """1분마다 유통기한 상태 확인 및 버튼 색상 변경"""
        if not self.running: return

        try:
            # 기본 90일, 특정 제품 270일 기준 적용된 데이터 가져오기
            data = self.db.get_expiring_products() 
            expired_count = len(data['expired'])
            expiring_count = len(data['expiring'])
            total_alert = expired_count + expiring_count
            
            if total_alert > 0:
                self.alert_btn.config(
                    text=f"⚠️ 유통기한 임박\n({total_alert}건)", 
                    bg="#d32f2f", fg="white", # 경고색 (빨간색)
                    activebackground="#b71c1c", activeforeground="white"
                )
            else:
                self.alert_btn.config(
                    text="✅ 유통기한 안전", 
                    bg="#455a64", fg="white", # 안정색 (회색조)
                    activebackground="#37474f", activeforeground="white"
                )
                
        except Exception as e:
            print(f"체크 오류: {e}")
        
        # 60초 후 다시 실행
        self.root.after(60000, self.check_expiry)

    def show_main_window(self, icon=None, item=None):
        """메인 윈도우(리스트 등)를 보여줍니다. (추후 구현)"""
        self.root.deiconify() 
        self.root.lift()
        self.root.focus_force()
        messagebox.showinfo("알림", "메인 창 기능은 아직 구현 중입니다.")

    def open_scan_window(self):
        """[Insert 키/버튼] 재고 추가 (스캔) 윈도우를 엽니다."""
        self.root.after(0, self._create_scan_window)

    def _create_scan_window(self):
        scan_win = tk.Toplevel(self.root)
        scan_win.title("📦 재고 추가 (바코드 스캔)")
        self.center_window(scan_win, 500, 200) # 화면 중앙 배치 및 강제 포커스
        scan_win.attributes('-topmost', True)
        
        lbl = tk.Label(scan_win, text="바코드를 스캔하세요 (Insert 키)", font=("Malgun Gothic", 12))
        lbl.pack(pady=10)
        
        entry = tk.Entry(scan_win, font=("Arial", 16), justify='center')
        entry.pack(pady=5, fill='x', padx=50)
        
        # 창이 뜨자마자 입력창에 커서가 가도록 설정 (지연 시간을 주어 더 확실하게 처리)
        # 동시에 한영 모드를 영문으로 강제 전환
        entry.bind("<FocusIn>", lambda e: self._force_english_ime(entry))
        scan_win.after(100, lambda: entry.focus_force())
        scan_win.after(150, lambda: self._force_english_ime(entry))

        result_lbl = tk.Label(scan_win, text="대기 중...", font=("Malgun Gothic", 10), fg="gray")
        result_lbl.pack(pady=10)

        def process_barcode(event=None):
            raw_barcode = entry.get().strip()
            if not raw_barcode: return
            
            entry.delete(0, tk.END)
            result_lbl.config(text="🔍 검색 중...", fg="blue")
            scan_win.update()

            try:
                parsed = self.parser.process_scanner_input(raw_barcode)
                gtin = parsed.get('gtin')
                
                # 기존 DB에서 GTIN으로 정보 조회
                existing_product = self.db.get_product_by_gtin(gtin)
                
                if existing_product:
                    # 이미 등록된 GTIN이면, 프로그램 자체적으로 바코드에서 파싱된 유통기한을 기반으로
                    # 이름과 도수는 기존 데이터를 자동으로 사용 (중복 확인 및 수동 입력 불필요)
                    parsed['name'] = existing_product['name']
                    parsed['power'] = existing_product['power']
                    final_data = parsed
                else:
                    # 신규 GTIN인 경우에만 API 검색 및 수동 입력 진행
                    api_info = self.api.fetch_product_info(gtin)
                    final_data = self.api.sync_with_local_db(api_info, parsed)
                    
                    if not final_data.get('name'):
                        manual_name = simpledialog.askstring("제품명 입력", f"제품명을 찾을 수 없습니다.\nGTIN: {gtin}\n제품명을 입력해주세요:", parent=scan_win)
                        if manual_name:
                            final_data['name'] = manual_name
                        else:
                            result_lbl.config(text="❌ 등록 취소됨 (제품명 없음)", fg="red")
                            return

                    # 도수 정보가 없는 경우 수동 입력 요청
                    if final_data.get('power') == 'N/A':
                        manual_power = simpledialog.askstring("도수 입력", f"도수 정보를 찾을 수 없습니다.\n제품명: {final_data['name']}\n도수를 입력해주세요 (예: -3.50):", parent=scan_win)
                        if manual_power:
                            final_data['power'] = manual_power

                # 공통 저장 로직 (UDI가 같으면 DB단에서 자동으로 수량증가, 다르면 새 데이터로 등록)
                if self.db.upsert_product(final_data):
                    success_msg = (
                        f"✅ 등록 완료!\n"
                        f"제품명: {final_data['name']}\n"
                        f"도수: {final_data.get('power')} / 유통기한: {final_data.get('expire_date')}"
                    )
                    result_lbl.config(text=success_msg, fg="green")
                    # 유통기한 상태 즉시 갱신
                    self.check_expiry()
                else:
                    result_lbl.config(text="❌ 저장 실패 (DB 오류)", fg="red")
            
            except Exception as e:
                result_lbl.config(text=f"⚠️ 오류 발생: {e}", fg="red")
                print(e)

        entry.bind("<Return>", process_barcode)

    def open_delete_window(self):
        """[Home 키/버튼] 재고 삭제 윈도우를 엽니다."""
        self.root.after(0, self._create_delete_window)

    def _create_delete_window(self):
        del_win = tk.Toplevel(self.root)
        del_win.title("📤 판매 (재고 차감)")
        self.center_window(del_win, 500, 240) # 창 높이 조금 증가
        del_win.attributes('-topmost', True)
        
        lbl = tk.Label(del_win, text="판매할 바코드를 스캔하거나\n상품번호(GTIN)/ID를 직접 입력하세요", font=("Malgun Gothic", 12))
        lbl.pack(pady=10)
        
        entry = tk.Entry(del_win, font=("Arial", 14), justify='center')
        entry.pack(pady=5, fill='x', padx=50)
        
        # 수동 판매 버튼 추가
        manual_btn = tk.Button(
            del_win,
            text="📋 수동 판매 (재고 목록에서 수량 변경)",
            font=("Malgun Gothic", 10, "bold"),
            bg="#f57c00", fg="white",
            activebackground="#e65100", activeforeground="white",
            relief="flat",
            command=self.open_manual_sales_window
        )
        manual_btn.pack(pady=5)

        # 창이 뜨자마자 입력창에 커서가 가도록 설정
        # 동시에 한영 모드를 영문으로 강제 전환
        entry.bind("<FocusIn>", lambda e: self._force_english_ime(entry))
        del_win.after(100, lambda: entry.focus_force())
        del_win.after(150, lambda: self._force_english_ime(entry))

        result_lbl = tk.Label(del_win, text="대기 중...", font=("Malgun Gothic", 10), fg="gray")
        result_lbl.pack(pady=5)

        def on_delete(event=None):
            raw_input = entry.get().strip()
            if not raw_input: return
            
            # 입력 초기화
            entry.delete(0, tk.END)
            
            # 1. 숫자만 입력된 경우 확인 (GTIN 직접 입력 vs ID 삭제)
            if raw_input.isdigit():
                # 길이가 13자리 이상이면 상품번호(GTIN) 수동 입력으로 판단
                if len(raw_input) >= 13:
                    res = self.db.decrement_stock_by_gtin(raw_input)
                    if res['success']:
                        product = res['product']
                        product_name = product['name']
                        msg = res['message']
                        display_msg = (
                            f"✅ {msg}\n"
                            f"제품명: {product_name}\n"
                            f"도수: {product.get('power')} / 유통기한: {product.get('expire_date')}"
                        )
                        result_lbl.config(text=display_msg, fg="blue")
                        self.check_expiry()
                    else:
                        result_lbl.config(text=f"❌ 실패: {res['message']}", fg="red")
                    return
                # 짧은 숫자면 기존처럼 ID로 판단하여 제품 자체를 강제 삭제
                else:
                    pid = int(raw_input)
                    if messagebox.askyesno("삭제 확인", f"정말로 ID {pid} 제품을 완전히 삭제하시겠습니까?", parent=del_win):
                        if self.db.delete_product(pid):
                            result_lbl.config(text=f"✅ ID {pid} 삭제 완료", fg="green")
                            self.check_expiry()
                        else:
                            result_lbl.config(text="❌ 삭제 실패 (ID 확인)", fg="red")
                    return

            # 2. 긴 바코드(영문, 괄호 등 포함)인 경우 전체 파싱 후 UDI로 재고 차감 시도
            try:
                # 바코드 파싱 (한글 변환 포함)
                parsed = self.parser.process_scanner_input(raw_input)
                udi = parsed['udi']
                
                # 재고 차감 실행
                res = self.db.decrement_stock_by_udi(udi)
                
                if res['success']:
                    product = res['product']
                    product_name = product['name']
                    msg = res['message'] # "재고 1 감소..." 또는 "재고 소진..."
                    
                    # 상세 정보 포함한 메시지 구성
                    display_msg = (
                        f"✅ {msg}\n"
                        f"제품명: {product_name}\n"
                        f"도수: {product.get('power')} / 유통기한: {product.get('expire_date')}"
                    )
                    
                    # 유통기한 경과 확인
                    try:
                        exp_date = datetime.strptime(product.get('expire_date'), "%Y-%m-%d").date()
                        if exp_date < datetime.now().date():
                            display_msg += "\n⚠️ 유통기한이 지난 제품입니다!"
                            result_lbl.config(text=display_msg, fg="red")
                        else:
                            result_lbl.config(text=display_msg, fg="blue")
                    except Exception:
                        result_lbl.config(text=display_msg, fg="blue")

                    self.check_expiry()
                else:
                    result_lbl.config(text=f"❌ 실패: {res['message']}", fg="red")
                    
            except Exception as e:
                result_lbl.config(text=f"⚠️ 오류: {e}", fg="red")

        entry.bind("<Return>", on_delete)

    def open_manual_sales_window(self):
        """수동 판매 (재고 목록 및 수량 변경) 윈도우를 엽니다."""
        manual_win = tk.Toplevel(self.root)
        manual_win.title("📋 재고 목록 (수동 수량 변경)")
        self.center_window(manual_win, 800, 500)
        manual_win.attributes('-topmost', True)
        
        lbl = tk.Label(manual_win, text="목록을 더블클릭하여 해당 제품의 수량을 변경할 수 있습니다.", font=("Malgun Gothic", 11, "bold"), fg="#1565c0")
        lbl.pack(pady=10)

        cols = ("ID", "제품명", "도수", "유통기한", "수량")
        tree = ttk.Treeview(manual_win, columns=cols, show='headings')
        
        tree.heading("ID", text="ID")
        tree.column("ID", width=50, anchor="center")
        tree.heading("제품명", text="제품명")
        tree.column("제품명", width=350)
        tree.heading("도수", text="도수")
        tree.column("도수", width=80, anchor="center")
        tree.heading("유통기한", text="유통기한")
        tree.column("유통기한", width=100, anchor="center")
        tree.heading("수량", text="수량")
        tree.column("수량", width=80, anchor="center")
        
        tree.pack(fill='both', expand=True, padx=10, pady=5)
        
        scrollbar = ttk.Scrollbar(manual_win, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        
        def load_data():
            for item in tree.get_children():
                tree.delete(item)
            products = self.db.list_products()
            for p in products:
                # 수량이 0인 항목은 회색으로 표시하기 위해 태그 사용
                tags = ('zero_qty',) if p['qty'] <= 0 else ()
                tree.insert("", "end", values=(p['id'], p['name'], p['power'], p['expire_date'], p['qty']), tags=tags)
            
            tree.tag_configure('zero_qty', foreground='gray')

        load_data()
        
        def on_double_click(event):
            selected = tree.selection()
            if not selected: return
            item = tree.item(selected[0])
            values = item['values']
            pid = values[0]
            name = values[1]
            current_qty = values[4]
            
            # 숫자 입력 다이얼로그 (초기값으로 현재 수량 제공)
            new_qty = simpledialog.askinteger(
                "수량 변경", 
                f"선택한 제품: {name}\n현재 수량: {current_qty}개\n\n새로운 수량을 입력하세요:", 
                initialvalue=current_qty, 
                minvalue=0, 
                parent=manual_win
            )
            
            if new_qty is not None and new_qty != current_qty:
                if self.db.update_product_qty(pid, new_qty):
                    messagebox.showinfo("완료", f"수량이 {new_qty}개로 변경되었습니다.", parent=manual_win)
                    load_data()
                    self.check_expiry() # 유통기한 알림 다시 계산
                else:
                    messagebox.showerror("오류", "수량 변경에 실패했습니다.", parent=manual_win)

        tree.bind("<Double-1>", on_double_click)

    def show_expiring_list(self):
        """[버튼 클릭] 유통기한 임박 목록을 보여줍니다."""
        list_win = tk.Toplevel(self.root)
        list_win.title("⚠️ 유통기한 임박 제품 목록")
        self.center_window(list_win, 750, 450) # 목록 창도 중앙 배치 및 강제 포커스
        list_win.attributes('-topmost', True)
        
        cols = ("ID", "제품명", "도수", "유통기한", "남은 일수", "상태")
        tree = ttk.Treeview(list_win, columns=cols, show='headings')
        
        # 헤더 설정
        tree.heading("ID", text="ID")
        tree.column("ID", width=50, anchor="center")
        tree.heading("제품명", text="제품명")
        tree.column("제품명", width=250)
        tree.heading("도수", text="도수")
        tree.column("도수", width=80, anchor="center")
        tree.heading("유통기한", text="유통기한")
        tree.column("유통기한", width=100, anchor="center")
        tree.heading("남은 일수", text="남은 일수")
        tree.column("남은 일수", width=100, anchor="center")
        tree.heading("상태", text="상태")
        tree.column("상태", width=80, anchor="center")
        
        tree.pack(fill='both', expand=True, padx=10, pady=10)
        
        # 스크롤바 추가
        scrollbar = ttk.Scrollbar(list_win, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        
        data = self.db.get_expiring_products()
        
        for p in data['expired']:
            d_day = p.get('days_left', '만료')
            tree.insert("", "end", values=(p['id'], p['name'], p['power'], p['expire_date'], d_day, "만료됨"), tags=('expired',))
        
        for p in data['expiring']:
            d_day = f"D-{p['days_left']}"
            tree.insert("", "end", values=(p['id'], p['name'], p['power'], p['expire_date'], d_day, "임박"), tags=('expiring',))
            
        tree.tag_configure('expired', foreground='white', background='#d32f2f')
        tree.tag_configure('expiring', foreground='black', background='#fff176')

    def quit_app(self, icon=None, item=None):
        """프로그램 종료"""
        self.running = False
        if self.icon:
            self.icon.stop()
        self.root.destroy()
        sys.exit()

if __name__ == "__main__":
    app = LensManagerApp()
    app.run()
