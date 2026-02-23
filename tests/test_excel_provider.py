import pytest
import os
from openpyxl import Workbook
from src.api_client import ExcelProvider

TEST_EXCEL_PATH = "test_products_korean.xlsx"

@pytest.fixture
def excel_file():
    """한글 헤더와 복합 데이터가 포함된 테스트용 엑셀 파일 생성"""
    wb = Workbook()
    ws = wb.active
    
    # 선생님께서 말씀하신 헤더 형식: 바코드, 품명, 규격, 재고
    ws.append(["바코드", "품명", "규격", "재고"])
    
    # 데이터 추가 (품명에 도수가 포함됨)
    # 바코드는 13자리로 입력 (엑셀 상황 재현)
    ws.append(["8801234567890", "바이오피니티 -3.00", "규격A", 100])
    ws.append(["8809876543210", "아큐브 오아시스 +1.25", "규격B", 50])
    ws.append(["1234567890123", "일반 렌즈 (도수 없음)", "규격C", 0])
    
    wb.save(TEST_EXCEL_PATH)
    yield TEST_EXCEL_PATH
    
    if os.path.exists(TEST_EXCEL_PATH):
        try: os.remove(TEST_EXCEL_PATH)
        except: pass

def test_excel_provider_korean_header(excel_file):
    """한글 헤더(바코드, 품명) 인식 테스트"""
    provider = ExcelProvider(excel_file)
    
    # 데이터가 로드되었는지 확인
    assert "8801234567890" in provider.data_cache

def test_excel_provider_parse_power(excel_file):
    """품명에서 도수 추출 로직 테스트"""
    provider = ExcelProvider(excel_file)
    
    # 1. 마이너스 도수
    res1 = provider.fetch("8801234567890")
    assert res1['name'].strip() == "바이오피니티"
    assert res1['power'] == "-3.00"
    
    # 2. 플러스 도수
    res2 = provider.fetch("8809876543210")
    assert res2['name'].strip() == "아큐브 오아시스"
    assert res2['power'] == "+1.25"
    
    # 3. 도수 없음
    res3 = provider.fetch("1234567890123")
    assert "일반 렌즈" in res3['name']
    assert res3['power'] == "N/A"

def test_excel_provider_13_digit_lookup(excel_file):
    """14자리 스캔 코드로 13자리 엑셀 데이터 검색 테스트"""
    provider = ExcelProvider(excel_file)
    
    # 엑셀에는 '8801234567890' (13자리) 저장됨
    # 스캐너 입력은 '08801234567890' (14자리 - 보통 GS1-128 파싱 결과)
    input_gtin = "08801234567890"
    
    result = provider.fetch(input_gtin)
    
    assert result is not None, "14자리 코드로 13자리 엑셀 데이터를 찾지 못했습니다."
    assert result['name'].strip() == "바이오피니티"
