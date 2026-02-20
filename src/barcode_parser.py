import re
import calendar
from datetime import datetime
from typing import Dict, Any, Optional

class BarcodeParser:
    """
    GS1-128 표준 바코드를 분석하여 제품 식별번호(GTIN), 유통기한, 
    로트번호 등을 추출하는 클래스입니다.
    """

    def process_scanner_input(self, input_str: str) -> Dict[str, Any]:
        """바코드 입력을 받아 각 항목별로 분해된 데이터를 반환합니다."""
        # 1. 기호 제거 및 문자열 정규화
        clean_str = input_str.replace('(', '').replace(')', '').replace(' ', '').strip()
        
        # 기본 데이터 구조 생성
        result = {
            'udi': input_str,
            'gtin': self._extract_gtin(clean_str),
            'expire_date': self._extract_expire_date(clean_str),
            'lot': self._extract_lot(clean_str),
            'manufacture_date': self._extract_manufacture_date(clean_str),
            'power': 'N/A',
            'name': ''
        }
        return result

    def _extract_gtin(self, text: str) -> str:
        """AI 01: 제품 고유 식별번호(GTIN) 추출 (14자리 숫자)"""
        match = re.search(r'01(\d{14})', text)
        if match:
            return match.group(1)
        # 01이 생략된 경우를 대비해 맨 앞 14자리 시도
        return text[:14] if len(text) >= 14 else ""

    def _extract_expire_date(self, text: str) -> str:
        """AI 17: 유통기한 추출 (YYMMDD -> YYYY-MM-DD)"""
        match = re.search(r'17(\d{6})', text)
        if not match:
            return "9999-12-31"

        date_val = match.group(1)
        try:
            year = int(date_val[0:2]) + 2000
            month = int(date_val[2:4])
            day = int(date_val[4:6])
            
            # 일자가 00이면 해당 월의 마지막 날로 처리
            if day == 0:
                day = calendar.monthrange(year, month)[1]
                
            return f"{year}-{month:02d}-{day:02d}"
        except (ValueError, IndexError):
            return "9999-12-31"

    def _extract_lot(self, text: str) -> str:
        """AI 10: 로트번호 추출 (가변 길이 문자열)"""
        match = re.search(r'10([a-zA-Z0-9]+)', text)
        if not match:
            return "N/A"
            
        lot_val = match.group(1)
        # 다른 주요 코드(유통기한 17 등)가 시작되기 전까지만 로트로 간주
        cleaned_lot = re.split(r'(17|21|11)', lot_val)[0]
        return cleaned_lot

    def _extract_manufacture_date(self, text: str) -> str:
        """AI 11: 제조일자 추출 (YYMMDD -> YYYY-MM-DD)"""
        match = re.search(r'11(\d{6})', text)
        if not match:
            return ""
            
        date_val = match.group(1)
        try:
            return f"20{date_val[0:2]}-{date_val[2:4]}-{date_val[4:6]}"
        except (ValueError, IndexError):
            return ""
