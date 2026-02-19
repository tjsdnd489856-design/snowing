import os
import time
import requests
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
from dotenv import load_dotenv

load_dotenv()

class APIClient:
    """외부 제품 메타데이터 API 연동 클래스"""

    def __init__(self):
        self.api_key = os.getenv("LENS_API_KEY")
        self.base_url = os.getenv("LENS_API_BASE_URL", "https://api.example.com/v1")
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.cache_ttl = 24  # 시간
        self.logger = logging.getLogger("APIClient")
        logging.basicConfig(level=logging.INFO)

    def _get_from_cache(self, gtin: str) -> Optional[Dict]:
        """캐시에서 데이터 조회 (TTL 체크)"""
        if gtin in self.cache:
            entry = self.cache[gtin]
            if datetime.now() < entry['expiry']:
                return entry['data']
            del self.cache[gtin]
        return None

    def _save_to_cache(self, gtin: str, data: Dict):
        """데이터를 캐시에 저장"""
        self.cache[gtin] = {
            'data': data,
            'expiry': datetime.now() + timedelta(hours=self.cache_ttl)
        }

    def fetch_product_info(self, gtin: str, retries: int = 3) -> Optional[Dict]:
        """외부 API로부터 제품 정보 조회 (재시도 로직 포함)"""
        # 1. 캐시 확인
        cached_data = self._get_from_cache(gtin)
        if cached_data:
            self.logger.info(f"캐시에서 데이터를 불러왔습니다: {gtin}")
            return cached_data

        headers = {"Authorization": f"Bearer {self.api_key}"}
        url = f"{self.base_url}/products/{gtin}"

        for i in range(retries):
            try:
                response = requests.get(url, headers=headers, timeout=5)
                
                if response.status_code == 200:
                    data = response.json()
                    self._save_to_cache(gtin, data)
                    return data
                elif response.status_code == 429:
                    self.logger.warning("Rate limit 도달. 대기 후 재시도...")
                    time.sleep(2 ** i)  # 지수 백오프
                elif 500 <= response.status_code < 600:
                    self.logger.error(f"서버 오류 ({response.status_code}). 재시도 중...")
                    time.sleep(1)
                else:
                    self.logger.error(f"API 오류: {response.status_code}")
                    break

            except requests.exceptions.RequestException as e:
                self.logger.error(f"네트워크 오류: {e}")
                time.sleep(1)

        return None

    def sync_with_local_db(self, api_data: Dict, local_data: Dict, policy: str = "api_priority") -> Dict:
        """외부 API 데이터와 로컬 데이터 동기화 정책 적용"""
        synced = local_data.copy()
        
        if policy == "api_priority":
            # API 데이터로 덮어쓰기 (중요 정보 우선)
            synced.update({
                'name': api_data.get('name', local_data.get('name')),
                'power': api_data.get('power', local_data.get('power')),
                'source': 'api',
                'change_log': f"Synced from API at {datetime.now()}"
            })
        
        return synced
