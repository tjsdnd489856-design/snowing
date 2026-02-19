import os
import time
import requests
import logging
import urllib.parse
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
from dotenv import load_dotenv

load_dotenv()

class APIClient:
    """공공데이터포털 의료기기 API 전용 클라이언트"""

    def __init__(self):
        # 공공데이터포털은 키가 이미 인코딩되어 오는 경우가 많아 처리가 중요합니다.
        raw_key = os.getenv("LENS_API_KEY")
        self.api_key = urllib.parse.unquote(raw_key) if raw_key else ""
        self.base_url = os.getenv("LENS_API_BASE_URL")
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.cache_ttl = 24
        self.logger = logging.getLogger("APIClient")
        logging.basicConfig(level=logging.INFO)

    def fetch_product_info(self, identifier: str, retries: int = 2) -> Optional[Dict]:
        """정부 DB에서 정보를 가져옵니다. (인증키 오류 방지 로직 포함)"""
        if not identifier or not self.api_key: return None
        
        if identifier in self.cache:
            entry = self.cache[identifier]
            if datetime.now() < entry['expiry']: return entry['data']

        endpoint = "getMdeqStdCdUnityInfoInq01"
        url = self.base_url.rstrip('/') + '/' + endpoint
        
        # GTIN 번호가 14자리가 아니면 보정 (앞에 0을 채움)
        gtin = identifier.zfill(14)

        for param_name in ["gtin_code", "udi_code"]:
            # 공공데이터 API 전용 파라미터 구성
            params = {
                "serviceKey": self.api_key,
                "type": "json",
                "pageNo": "1",
                "numOfRows": "1",
                param_name: gtin
            }

            for i in range(retries):
                try:
                    # verify=False는 간혹 발생하는 SSL 보안 인증 오류 방지용입니다.
                    response = requests.get(url, params=params, timeout=10, verify=True)
                    
                    if response.status_code == 200:
                        try:
                            result = response.json()
                            items = result.get('body', {}).get('items', [])
                            
                            if items:
                                item = items[0]
                                # 모델명(브랜드) -> 제품명 -> 품목명 순으로 가장 정확한 이름을 찾습니다.
                                name = (item.get('MODEL_NM') or 
                                        item.get('PRDLST_NM') or 
                                        item.get('MDEQ_PRDLST_NM'))
                                
                                data = {
                                    'name': str(name).strip() if name else "",
                                    'power': str(item.get('SPEC_NM') or "N/A").strip(),
                                    'manufacturer': str(item.get('ENTP_NM') or "N/A").strip(),
                                    'gtin': gtin
                                }
                                
                                if data['name']: # 이름이 있을 때만 캐시 저장
                                    self.cache[identifier] = {
                                        'data': data,
                                        'expiry': datetime.now() + timedelta(hours=self.cache_ttl)
                                    }
                                    return data
                        except Exception:
                            self.logger.error("API 응답 해석 오류 (데이터 없음)")
                    
                except Exception as e:
                    self.logger.error(f"API 접속 실패: {e}")
                    time.sleep(0.5)
        
        return None

    def sync_with_local_db(self, api_data: Dict, local_data: Dict) -> Dict:
        synced = local_data.copy()
        if api_data:
            synced['name'] = api_data.get('name') or local_data.get('name')
            synced['power'] = api_data.get('power') or local_data.get('power')
        return synced
