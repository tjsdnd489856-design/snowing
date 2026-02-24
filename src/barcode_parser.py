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
        # 한글 자판 입력 시 영문으로 변환
        converted_str = self._convert_korean_to_english(input_str)
        
        # 괄호와 공백 제거
        clean_str = converted_str.replace('(', '').replace(')', '').replace(' ', '').strip()
        
        # 결과 저장용 딕셔너리
        result = {
            'udi': converted_str,
            'gtin': '',
            'expire_date': '',
            'lot': 'N/A',
            'manufacture_date': '',
            'power': 'N/A',
            'name': ''
        }

        remaining_str = clean_str
        
        # 무한 루프 방지를 위한 카운터
        loop_limit = 20
        
        while remaining_str and loop_limit > 0:
            loop_limit -= 1
            matched = False
            
            # 1. GTIN (AI: 01) - 14자리
            if remaining_str.startswith('01'):
                if len(remaining_str) >= 16: # 01 + 14자리
                    result['gtin'] = remaining_str[2:16]
                    remaining_str = remaining_str[16:]
                    matched = True
                    continue

            # 2. 제조일자 (AI: 11) - 6자리 (YYMMDD)
            if remaining_str.startswith('11'):
                if len(remaining_str) >= 8:
                    date_val = remaining_str[2:8]
                    # 유효성 검사
                    parsed_date = self._parse_date(date_val)
                    if parsed_date:
                        result['manufacture_date'] = parsed_date
                        remaining_str = remaining_str[8:]
                        matched = True
                        continue

            # 3. 유통기한 (AI: 17) - 6자리 (YYMMDD)
            if remaining_str.startswith('17'):
                if len(remaining_str) >= 8:
                    date_val = remaining_str[2:8]
                    parsed_date = self._parse_date(date_val, is_expiry=True)
                    if parsed_date:
                        result['expire_date'] = parsed_date
                        remaining_str = remaining_str[8:]
                        matched = True
                        continue

            # 4. LOT 번호 (AI: 10) - 가변 길이
            if remaining_str.startswith('10'):
                # 다음 AI 패턴 찾기 (11, 17, 21, 01 등)
                # 정규식으로 가장 먼저 나오는 AI 패턴 찾기
                match = re.search(r'(11\d{6}|17\d{6}|21|01\d{14})', remaining_str[2:])
                
                if match:
                    # 매치된 위치 전까지가 LOT
                    split_idx = match.start() + 2
                    result['lot'] = remaining_str[2:split_idx]
                    remaining_str = remaining_str[split_idx:]
                else:
                    # 뒤에 AI가 없으면 끝까지 LOT
                    result['lot'] = remaining_str[2:]
                    remaining_str = ""
                matched = True
                continue

            # 5. 일련번호 (AI: 21) - 가변 길이
            if remaining_str.startswith('21'):
                # 다음 AI 패턴 찾기
                match = re.search(r'(11\d{6}|17\d{6}|10|01\d{14})', remaining_str[2:])
                
                if match:
                    split_idx = match.start() + 2
                    remaining_str = remaining_str[split_idx:]
                else:
                    remaining_str = ""
                matched = True
                continue

            # 매치되는 AI가 없으면 루프 종료
            if not matched:
                break
        
        # 01로 시작하지 않았더라도 중간에 있을 수 있음 (안전장치)
        if not result['gtin']:
            match = re.search(r'01(\d{14})', clean_str)
            if match:
                result['gtin'] = match.group(1)

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

    def _convert_korean_to_english(self, text: str) -> str:
        """한글 자판 입력을 영문 자판 입력으로 변환합니다."""
        korean_map = {
            'ㅂ': 'q', 'ㅈ': 'w', 'ㄷ': 'e', 'ㄱ': 'r', 'ㅅ': 't',
            'ㅛ': 'y', 'ㅕ': 'u', 'ㅑ': 'i', 'ㅐ': 'o', 'ㅔ': 'p',
            'ㅁ': 'a', 'ㄴ': 's', 'ㅇ': 'd', 'ㄹ': 'f', 'ㅎ': 'g',
            'ㅗ': 'h', 'ㅓ': 'j', 'ㅏ': 'k', 'ㅣ': 'l',
            'ㅋ': 'z', 'ㅌ': 'x', 'ㅊ': 'c', 'ㅍ': 'v', 'ㅠ': 'b',
            'ㅜ': 'n', 'ㅡ': 'm',
            'ㅃ': 'Q', 'ㅉ': 'W', 'ㄸ': 'E', 'ㄲ': 'R', 'ㅆ': 'T',
            'ㅒ': 'O', 'ㅖ': 'P'
        }
        
        result = []
        for char in text:
            result.append(korean_map.get(char, char))
        return "".join(result)

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
