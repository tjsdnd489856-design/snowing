import os
import time
import requests
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
from dotenv import load_dotenv

load_dotenv()

class APIClient:
    """식약처 의료기기 표준코드 DB 연동 클래스"""

    def __init__(self):
        self.api_key = os.getenv("LENS_API_KEY")
        self.base_url = os.getenv("LENS_API_BASE_URL")
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.cache_ttl = 24
        self.logger = logging.getLogger("APIClient")
        logging.basicConfig(level=logging.INFO)

    def fetch_product_info(self, identifier: str, retries: int = 3) -> Optional[Dict]:
        """정부 DB에서 제품 정보를 가져오며 이름 누락을 방지합니다."""
        if not identifier: return None
        
        if identifier in self.cache:
            entry = self.cache[identifier]
            if datetime.now() < entry['expiry']: return entry['data']

        endpoint = "getMdeqStdCdUnityInfoInq01"
        url = self.base_url.rstrip('/') + '/' + endpoint if endpoint not in self.base_url else self.base_url

        for param_name in ["gtin_code", "udi_code"]:
            params = {
                "serviceKey": self.api_key,
                "type": "json",
                "pageNo": "1",
                "numOfRows": "1",
                param_name: identifier
            }

            for i in range(retries):
                try:
                    # 공공데이터 API 호출 시 인증키 인코딩 이슈 대응을 위해 주소에 직접 붙이지 않고 params 사용
                    response = requests.get(url, params=params, timeout=10)
                    if response.status_code == 200:
                        result = response.json()
                        body = result.get('body', {})
                        items = body.get('items', [])
                        
                        if items:
                            item = items[0]
                            # 최대한 이름을 찾기 위해 가능한 모든 필드를 순서대로 확인
                            name = (item.get('MODEL_NM') or 
                                    item.get('PRDLST_NM') or 
                                    item.get('MDEQ_PRDLST_NM') or 
                                    "이름 미등록 제품")
                            
                            data = {
                                'name': str(name).strip(),
                                'power': str(item.get('SPEC_NM') or "N/A").strip(),
                                'manufacturer': str(item.get('ENTP_NM') or "N/A").strip(),
                                'gtin': str(item.get('GTIN_CODE') or identifier).strip()
                            }
                            
                            self._save_to_cache(identifier, data)
                            return data
                    break 
                except Exception as e:
                    self.logger.error(f"네트워크 오류: {e}")
                    time.sleep(1)
        
        return None

    def _save_to_cache(self, key: str, data: Dict):
        self.cache[key] = {
            'data': data,
            'expiry': datetime.now() + timedelta(hours=self.cache_ttl)
        }

    def sync_with_local_db(self, api_data: Dict, local_data: Dict) -> Dict:
        synced = local_data.copy()
        # API 데이터가 우선이지만, API 데이터의 값이 비어있을 경우 기존 값 유지
        synced['name'] = api_data.get('name') or local_data.get('name')
        synced['power'] = api_data.get('power') or local_data.get('power')
        synced['gtin'] = api_data.get('gtin') or local_data.get('gtin')
        synced['source'] = 'api'
        return synced
