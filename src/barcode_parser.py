import cv2
import re
from pyzbar import pyzbar
from datetime import datetime
import calendar
from typing import Dict, Optional, Any

class BarcodeParser:
    """UDI/GS1 바코드뿐만 아니라 일반 숫자 바코드도 인식하는 파서"""

    @staticmethod
    def parse_gs1_128(raw_data: str) -> Dict[str, Any]:
        """GS1-128 또는 UDI 문자열 파싱 (유연한 숫자 인식 포함)"""
        clean_data = raw_data.replace('(', '').replace(')', '')
        # 기본 결과 셋 (숫자만 들어온 경우 gtin으로 우선 간주)
        result = {'udi': raw_data, 'gtin': '', 'expire_date': '9999-12-31', 'lot': 'N/A', 'manufacture_date': '', 'power': 'N/A', 'name': ''}

        # 만약 입력이 순수 숫자(13~14자리)라면 GTIN으로 바로 할당
        if raw_data.isdigit() and len(raw_data) in [13, 14]:
            result['gtin'] = raw_data
            return result

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
                    try:
                        year = int(val[0:2]) + 2000
                        month = int(val[2:4])
                        day = int(val[4:6])
                        if day == 0:
                            if month == 0: month = 1
                            day = calendar.monthrange(year, month)[1]
                        val = f"{year}-{month:02d}-{day:02d}"
                    except Exception:
                        val = "9999-12-31"
                result[key] = val
        
        # 정규표현식으로 gtin을 못 찾았는데 숫자만 있는 경우 재확인
        if not result['gtin']:
            digits = re.findall(r'\d{13,14}', clean_data)
            if digits: result['gtin'] = digits[0]
            
        return result

    def read_from_image(self, image_path: str, retries: int = 3) -> Optional[str]:
        image = cv2.imread(image_path)
        if image is None: return None
        for i in range(retries):
            if i == 0: processed = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            elif i == 1: _, processed = cv2.threshold(processed, 127, 255, cv2.THRESH_BINARY)
            else: processed = cv2.morphologyEx(processed, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)))
            barcodes = pyzbar.decode(processed)
            if barcodes: return barcodes[0].data.decode('utf-8')
        return None

    def process_scanner_input(self, input_str: str) -> Dict[str, Any]:
        return self.parse_gs1_128(input_str.strip())
