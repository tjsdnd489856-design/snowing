import sys
from src.db import Database
from src.barcode_parser import BarcodeParser
from src.api_client import APIClient
from src.ui import LensUI

class LensApp:
    """콘택트렌즈 관리 시스템의 전체 흐름을 제어하는 클래스입니다."""

    def __init__(self):
        self.db = Database()
        self.parser = BarcodeParser()
        self.api = APIClient()
        self.ui = LensUI()

    def run(self):
        """프로그램 메인 루프를 실행합니다."""
        while True:
            self.ui.display_menu()
            choice = self.ui.get_input("원하시는 작업의 번호를 선택하세요")

            if choice == '1':
                self.handle_barcode_scan()
            elif choice == '2':
                self.ui.show_products(self.db.list_products(), "전체 제품 목록")
            elif choice == '3':
                self.handle_expiration_check()
            elif choice == '4':
                self.handle_search()
            elif choice == '5':
                self.handle_delete()
            elif choice == '0':
                self.ui.show_message("프로그램을 종료합니다. 감사합니다.")
                break
            else:
                self.ui.show_message("잘못된 선택입니다. 다시 입력해주세요.", "warning")

    def handle_barcode_scan(self):
        """바코드를 스캔하여 제품을 등록하는 로직입니다."""
        input_data = self.ui.get_input("바코드 입력 (이미지 경로 또는 스캐너 문자열)")
        if not input_data:
            return

        # 1. 원본 데이터 확보 (이미지 파일인 경우 인식 시도)
        raw_barcode = input_data
        if input_data.lower().endswith(('.png', '.jpg', '.jpeg')):
            raw_barcode = self.parser.read_from_image(input_data)
            if not raw_barcode:
                self.ui.show_message("이미지에서 바코드를 읽을 수 없습니다.", "error")
                return

        # 2. 바코드 정보 분석
        parsed_data = self.parser.process_scanner_input(raw_barcode)
        
        # 3. 식약처 API 연동 (GTIN 정보가 있는 경우)
        if parsed_data.get('gtin'):
            api_info = self.api.fetch_product_info(parsed_data['gtin'])
            parsed_data = self.api.sync_with_local_db(api_info, parsed_data)
        
        # 4. 제품명 보완 및 최종 저장
        if not parsed_data.get('name'):
            self.ui.show_message("제품명을 가져오지 못했습니다.", "warning")
            manual_name = self.ui.get_input("제품명을 수동으로 입력해주세요 (공란 시 '미지정')")
            parsed_data['name'] = manual_name if manual_name else "미지정 제품"

        if self.db.upsert_product(parsed_data):
            self.ui.show_message(f"등록 성공: {parsed_data['name']}", "success")
        else:
            self.ui.show_message("데이터 저장 중 오류가 발생했습니다.", "error")

    def handle_expiration_check(self):
        """유통기한 상태를 확인하고 출력합니다."""
        exp_data = self.db.get_expiring_products()
        self.ui.show_products(exp_data['expired'], "❌ 만료된 제품 (폐기 필요)")
        self.ui.show_products(exp_data['expiring'], "⚠️ 만료 임박 제품 (30일 이내)")

    def handle_search(self):
        """키워드로 제품을 검색합니다."""
        keyword = self.ui.get_input("검색어 (제품명/LOT/UDI)")
        if keyword:
            results = self.db.list_products(keyword)
            self.ui.show_products(results, f"'{keyword}' 검색 결과")

    def handle_delete(self):
        """제품을 삭제합니다."""
        pid = self.ui.get_input("삭제할 제품의 ID(숫자)")
        if not pid.isdigit():
            self.ui.show_message("유효한 숫자 ID를 입력해주세요.", "error")
            return
            
        if self.db.delete_product(int(pid)):
            self.ui.show_message("성공적으로 삭제되었습니다.", "success")
        else:
            self.ui.show_message("삭제에 실패했습니다. ID를 확인해주세요.", "error")

def main():
    app = LensApp()
    app.run()

if __name__ == "__main__":
    main()
