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
                self.handle_continuous_scan()
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

    def handle_continuous_scan(self):
        """바코드를 연속으로 스캔하여 등록하는 모드입니다."""
        self.ui.show_message("--- [연속 스캔 모드 시작] ---", "info")
        self.ui.show_message("바코드를 찍어주세요. (종료하려면 엔터만 입력)", "info")
        
        while True:
            input_data = self.ui.get_input("바코드 스캔")
            
            # 아무 입력 없이 엔터만 치면 메뉴로 복귀
            if not input_data:
                self.ui.show_message("--- [연속 스캔 모드 종료] ---", "info")
                break

            # 1. 원본 데이터 확보 (이미지 경로가 입력될 경우 처리 포함)
            raw_barcode = input_data
            if input_data.lower().endswith(('.png', '.jpg', '.jpeg')):
                raw_barcode = self.parser.read_from_image(input_data)
                if not raw_barcode:
                    self.ui.show_message("이미지 분석 실패. 다음 바코드를 시도하세요.", "error")
                    continue

            # 2. 바코드 정보 분석 (GTIN, 유통기한 등 추출)
            parsed_data = self.parser.process_scanner_input(raw_barcode)
            
            # 3. API 연동 (데이터 보완)
            if parsed_data.get('gtin'):
                api_info = self.api.fetch_product_info(parsed_data['gtin'])
                parsed_data = self.api.sync_with_local_db(api_info, parsed_data)
            
            # 4. 이름이 없을 경우 처리
            if not parsed_data.get('name'):
                self.ui.show_message("제품 정보를 찾지 못했습니다.", "warning")
                manual_name = self.ui.get_input("제품명 수동 입력 (건너뛰려면 엔터)")
                parsed_data['name'] = manual_name if manual_name else "미지정 제품"

            # 5. DB 저장
            if self.db.upsert_product(parsed_data):
                self.ui.show_message(f"✅ 등록 완료: {parsed_data['name']}", "success")
            else:
                self.ui.show_message("❌ 저장 중 오류가 발생했습니다.", "error")
            
            self.ui.show_message("-" * 40, "info")
            self.ui.show_message("다음 바코드를 찍으세요...", "info")

    def handle_expiration_check(self):
        """유통기한 상태 확인"""
        exp_data = self.db.get_expiring_products()
        self.ui.show_products(exp_data['expired'], "❌ 만료된 제품 (폐기 필요)")
        self.ui.show_products(exp_data['expiring'], "⚠️ 만료 임박 제품 (30일 이내)")

    def handle_search(self):
        """키워드 검색"""
        keyword = self.ui.get_input("검색어 (제품명/LOT/UDI)")
        if keyword:
            results = self.db.list_products(keyword)
            self.ui.show_products(results, f"'{keyword}' 검색 결과")

    def handle_delete(self):
        """제품 삭제"""
        pid = self.ui.get_input("삭제할 제품의 ID(숫자)")
        if not pid.isdigit():
            self.ui.show_message("유효한 숫자 ID를 입력해주세요.", "error")
            return
            
        if self.db.delete_product(int(pid)):
            self.ui.show_message("성공적으로 삭제되었습니다.", "success")
        else:
            self.ui.show_message("삭제 실패. ID를 확인하세요.", "error")

def main():
    app = LensApp()
    app.run()

if __name__ == "__main__":
    main()
