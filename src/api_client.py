import os
import time
import requests
import logging
import urllib.parse
import json
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
from dotenv import load_dotenv

load_dotenv()

class APIClient:
    """식약처 API 주소 체계를 완벽하게 탐색하는 클라이언트"""

    def __init__(self):
        raw_key = os.getenv("LENS_API_KEY")
        self.api_key = urllib.parse.unquote(raw_key) if raw_key else ""
        self.base_url = os.getenv("LENS_API_BASE_URL").rstrip('/')
        self.logger = logging.getLogger("APIClient")
        logging.basicConfig(level=logging.INFO)

    def fetch_product_info(self, identifier: str) -> Optional[Dict]:
        """주소 후보군을 순차적으로 찔러보며 이름과 도수를 반드시 찾아냅니다."""
        if not identifier: return None
        gtin = identifier.zfill(14)
        
        # [최종 후보 주소군] 
        # 1. 표준코드조회 (이름/도수 확률 높음)
        # 2. 통합정보조회 (아까 데이터 찾았던 곳)
        # 3. 서비스 기본 주소
        endpoints = [
            f"{self.base_url}/getMdeqStdCdInq01",
            f"{self.base_url}/getMdeqStdCdUnityInfoInq01",
            self.base_url
        ]

        for url in endpoints:
            for param in ["gtin_code", "udi_code"]:
                params = {
                    "serviceKey": self.api_key,
                    "type": "json",
                    "pageNo": "1",
                    "numOfRows": "1",
                    param: gtin
                }

                try:
                    response = requests.get(url, params=params, timeout=10)
                    
                    if response.status_code == 200:
                        result = response.json()
                        body = result.get('body', {})
                        items = body.get('items', {})
                        
                        # 데이터 리스트 추출
                        item_list = []
                        if isinstance(items, dict):
                            item_data = items.get('item', [])
                            item_list = item_data if isinstance(item_data, list) else [item_data]
                        elif isinstance(items, list):
                            item_list = items

                        if item_list and len(item_list) > 0:
                            # 모든 층의 데이터를 하나로 통합 (ITEM 안쪽까지)
                            raw_data = item_list[0]
                            final_data = {str(k).upper(): v for k, v in raw_data.items()}
                            
                            # 중첩된 ITEM 상자가 있다면 그 안의 내용도 병합
                            nested = raw_data.get('ITEM') or raw_data.get('item')
                            if isinstance(nested, dict):
                                for nk, nv in nested.items(): final_data[str(nk).upper()] = nv

                            # [추출] 렌즈명(MODEL_NM)과 도수(SPEC_NM)
                            name = final_data.get('MODEL_NM') or final_data.get('PRDLST_NM') or ""
                            spec = final_data.get('SPEC_NM') or "N/A"
                            
                            if name:
                                self.logger.info(f"성공! 주소: {url.split('/')[-1]} / 제품: {name} / 도수: {spec}")
                                return {
                                    'name': str(name).strip(),
                                    'power': str(spec).strip(),
                                    'manufacturer': str(final_data.get('ENTP_NM', 'N/A')),
                                    'gtin': gtin
                                }
                    elif response.status_code == 404:
                        continue # 다음 주소로 시도
                except Exception:
                    continue

        return None

    def sync_with_local_db(self, api_data: Dict, local_data: Dict) -> Dict:
        synced = local_data.copy()
        if api_data:
            synced['name'] = api_data.get('name') or local_data.get('name')
            synced['power'] = api_data.get('power') or local_data.get('power')
        return synced
