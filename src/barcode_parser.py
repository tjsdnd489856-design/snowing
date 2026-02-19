import cv2
import re
from pyzbar import pyzbar
from datetime import datetime
from typing import Dict, Optional, Any

class BarcodeParser:
    """UDI/GS1 바코드 파싱 및 이미지 인식 클래스"""

    # GS1 Application Identifiers (AI) 매핑
    AI_MAP = {
        '01': 'gtin',
        '17': 'expire_date',
        '10': 'lot',
        '11': 'manufacture_date',
        '21': 'serial',
    }

    @staticmethod
    def parse_gs1_128(raw_data: str) -> Dict[str, Any]:
        """GS1-128 또는 UDI 문자열 파싱"""
        # (01) 형식 또는 일반 숫자가 혼합된 경우 처리
        clean_data = raw_data.replace('(', '').replace(')', '')
        result = {'udi': raw_data, 'gtin': '', 'expire_date': '', 'lot': '', 'manufacture_date': '', 'power': 'N/A'}

        # 정규표현식을 이용한 AI 추출 (간소화된 로직)
        # 실제 환경에서는 AI별 고정 길이를 고려한 정교한 파서가 필요함
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
                    # YYMMDD -> YYYY-MM-DD 변환
                    try:
                        val = datetime.strptime(val, "%y%m%d").strftime("%Y-%m-%d")
                    except ValueError:
                        pass
                result[key] = val
        
        return result

    def read_from_image(self, image_path: str, retries: int = 3) -> Optional[str]:
        """이미지 파일에서 바코드 읽기 (전처리 및 재시도 포함)"""
        image = cv2.imread(image_path)
        if image is None:
            return None

        for i in range(retries):
            # 전처리 단계
            if i == 0:
                processed = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            elif i == 1:
                _, processed = cv2.threshold(processed, 127, 255, cv2.THRESH_BINARY)
            else:
                kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
                processed = cv2.morphologyEx(processed, cv2.MORPH_CLOSE, kernel)

            barcodes = pyzbar.decode(processed)
            if barcodes:
                return barcodes[0].data.decode('utf-8')
        
        return None

    def process_scanner_input(self, input_str: str) -> Dict[str, Any]:
        """키보드 입력 방식(바코드 스캐너) 데이터 처리"""
        return self.parse_gs1_128(input_str.strip())
