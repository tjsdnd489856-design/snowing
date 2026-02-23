import pytest
import os
from openpyxl import Workbook
from src.api_client import ExcelProvider

# 테스트용 엑셀 파일 경로
TEST_EXCEL_PATH = "test_products.xlsx"

@pytest.fixture
def excel_file():
    """테스트용 엑셀 파일을 생성하고 경로를 반환합니다."""
    wb = Workbook()
    ws = wb.active
    
    # 헤더 생성
    ws.append(["GTIN", "NAME", "POWER"])
    
    # 데이터 추가
    ws.append(["8801234567890", "Test Lens A", "-2.00"])
    ws.append(["8809876543210", "Test Lens B", "-3.50"])
    ws.append(["1234567890123", "No Power Lens", "N/A"])
    
    wb.save(TEST_EXCEL_PATH)
    yield TEST_EXCEL_PATH
    
    # 테스트 종료 후 파일 삭제
    if os.path.exists(TEST_EXCEL_PATH):
        os.remove(TEST_EXCEL_PATH)

def test_excel_provider_load(excel_file):
    """엑셀 파일을 정상적으로 로드하는지 테스트"""
    provider = ExcelProvider(excel_file)
    
    # 캐시에 데이터가 로드되었는지 확인
    assert "8801234567890" in provider.data_cache
    assert "8809876543210" in provider.data_cache

def test_excel_provider_fetch(excel_file):
    """엑셀에서 데이터를 검색하는지 테스트"""
    provider = ExcelProvider(excel_file)
    
    # 1. 정상 검색
    result = provider.fetch("8801234567890")
    assert result['name'] == "Test Lens A"
    assert result['power'] == "-2.00"
    
    # 2. 다른 데이터 검색
    result = provider.fetch("8809876543210")
    assert result['name'] == "Test Lens B"
    assert result['power'] == "-3.50"
    
    # 3. 없는 데이터 검색
    result = provider.fetch("9999999999999")
    assert result is None

def test_excel_provider_missing_file():
    """존재하지 않는 파일을 로드할 때 처리"""
    provider = ExcelProvider("non_existent_file.xlsx")
    assert provider.data_cache == {} # 빈 딕셔너리여야 함 (에러 없이)
