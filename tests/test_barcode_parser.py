import pytest
from src.barcode_parser import BarcodeParser

@pytest.fixture
def parser():
    return BarcodeParser()

def test_extract_gtin_standard(parser):
    """표준 바코드에서 GTIN 추출 (괄호 포함)"""
    # (01)08801234567890(17)251231(10)ABC12345
    input_str = "(01)08801234567890(17)251231(10)ABC12345"
    result = parser.process_scanner_input(input_str)
    assert result['gtin'] == "08801234567890"

def test_extract_gtin_no_parentheses(parser):
    """괄호 없는 바코드에서 GTIN 추출"""
    # 01088012345678901725123110ABC12345
    input_str = "01088012345678901725123110ABC12345"
    result = parser.process_scanner_input(input_str)
    assert result['gtin'] == "08801234567890"

def test_extract_expiry_date_valid(parser):
    """유효한 유통기한 추출 (YYMMDD)"""
    # 17251231 -> 2025-12-31
    input_str = "(01)08801234567890(17)251231"
    result = parser.process_scanner_input(input_str)
    assert result['expire_date'] == "2025-12-31"

def test_extract_expiry_date_invalid(parser):
    """잘못된 날짜 형식 처리 (월/일 오류)"""
    # 17251332 -> 13월 32일 (불가능)
    input_str = "(01)08801234567890(17)251332"
    result = parser.process_scanner_input(input_str)
    # 현재 구현상 예외 발생 시 "9999-12-31" 반환
    assert result['expire_date'] == "9999-12-31"

def test_extract_lot_number(parser):
    """LOT 번호 추출"""
    # (10)LOT12345(17)...
    input_str = "(10)LOT12345(17)251231"
    result = parser.process_scanner_input(input_str)
    assert result['lot'] == "LOT12345"

def test_extract_manufacture_date(parser):
    """제조일자 추출 (11)"""
    # (11)230101
    input_str = "(11)230101"
    result = parser.process_scanner_input(input_str)
    assert result['manufacture_date'] == "2023-01-01"

def test_empty_input(parser):
    """빈 문자열 입력 시 처리"""
    input_str = ""
    result = parser.process_scanner_input(input_str)
    assert result['gtin'] == ""
    assert result['expire_date'] == "9999-12-31"
