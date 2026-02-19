import re
import calendar
from datetime import datetime
from typing import Dict, Any, Optional

class BarcodeParser:
    """GS1 표준 AI 식별자를 정밀 분석하여 UDI-DI, 유통기한, 로트번호를 추출하는 파서"""

    @staticmethod
    def parse_gs1_128(raw_data: str) -> Dict[str, Any]:
        """GS1-128 바코드를 AI 블록별로 해체합니다."""
        # 괄호 제거 및 공백 정리
        clean = raw_data.replace('(', '').replace(')', '').replace(' ', '').strip()
        
        result = {
            'udi': raw_data,
            'gtin': '',
            'expire_date': '9999-12-31',
            'lot': 'N/A',
            'manufacture_date': '',
            'power': 'N/A',
            'name': ''
        }

        # 1. AI 01 (GTIN / UDI-DI) - 고정 14자리
        # 문자열 내에서 01로 시작하거나 01을 포함하는 14자리 숫자를 찾습니다.
        gtin_match = re.search(r'01(\d{14})', clean)
        if gtin_match:
            result['gtin'] = gtin_match.group(1)
        elif len(clean) >= 14:
            # 01이 생략된 경우를 대비해 앞의 14자리를 GTIN으로 시도
            result['gtin'] = clean[:14]

        # 2. AI 17 (유통기한) - 고정 6자리 (YYMMDD)
        exp_match = re.search(r'17(\d{6})', clean)
        if exp_match:
            val = exp_match.group(1)
            try:
                year = int(val[0:2]) + 2000
                month = int(val[2:4])
                day = int(val[4:6])
                if day == 0: # 일자가 00이면 해당 월 말일로
                    day = calendar.monthrange(year, month)[1]
                result['expire_date'] = f"{year}-{month:02d}-{day:02d}"
            except Exception: pass

        # 3. AI 10 (로트번호) - 가변 길이 (최대 20자)
        # 10 뒤에 오되, 다른 AI(17, 21, 11)가 시작되기 전까지만 추출
        lot_match = re.search(r'10([a-zA-Z0-9]+)', clean)
        if lot_match:
            lot_val = lot_match.group(1)
            # 다른 주요 AI 코드로 끊기
            lot_val = re.split(r'(17|21|11)', lot_val)[0]
            result['lot'] = lot_val

        # 4. AI 11 (제조일자) - 고정 6자리
        mfg_match = re.search(r'11(\d{6})', clean)
        if mfg_match:
            val = mfg_match.group(1)
            try:
                result['manufacture_date'] = f"20{val[0:2]}-{val[2:4]}-{val[4:6]}"
            except Exception: pass

        return result

    def process_scanner_input(self, input_str: str) -> Dict[str, Any]:
        return self.parse_gs1_128(input_str)
