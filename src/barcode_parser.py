import re
import calendar
import cv2
from pyzbar import pyzbar
from datetime import datetime
from typing import Dict, Any, Optional

class BarcodeParser:
    """
    GS1-128 표준 바코드를 분석하고, 이미지 파일에서 바코드를 추출하는 클래스입니다.
    """

    def process_scanner_input(self, input_str: str) -> Dict[str, Any]:
        """바코드 입력을 받아 각 항목별로 분해된 데이터를 반환합니다."""
        clean_str = input_str.replace('(', '').replace(')', '').replace(' ', '').strip()
        
        return {
            'udi': input_str,
            'gtin': self._extract_gtin(clean_str),
            'expire_date': self._extract_expire_date(clean_str),
            'lot': self._extract_lot(clean_str),
            'manufacture_date': self._extract_manufacture_date(clean_str),
            'power': 'N/A',
            'name': ''
        }

    def read_from_image(self, image_path: str) -> Optional[str]:
        """이미지 파일에서 바코드 문자열을 읽어옵니다."""
        try:
            image = cv2.imread(image_path)
            if image is None:
                return None
            
            barcodes = pyzbar.decode(image)
            for barcode in barcodes:
                # 첫 번째로 발견된 바코드 내용 반환
                return barcode.data.decode('utf-8')
        except Exception as e:
            print(f"이미지 분석 중 오류 발생: {e}")
        return None

    def _extract_gtin(self, text: str) -> str:
        """AI 01: 제품 고유 식별번호(GTIN) 추출"""
        match = re.search(r'01(\d{14})', text)
        return match.group(1) if match else (text[:14] if len(text) >= 14 else "")

    def _extract_expire_date(self, text: str) -> str:
        """AI 17: 유통기한 추출"""
        match = re.search(r'17(\d{6})', text)
        if not match: return "9999-12-31"

        v = match.group(1)
        try:
            year, month, day = int(v[0:2]) + 2000, int(v[2:4]), int(v[4:6])
            if day == 0: day = calendar.monthrange(year, month)[1]
            return f"{year}-{month:02d}-{day:02d}"
        except: return "9999-12-31"

    def _extract_lot(self, text: str) -> str:
        """AI 10: 로트번호 추출"""
        match = re.search(r'10([a-zA-Z0-9]+)', text)
        if not match: return "N/A"
        return re.split(r'(17|21|11)', match.group(1))[0]

    def _extract_manufacture_date(self, text: str) -> str:
        """AI 11: 제조일자 추출"""
        match = re.search(r'11(\d{6})', text)
        if not match: return ""
        v = match.group(1)
        try: return f"20{v[0:2]}-{v[2:4]}-{v[4:6]}"
        except: return ""
