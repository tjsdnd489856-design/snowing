import cv2
import re
from pyzbar import pyzbar
from datetime import datetime
import calendar
from typing import Dict, Optional, Any

class BarcodeParser:
    """UDI/GS1 바코드 파싱 및 이미지 인식 클래스"""

    @staticmethod
    def parse_gs1_128(raw_data: str) -> Dict[str, Any]:
        """GS1-128 또는 UDI 문자열 파싱 (유연한 날짜 처리 포함)"""
        clean_data = raw_data.replace('(', '').replace(')', '')
        result = {'udi': raw_data, 'gtin': '', 'expire_date': '9999-12-31', 'lot': '', 'manufacture_date': '', 'power': 'N/A', 'name': ''}

        patterns = {
            'gtin': r'01(\d{14})',
            'expire_date': r'17(\d{6})',
            'lot': r'10([a-zA-Z0-9]{1,20})',
            'manufacture_date': r'11(\d{6})',
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, clean_data)
            if match:
                val = match.group(1)
                if key in ['expire_date', 'manufacture_date']:
                    # YYMMDD 처리
                    year = int(val[0:2]) + 2000
                    month = int(val[2:4])
                    day = int(val[4:6])

                    # 일자가 00인 경우 해당 월의 말일로 보정
                    if day == 0:
                        if month == 0: month = 1 # 월도 00이면 1월로
                        day = calendar.monthrange(year, month)[1]
                    
                    try:
                        val = f"{year}-{month:02d}-{day:02d}"
                    except ValueError:
                        val = "9999-12-31" # 오류 시 먼 미래 날짜로 대체
                result[key] = val
        
        return result

    def read_from_image(self, image_path: str, retries: int = 3) -> Optional[str]:
        image = cv2.imread(image_path)
        if image is None: return None

        for i in range(retries):
            if i == 0: processed = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            elif i == 1: _, processed = cv2.threshold(processed, 127, 255, cv2.THRESH_BINARY)
            else:
                kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
                processed = cv2.morphologyEx(processed, cv2.MORPH_CLOSE, kernel)

            barcodes = pyzbar.decode(processed)
            if barcodes: return barcodes[0].data.decode('utf-8')
        return None

    def process_scanner_input(self, input_str: str) -> Dict[str, Any]:
        return self.parse_gs1_128(input_str.strip())
