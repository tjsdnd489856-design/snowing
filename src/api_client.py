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
        """정부 DB에서 모델명(브랜드명)과 규격(도수)을 찾아옵니다."""
        if not identifier: return None
        
        if identifier in self.cache:
            entry = self.cache[identifier]
            if datetime.now() < entry['expiry']: return entry['data']

        # 엔드포인트가 중복되지 않도록 처리
        endpoint = "getMdeqStdCdUnityInfoInq01"
        if not self.base_url.endswith(endpoint):
            url = f"{self.base_url}/{endpoint}" if not self.base_url.endswith('/') else f"{self.base_url}{endpoint}"
        else:
            url = self.base_url

        # gtin_code로 먼저 찾고, 없으면 udi_code로 시도
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
                    response = requests.get(url, params=params, timeout=10)
                    if response.status_code == 200:
                        result = response.json()
                        # 공공데이터 API의 복잡한 계층 구조 파싱
                        body = result.get('body', {})
                        items = body.get('items', [])
                        
                        if items and len(items) > 0:
                            item = items[0]
                            # MODEL_NM: 우리가 아는 실제 제품명 (예: 클라렌 아이리스)
                            # SPEC_NM: 도수, 곡률 등이 포함된 상세 규격
                            # MDEQ_PRDLST_NM: 품목명 (예: 소프트콘택트렌즈)
                            name = item.get('MODEL_NM') or item.get('PRDLST_NM') or item.get('MDEQ_PRDLST_NM')
                            power = item.get('SPEC_NM') or "N/A"
                            
                            data = {
                                'name': name,
                                'power': power,
                                'manufacturer': item.get('ENTP_NM', 'N/A'),
                                'gtin': item.get('GTIN_CODE', identifier)
                            }
                            
                            self.cache[identifier] = {
                                'data': data,
                                'expiry': datetime.now() + timedelta(hours=self.cache_ttl)
                            }
                            return data
                    break 
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
