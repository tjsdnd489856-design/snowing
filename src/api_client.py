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

    def _get_from_cache(self, udi: str) -> Optional[Dict]:
        if udi in self.cache:
            entry = self.cache[udi]
            if datetime.now() < entry['expiry']:
                return entry['data']
            del self.cache[udi]
        return None

    def _save_to_cache(self, udi: str, data: Dict):
        self.cache[udi] = {
            'data': data,
            'expiry': datetime.now() + timedelta(hours=self.cache_ttl)
        }

    def fetch_product_info(self, udi: str, retries: int = 3) -> Optional[Dict]:
        """공공데이터 API를 호출하여 의료기기 정보를 가져옵니다."""
        cached_data = self._get_from_cache(udi)
        if cached_data:
            return cached_data

        # 공공데이터포털 상세 코드 조회 엔드포인트 (기본값에 오퍼레이션 추가)
        url = f"{self.base_url}/getMdeqStdCdUnityInfoInq01"
        
        # 공공데이터 규격 파라미터
        params = {
            "serviceKey": self.api_key,
            "type": "json",
            "udi_code": udi,  # UDI 코드로 검색
            "pageNo": "1",
            "numOfRows": "1"
        }

        for i in range(retries):
            try:
                # 공공데이터 API는 인증키가 인코딩된 상태로 전달되어야 할 때가 있어 params로 전달
                response = requests.get(url, params=params, timeout=10)
                
                if response.status_code == 200:
                    result = response.json()
                    # 공공데이터 결과 구조 분석 (body -> items -> item)
                    try:
                        items = result.get('body', {}).get('items', [])
                        if items:
                            item = items[0]
                            data = {
                                'name': item.get('MDEQ_PRDLST_NM', '알 수 없는 제품'),
                                'power': item.get('SPEC_NM', 'N/A'),
                                'manufacturer': item.get('ENTP_NM', 'N/A'),
                                'gtin': item.get('GTIN_CODE', '')
                            }
                            self._save_to_cache(udi, data)
                            return data
                    except (IndexError, AttributeError):
                        self.logger.warning("검색 결과가 없습니다.")
                        return None
                
                elif response.status_code == 429:
                    time.sleep(2 ** i)
                else:
                    self.logger.error(f"API 오류: {response.status_code}")
                    break

            except Exception as e:
                self.logger.error(f"네트워크 오류: {e}")
                time.sleep(1)

        return None

    def sync_with_local_db(self, api_data: Dict, local_data: Dict, policy: str = "api_priority") -> Dict:
        synced = local_data.copy()
        if policy == "api_priority":
            synced.update({
                'name': api_data.get('name', local_data.get('name')),
                'power': api_data.get('power', local_data.get('power')),
                'gtin': api_data.get('gtin', local_data.get('gtin')),
                'source': 'api',
                'change_log': f"Synced from Public Data API at {datetime.now()}"
            })
        return synced
