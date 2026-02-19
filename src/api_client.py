import os
import time
import requests
import logging
import urllib.parse
import re
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
from dotenv import load_dotenv

load_dotenv()

class APIClient:
    """정부 API 응답에서 PRDT_ADD_EXPL 필드를 정밀 분석하는 클라이언트"""

    def __init__(self):
        raw_key = os.getenv("LENS_API_KEY")
        self.api_key = urllib.parse.unquote(raw_key) if raw_key else ""
        self.base_url = os.getenv("LENS_API_BASE_URL").rstrip('/')
        self.logger = logging.getLogger("APIClient")
        logging.basicConfig(level=logging.INFO)

    def _extract_info(self, text: str) -> Dict[str, str]:
        """텍스트에서 제품명과 도수를 분리합니다. (예: PURSFIT 1DAY AIRCLEAR(10P) -7.00)"""
        # 1. 도수 찾기 (예: -7.00, +2.50 등)
        power_match = re.search(r'([+-]?\d+\.\d{2})', text)
        power = power_match.group(1) if power_match else "N/A"
        
        # 2. 제품명 정리 (도수 부분과 불필요한 괄호 제거)
        name = text
        if power != "N/A":
            name = name.replace(power, "")
        
        # (10P), (30P) 같은 수량 정보나 특수문자 정리
        name = re.sub(r'\(\d+P\)', '', name)
        name = name.strip("- ").strip()
        
        return {"name": name, "power": power}

    def fetch_product_info(self, identifier: str) -> Optional[Dict]:
        """PRDT_ADD_EXPL 필드를 분석하여 제품명과 도수를 완벽히 가져옵니다."""
        if not identifier: return None
        
        gtin = identifier.zfill(14)
        # 확인된 정확한 엔드포인트
        url = f"{self.base_url}/getMdeqStdCdUnityInfoInq01"
        
        for param in ["udi_code", "gtin_code", "udi_di"]:
            full_url = f"{url}?serviceKey={self.api_key}&type=json&pageNo=1&numOfRows=1&{param}={gtin}"
            try:
                response = requests.get(full_url, timeout=10)
                if response.status_code == 200:
                    res_data = response.json()
                    
                    # 모든 필드를 평면화하여 검색
                    def walk(obj):
                        if isinstance(obj, dict):
                            # 우리가 찾은 핵심 필드 확인
                            if 'PRDT_ADD_EXPL' in obj and obj['PRDT_ADD_EXPL']:
                                return obj['PRDT_ADD_EXPL']
                            for v in obj.values():
                                res = walk(v)
                                if res: return res
                        elif isinstance(obj, list):
                            for i in obj:
                                res = walk(i)
                                if res: return res
                        return None

                    raw_text = walk(res_data)
                    
                    if raw_text:
                        self.logger.info(f"데이터 발견: {raw_text}")
                        extracted = self._extract_info(raw_text)
                        
                        return {
                            'name': extracted['name'],
                            'power': extracted['power'],
                            'manufacturer': "정부 DB 등록 제품",
                            'gtin': gtin
                        }
            except Exception as e:
                self.logger.error(f"오류 발생: {e}")
                continue
        
        return None

    def sync_with_local_db(self, api_data: Dict, local_data: Dict) -> Dict:
        synced = local_data.copy()
        if api_data:
            synced['name'] = api_data.get('name') or local_data.get('name')
            synced['power'] = api_data.get('power') or local_data.get('power')
        return synced
