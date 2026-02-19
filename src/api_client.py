import os
import time
import requests
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
from dotenv import load_dotenv

load_dotenv()

class APIClient:
    """공공데이터포털(의료기기 표준코드) API 연동 클래스"""

    def __init__(self):
        self.api_key = os.getenv("LENS_API_KEY")
        self.base_url = os.getenv("LENS_API_BASE_URL")
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.cache_ttl = 24
        self.logger = logging.getLogger("APIClient")
        logging.basicConfig(level=logging.INFO)

    def fetch_product_info(self, identifier: str, retries: int = 3) -> Optional[Dict]:
        """UDI 또는 GTIN으로 제품 정보를 조회합니다."""
        if not identifier: return None
        
        # 1. 캐시 확인
        if identifier in self.cache:
            entry = self.cache[identifier]
            if datetime.now() < entry['expiry']: return entry['data']

        # 2. 검색 시도 (gtin_code와 udi_code 두 가지 파라미터를 시도)
        # 먼저 gtin_code로 시도해보고 없으면 udi_code로 시도합니다.
        search_params = ["gtin_code", "udi_code"]
        
        for param_name in search_params:
            url = f"{self.base_url}/getMdeqStdCdUnityInfoInq01"
            params = {
                "serviceKey": self.api_key,
                "type": "json",
                "pageNo": "1",
                "numOfRows": "1",
                param_name: identifier
            }

            for i in range(retries):
                try:
                    response = requests.get(url, params=params, timeout=10)
                    if response.status_code == 200:
                        result = response.json()
                        body = result.get('body', {})
                        items = body.get('items', [])
                        
                        if items and len(items) > 0:
                            item = items[0]
                            # 공공데이터 필드 매핑
                            # MDEQ_PRDLST_NM: 제품명, SPEC_NM: 규격(여기에 도수가 포함됨)
                            data = {
                                'name': item.get('MDEQ_PRDLST_NM') or item.get('PRDLST_NM') or "이름 없는 제품",
                                'power': item.get('SPEC_NM') or "N/A",
                                'manufacturer': item.get('ENTP_NM') or "N/A",
                                'gtin': item.get('GTIN_CODE') or ""
                            }
                            self.cache[identifier] = {
                                'data': data,
                                'expiry': datetime.now() + timedelta(hours=self.cache_ttl)
                            }
                            return data
                    break # 에러 아니면 리트라이 중단하고 다음 파라미터로
                except Exception as e:
                    self.logger.error(f"네트워크 오류: {e}")
                    time.sleep(1)
        
        return None

    def sync_with_local_db(self, api_data: Dict, local_data: Dict) -> Dict:
        synced = local_data.copy()
        synced.update({
            'name': api_data.get('name', local_data.get('name')),
            'power': api_data.get('power', local_data.get('power')),
            'gtin': api_data.get('gtin', local_data.get('gtin')),
            'source': 'api'
        })
        return synced
