import sys
from src.db import Database
from src.barcode_parser import BarcodeParser
from src.api_client import APIClient
from src.ui import LensUI

def main():
    db = Database()
    parser = BarcodeParser()
    api = APIClient()
    ui = LensUI()

    while True:
        ui.display_menu()
        choice = ui.get_input("선택")

        if choice == '1':
            input_data = ui.get_input("바코드 입력 (이미지 경로 또는 스캐너 문자열)")
            if not input_data: continue
            
            # 1. 이미지 처리
            if input_data.lower().endswith(('.png', '.jpg', '.jpeg')):
                raw_barcode = parser.read_from_image(input_data)
            else:
                raw_barcode = input_data
            
            if not raw_barcode:
                ui.show_message("바코드를 인식할 수 없습니다.", "error")
                continue

            # 2. [핵심] GS1 표준 파싱 (유통기한, 로트번호 등 즉시 확보)
            parsed_data = parser.process_scanner_input(raw_barcode)
            
            # 3. [핵심] 추출된 UDI-DI(GTIN)로만 API 정석 조회
            if parsed_data['gtin']:
                api_data = api.fetch_product_info(parsed_data['gtin'])
                if api_data:
                    # API에서 가져온 제품명과 도수 합치기
                    parsed_data = api.sync_with_local_db(api_data, parsed_data)
            
            # 4. 최종 확인 및 수동 입력
            if not parsed_data.get('name'):
                ui.show_message("정부 DB에서 제품명을 찾지 못했습니다.", "warning")
                manual_name = ui.get_input("제품명 직접 입력")
                parsed_data['name'] = manual_name if manual_name else "미지정 제품"

            # 5. DB 저장
            if db.upsert_product(parsed_data):
                ui.show_message(f"성공적으로 등록되었습니다: {parsed_data['name']}", "success")
            else:
                ui.show_message("DB 저장 중 오류 발생", "error")

        elif choice == '2':
            products = db.list_products()
            ui.show_products(products, "전체 제품 목록")

        elif choice == '3':
            exp_data = db.get_expiring_products()
            ui.show_products(exp_data['expired'], "만료된 제품 (폐기 필요!)")
            ui.show_products(exp_data['expiring'], "만료 임박 제품 (30일 이내)")

        elif choice == '4':
            search_term = ui.get_input("검색어 (이름/LOT/UDI)")
            products = db.list_products(search_term)
            ui.show_products(products, f"'{search_term}' 검색 결과")

        elif choice == '5':
            pid = ui.get_input("삭제할 제품 ID")
            try:
                if db.delete_product(int(pid)):
                    ui.show_message("삭제 완료", "success")
                else:
                    ui.show_message("삭제 실패", "error")
            except ValueError:
                ui.show_message("유효한 ID를 입력하세요.", "error")

        elif choice == '0':
            ui.show_message("프로그램을 종료합니다.")
            sys.exit(0)

        else:
            ui.show_message("잘못된 선택입니다.", "warning")

if __name__ == "__main__":
    main()
