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
    """식약처 API 응답의 모든 층을 검색하여 정보를 추출하는 최종 클라이언트"""

    def __init__(self):
        raw_key = os.getenv("LENS_API_KEY")
        self.api_key = urllib.parse.unquote(raw_key) if raw_key else ""
        self.base_url = os.getenv("LENS_API_BASE_URL")
        self.logger = logging.getLogger("APIClient")
        logging.basicConfig(level=logging.INFO)

    def fetch_product_info(self, identifier: str) -> Optional[Dict]:
        """주소 복구 및 모든 데이터 층을 통합 검색하여 이름/도수를 가져옵니다."""
        if not identifier: return None
        
        gtin = identifier.zfill(14)
        # 작동이 확인된 기본 엔드포인트로 복구
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
                    items_wrapper = body.get('items')
                    
                    item_list = []
                    if isinstance(items_wrapper, dict):
                        item_data = items_wrapper.get('item', [])
                        item_list = item_data if isinstance(item_data, list) else [item_data]
                    elif isinstance(items_wrapper, list):
                        item_list = items_wrapper

                    if item_list and len(item_list) > 0:
                        main_item = item_list[0]
                        
                        # [핵심] 모든 층의 데이터를 하나로 합침
                        # 바깥층(부모) 정보 + 안쪽층(ITEM) 정보를 통합
                        combined_data = {str(k).upper(): v for k, v in main_item.items()}
                        
                        nested = main_item.get('ITEM') or main_item.get('item')
                        if isinstance(nested, dict):
                            for k, v in nested.items():
                                combined_data[str(k).upper()] = v
                        elif isinstance(nested, list) and len(nested) > 0:
                            if isinstance(nested[0], dict):
                                for k, v in nested[0].items():
                                    combined_data[str(k).upper()] = v

                        # 제품명 후보군 검색
                        model = combined_data.get('MODEL_NM') or combined_data.get('MODELNM') or ""
                        prdlst = combined_data.get('PRDLST_NM') or combined_data.get('MDEQ_PRDLST_NM') or ""
                        spec = combined_data.get('SPEC_NM') or combined_data.get('SPECNM') or "N/A"
                        entp = combined_data.get('ENTP_NM') or combined_data.get('ENTPNM') or "N/A"
                        
                        name = ""
                        if model and prdlst: name = f"[{model}] {prdlst}"
                        elif model: name = model
                        elif prdlst: name = prdlst
                        else: name = "이름 정보 없음"

                        if name != "이름 정보 없음":
                            self.logger.info(f"정보 추출 성공: {name} / 도수: {spec}")
                            return {
                                'name': str(name).strip(),
                                'power': str(spec).strip(),
                                'manufacturer': str(entp).strip(),
                                'gtin': combined_data.get('GTIN_CODE') or gtin
                            }
                        else:
                            self.logger.warning(f"데이터 발견했으나 이름 필드 누락. 확인된 필드: {list(combined_data.keys())}")
                
            except Exception as e:
                self.logger.error(f"접속 시도 오류: {e}")
        
        return None

    def sync_with_local_db(self, api_data: Dict, local_data: Dict) -> Dict:
        synced = local_data.copy()
        if api_data:
            synced['name'] = api_data.get('name') or local_data.get('name')
            synced['power'] = api_data.get('power') or local_data.get('power')
        return synced
