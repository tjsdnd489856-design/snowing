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
        # 괄호와 공백 제거
        clean_str = input_str.replace('(', '').replace(')', '').replace(' ', '').strip()
        
        # 결과 저장용 딕셔너리
        result = {
            'udi': input_str,
            'gtin': '',
            'expire_date': '',
            'lot': 'N/A',
            'manufacture_date': '',
            'power': 'N/A',
            'name': ''
        }

        # 순차적 파싱을 위해 문자열 복사
        remaining_str = clean_str

        # 1. GTIN (AI: 01) - 고정 길이 14자리
        if remaining_str.startswith('01'):
            if len(remaining_str) >= 16: # 01 + 14자리
                result['gtin'] = remaining_str[2:16]
                remaining_str = remaining_str[16:]
        
        # 01로 시작하지 않았더라도 중간에 있을 수 있음 (안전장치)
        if not result['gtin']:
            match = re.search(r'01(\d{14})', clean_str)
            if match:
                result['gtin'] = match.group(1)
                # 이미 파싱된 부분 제거는 복잡하므로 여기서는 값만 추출

        # 2. 날짜 정보 파싱 (AI: 11, 17) - 고정 길이 6자리
        # 순서가 섞여 있을 수 있으므로 반복적으로 찾기
        while True:
            found = False
            # 제조일자 (11)
            if remaining_str.startswith('11'):
                if len(remaining_str) >= 8: # 11 + 6자리
                    date_val = remaining_str[2:8]
                    # 유효한 날짜인지 확인
                    parsed_date = self._parse_date(date_val)
                    if parsed_date:
                        result['manufacture_date'] = parsed_date
                        remaining_str = remaining_str[8:]
                        found = True
                        continue

            # 유통기한 (17)
            if remaining_str.startswith('17'):
                if len(remaining_str) >= 8: # 17 + 6자리
                    date_val = remaining_str[2:8]
                    parsed_date = self._parse_date(date_val, is_expiry=True)
                    if parsed_date:
                        result['expire_date'] = parsed_date
                        remaining_str = remaining_str[8:]
                        found = True
                        continue
            
            if not found:
                break

        # 3. LOT 번호 (AI: 10) - 가변 길이
        if remaining_str.startswith('10'):
            # LOT 번호 뒤에 다른 AI가 올 수 있음
            lot_raw = remaining_str[2:]
            
            # 뒤에 11(제조일), 17(유통기한), 21(일련번호) 같은 AI 패턴이 나오면 끊어야 함
            # 정규식으로 가장 먼저 나오는 AI 패턴 찾기
            # 주의: LOT 번호 자체에 숫자가 포함될 수 있으므로, AI 패턴과 구분하기 어려움.
            # 하지만 GS1 표준상 AI 앞에는 FNC1이 있어야 함. 여기서는 FNC1이 없으므로 추정해야 함.
            
            # 우리가 처리하지 못한 11, 17이 뒤에 남아있다면 여기서 끊어줌
            match = re.search(r'(11\d{6}|17\d{6}|21)', lot_raw)
            if match:
                lot_val = lot_raw[:match.start()]
            else:
                lot_val = lot_raw
            
            result['lot'] = lot_val

        # 만약 순차 파싱으로 LOT를 못 찾았는데, 원본 문자열에는 있었던 경우 (순서가 섞인 경우)
        if result['lot'] == 'N/A' and '10' in clean_str:
             # GTIN(01)과 날짜(11, 17)를 제외한 나머지 문자열에서 찾기
             # (이 부분은 매우 복잡해질 수 있어 생략하거나 간단히 처리)
             pass
        
        # 유통기한 기본값 처리
        if not result['expire_date']:
            result['expire_date'] = "9999-12-31"

        return result

    def read_from_image(self, image_path: str) -> Optional[str]:
        """이미지 파일에서 바코드 문자열을 읽어옵니다."""
        try:
            image = cv2.imread(image_path)
            if image is None:
                return None
            
            barcodes = pyzbar.decode(image)
            for barcode in barcodes:
                return barcode.data.decode('utf-8')
        except Exception as e:
            print(f"이미지 분석 중 오류 발생: {e}")
        return None

    def _parse_date(self, text: str, is_expiry: bool = False) -> str:
        """YYMMDD 형식의 문자열을 YYYY-MM-DD로 변환"""
        if not text or len(text) != 6:
            return ""
        
        try:
            year = int(text[0:2]) + 2000
            month = int(text[2:4])
            day = int(text[4:6])

            if day == 0:
                day = calendar.monthrange(year, month)[1]
            
            valid_date = datetime(year, month, day)
            return valid_date.strftime("%Y-%m-%d")
        except (ValueError, IndexError):
            # 날짜 형식이 아니면 빈 문자열 반환 (유효하지 않은 날짜)
            return ""

    # 기존 메서드들은 호환성을 위해 남겨두거나 내부적으로 사용하지 않음
    def _extract_gtin(self, text: str) -> str: return ""
    def _extract_expire_date(self, text: str) -> str: return ""
    def _extract_lot(self, text: str) -> str: return ""
    def _extract_manufacture_date(self, text: str) -> str: return ""
