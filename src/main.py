import sys
from src.db import Database
from src.barcode_parser import BarcodeParser
from src.api_client import APIClient
from src.ui import LensUI

class LensApp:
    def __init__(self):
        self.db = Database()
        self.parser = BarcodeParser()
        self.api = APIClient()
        self.ui = LensUI()

    def run(self):
        while True:
            self.ui.display_menu()
            choice = self.ui.get_input("번호 선택")
            
            # 메뉴 번호 재매핑
            if choice == '1': 
                self.handle_continuous_scan()
            elif choice == '2': 
                self.ui.show_products(self.db.list_products(), "전체 목록")
            elif choice == '3': 
                self.handle_expiration_check()
            elif choice == '4': 
                self.handle_delete() # 기존 5번에서 4번으로 변경
            elif choice == '0': 
                break
            else: 
                self.ui.show_message("잘못된 선택입니다.", "warning")

    def handle_continuous_scan(self):
        self.ui.show_message("--- [연속 스캔 모드] ---", "info")
        while True:
            input_data = self.ui.get_input("바코드 스캔 (엔터 시 종료)")
            if not input_data: break

            raw_barcode = input_data
            if input_data.lower().endswith(('.png', '.jpg', '.jpeg')):
                raw_barcode = self.parser.read_from_image(input_data)
                if not raw_barcode: continue

            existing_product = self.db.get_product_by_udi(raw_barcode)
            if existing_product:
                self.ui.show_message(f"이미 등록된 제품입니다: {existing_product['name']}", "success")
                existing_product['qty'] += 1
                self.db.upsert_product(existing_product)
                self.ui.show_message(f"수량이 추가되었습니다. (현재: {existing_product['qty']}개)", "info")
                continue

            parsed_data = self.parser.process_scanner_input(raw_barcode)
            if parsed_data.get('gtin'):
                api_info = self.api.fetch_product_info(parsed_data['gtin'])
                parsed_data = self.api.sync_with_local_db(api_info, parsed_data)
            
            if not parsed_data.get('name'):
                manual_name = self.ui.get_input("제품명 수동 입력")
                parsed_data['name'] = manual_name if manual_name else "미지정 제품"

            if self.db.upsert_product(parsed_data):
                self.ui.show_message(f"✅ 신규 등록 완료: {parsed_data['name']}", "success")
            
            self.ui.show_message("-" * 20, "info")

    def handle_expiration_check(self):
        data = self.db.get_expiring_products()
        self.ui.show_products(data['expired'], "❌ 만료된 제품 (폐기 필요)")
        self.ui.show_products(data['expiring'], "⚠️ 만료 임박 제품 (30일 이내)")

    def handle_delete(self):
        pid = self.ui.get_input("삭제할 제품의 ID(숫자)")
        if pid.isdigit() and self.db.delete_product(int(pid)):
            self.ui.show_message("성공적으로 삭제되었습니다.", "success")
        else:
            self.ui.show_message("삭제 실패. ID를 확인하세요.", "error")

def main():
    LensApp().run()

if __name__ == "__main__":
    main()
