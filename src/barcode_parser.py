import cv2
import re
from pyzbar import pyzbar
from datetime import datetime
import calendar
from typing import Dict, Optional, Any

class BarcodeParser:
    """GS1-128 표준 가이드를 준수하는 정밀 바코드 파서"""

    @staticmethod
    def parse_gs1_128(raw_data: str) -> Dict[str, Any]:
        """AI(Application Identifier)를 분석하여 데이터를 정확히 분리합니다."""
        # 불필요한 괄호나 공백 제거
        clean = raw_data.replace('(', '').replace(')', '').strip()
        
        # 결과 기본값
        result = {
            'udi': raw_data,
            'gtin': '',
            'expire_date': '9999-12-31',
            'lot': 'N/A',
            'power': 'N/A',
            'name': ''
        }

        # 1. GTIN (AI: 01) 추출 - 고정 14자리
        if clean.startswith('01'):
            result['gtin'] = clean[2:16]
            remaining = clean[16:]
        elif len(clean) == 13 or len(clean) == 14:
            # 숫자만 들어온 경우
            result['gtin'] = clean.zfill(14)
            remaining = ""
        else:
            # 01이 중간에 있는 경우 검색
            match = re.search(r'01(\d{14})', clean)
            if match:
                result['gtin'] = match.group(1)
                remaining = clean.replace(f"01{result['gtin']}", "")
            else:
                result['gtin'] = clean[:14].zfill(14)
                remaining = clean[14:]

        # 2. 유통기한 (AI: 17) 추출 - 고정 6자리 (YYMMDD)
        exp_match = re.search(r'17(\d{6})', remaining)
        if exp_match:
            val = exp_match.group(1)
            try:
                year = int(val[0:2]) + 2000
                month = int(val[2:4])
                day = int(val[4:6])
                # 일자가 00인 경우 해당 월의 말일로 보정
                if day == 0:
                    day = calendar.monthrange(year, month)[1]
                result['expire_date'] = f"{year}-{month:02d}-{day:02d}"
            except Exception:
                pass

        # 3. 로트 번호 (AI: 10) 추출 - 가변 길이
        lot_match = re.search(r'10([a-zA-Z0-9]+)', remaining)
        if lot_match:
            # 다른 AI(예: 17, 21)가 시작되기 전까지만 로트로 인정
            lot_val = lot_match.group(1)
            # 보통 17이나 21이 뒤에 붙으므로 이를 잘라냄
            lot_val = re.split(r'(17|21|11)', lot_val)[0]
            result['lot'] = lot_val

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
