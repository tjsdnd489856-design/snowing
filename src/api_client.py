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
    """공공데이터포털 의료기기 전용 정밀 파싱 클라이언트"""

    def __init__(self):
        raw_key = os.getenv("LENS_API_KEY")
        self.api_key = urllib.parse.unquote(raw_key) if raw_key else ""
        self.base_url = os.getenv("LENS_API_BASE_URL")
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.logger = logging.getLogger("APIClient")
        logging.basicConfig(level=logging.INFO)

    def fetch_product_info(self, identifier: str) -> Optional[Dict]:
        """정부 DB의 복잡한 계층 구조를 뚫고 실제 제품명과 도수를 가져옵니다."""
        if not identifier: return None
        
        gtin = identifier.zfill(14)
        endpoint = "getMdeqStdCdUnityInfoInq01"
        url = self.base_url.rstrip('/') + '/' + endpoint

        for param_name in ["gtin_code", "udi_code"]:
            params = {
                "serviceKey": self.api_key,
                "type": "json",
                "pageNo": "1",
                "numOfRows": "1",
                param_name: gtin
            }

            try:
                response = requests.get(url, params=params, timeout=15)
                if response.status_code == 200:
                    result = response.json()
                    body = result.get('body', {})
                    
                    # 공공데이터 특유의 구조: body -> items -> item (리스트 또는 단일 객체)
                    items_wrapper = body.get('items')
                    item_list = []
                    
                    if isinstance(items_wrapper, dict):
                        item_data = items_wrapper.get('item', [])
                        item_list = item_data if isinstance(item_data, list) else [item_data]
                    elif isinstance(items_wrapper, list):
                        item_list = items_wrapper

                    if item_list and len(item_list) > 0:
                        item = item_list[0]
                        
                        # 모든 가능한 필드명 대조 (대소문자 및 오타 대비)
                        model = item.get('MODEL_NM') or item.get('modelNm') or ""
                        prdlst = item.get('PRDLST_NM') or item.get('mdeqPrdlstNm') or item.get('MDEQ_PRDLST_NM') or ""
                        spec = item.get('SPEC_NM') or item.get('specNm') or "N/A"
                        entp = item.get('ENTP_NM') or item.get('entpNm') or "N/A"
                        
                        # 브랜드명이 있으면 브랜드명 우선, 없으면 품목명 사용
                        name = f"[{model}] {prdlst}".strip() if model and prdlst else (model or prdlst or "이름 없는 제품")
                        
                        self.logger.info(f"성공: {name} / {spec}")
                        
                        return {
                            'name': name,
                            'power': spec,
                            'manufacturer': entp,
                            'gtin': item.get('GTIN_CODE') or gtin
                        }
            except Exception as e:
                self.logger.error(f"접속 오류: {e}")
        
        return None

    def sync_with_local_db(self, api_data: Dict, local_data: Dict) -> Dict:
        synced = local_data.copy()
        if api_data:
            synced['name'] = api_data.get('name') or local_data.get('name')
            synced['power'] = api_data.get('power') or local_data.get('power')
        return synced
