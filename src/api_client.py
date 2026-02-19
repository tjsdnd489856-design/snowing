import os
import time
import requests
import logging
import urllib.parse
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
from dotenv import load_dotenv

load_dotenv()

class APIClient:
    """JSON과 XML 응답을 모두 처리하는 통합 정부 API 클라이언트"""

    def __init__(self):
        raw_key = os.getenv("LENS_API_KEY")
        self.api_key = urllib.parse.unquote(raw_key) if raw_key else ""
        self.base_url = os.getenv("LENS_API_BASE_URL").rstrip('/')
        self.logger = logging.getLogger("APIClient")
        logging.basicConfig(level=logging.INFO)

    def _extract_from_text(self, text: str) -> Dict[str, str]:
        """텍스트에서 제품명과 도수를 추출 (예: PURSFIT 1DAY AIRCLEAR(10P) -7.00)"""
        if not text: return {"name": "알 수 없는 제품", "power": "N/A"}
        
        # 도수 패턴 추출 (-7.00, +1.50 등)
        power_match = re.search(r'([+-]?\d+\.\d{2})', text)
        power = power_match.group(1) if power_match else "N/A"
        
        # 제품명 정리
        name = text.replace(power, "") if power != "N/A" else text
        name = re.sub(r'\(\d+P\)', '', name) # 수량 제거
        name = name.strip("- ").strip()
        
        return {"name": name, "power": power}

    def fetch_product_info(self, identifier: str) -> Optional[Dict]:
        """JSON/XML 응답을 모두 분석하여 PRDT_ADD_EXPL 필드를 찾아냅니다."""
        if not identifier: return None
        gtin = identifier.zfill(14)
        url = f"{self.base_url}/getMdeqStdCdUnityInfoInq01"
        
        for param in ["udi_code", "gtin_code", "udi_di"]:
            # 인증키 보호를 위해 직접 조립
            full_url = f"{url}?serviceKey={self.api_key}&type=json&pageNo=1&numOfRows=1&{param}={gtin}"
            
            try:
                response = requests.get(full_url, timeout=10)
                if response.status_code == 200:
                    content = response.text.strip()
                    raw_info_text = None

                    # 1. XML 응답 처리
                    if content.startswith('<'):
                        try:
                            root = ET.fromstring(content)
                            for elem in root.iter():
                                if 'PRDT_ADD_EXPL' in elem.tag and elem.text:
                                    raw_info_text = elem.text
                                    break
                        except Exception as e:
                            self.logger.error(f"XML 파싱 에러: {e}")

                    # 2. JSON 응답 처리
                    else:
                        try:
                            res_json = response.json()
                            def find_field(obj):
                                if isinstance(obj, dict):
                                    if obj.get('PRDT_ADD_EXPL'): return obj['PRDT_ADD_EXPL']
                                    for v in obj.values():
                                        res = find_field(v)
                                        if res: return res
                                elif isinstance(obj, list):
                                    for i in obj:
                                        res = find_field(i)
                                        if res: return res
                                return None
                            raw_info_text = find_field(res_json)
                        except Exception as e:
                            self.logger.error(f"JSON 파싱 에러: {e}")

                    if raw_info_text:
                        self.logger.info(f"데이터 추출 성공: {raw_info_text}")
                        info = self._extract_from_text(raw_info_text)
                        return {
                            'name': info['name'],
                            'power': info['power'],
                            'manufacturer': "정부 DB 등록 제품",
                            'gtin': gtin
                        }
            except Exception as e:
                self.logger.error(f"접속 에러: {e}")
        
        return None

    def sync_with_local_db(self, api_data: Dict, local_data: Dict) -> Dict:
        synced = local_data.copy()
        if api_data:
            synced['name'] = api_data.get('name') or local_data.get('name')
            synced['power'] = api_data.get('power') or local_data.get('power')
        return synced
