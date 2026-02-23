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
    ws.append(["8801234567890", "바이오피니티 -3.00", "규격A", 100])
    ws.append(["8809876543210", "아큐브 오아시스 +1.25", "규격B", 50])
    ws.append(["1234567890123", "일반 렌즈 (도수 없음)", "규격C", 0])
    ws.append(["1111222233334", "난시용 -4.50", "규격D", 20])
    
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
    # 도수가 없으면 전체를 이름으로 쓰고, 도수는 N/A
    assert "일반 렌즈" in res3['name']
    assert res3['power'] == "N/A"

def test_excel_provider_mixed_format(excel_file):
    """복잡한 형식의 도수 추출"""
    provider = ExcelProvider(excel_file)
    # 정규식 패턴 테스트를 위해 직접 메서드 호출해보기
    
    # 케이스 1: 괄호 안에 도수가 있는 경우 (현재 로직으로는 단순 숫자 패턴만 찾음)
    # 필요하다면 로직을 더 정교하게 수정해야 함.
    pass 
