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
    """중첩된 'ITEM' 구조를 완벽하게 파싱하는 클라이언트"""

    def __init__(self):
        raw_key = os.getenv("LENS_API_KEY")
        self.api_key = urllib.parse.unquote(raw_key) if raw_key else ""
        self.base_url = os.getenv("LENS_API_BASE_URL")
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.logger = logging.getLogger("APIClient")
        logging.basicConfig(level=logging.INFO)

    def fetch_product_info(self, identifier: str) -> Optional[Dict]:
        """정부 DB의 중첩된 상자(ITEM)를 열어 실제 데이터를 추출합니다."""
        if not identifier: return None
        
        gtin = identifier.zfill(14)
        endpoint = "getMdeqStdCdUnityInfoInq01"
        url = self.base_url.rstrip('/') + '/' + endpoint

        for param_name in ["gtin_code", "udi_code"]:
            params = {"serviceKey": self.api_key, "type": "json", "pageNo": "1", "numOfRows": "1", param_name: gtin}

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
                        # 1단계 아이템 꺼내기
                        target = item_list[0]
                        
                        # [핵심] 'ITEM' 또는 'item' 상자가 안에 또 들어있는 경우, 그 안으로 들어감
                        if isinstance(target, dict):
                            nested = target.get('ITEM') or target.get('item')
                            if nested:
                                target = nested

                        # 필드명을 대문자로 통일하여 알맹이 찾기
                        raw = {str(k).upper(): v for k, v in target.items()}
                        
                        # 제품명 후보군
                        model = raw.get('MODEL_NM') or raw.get('MODELNM') or ""
                        prdlst = raw.get('PRDLST_NM') or raw.get('MDEQ_PRDLST_NM') or ""
                        spec = raw.get('SPEC_NM') or raw.get('SPECNM') or "N/A"
                        entp = raw.get('ENTP_NM') or raw.get('ENTPNM') or "N/A"
                        
                        # 최종 이름 결정
                        name = ""
                        if model and prdlst: name = f"[{model}] {prdlst}"
                        elif model: name = model
                        elif prdlst: name = prdlst
                        else: name = "이름 정보 없음"

                        if name != "이름 정보 없음":
                            self.logger.info(f"알맹이 추출 성공: {name} ({spec})")
                            return {
                                'name': str(name).strip(),
                                'power': str(spec).strip(),
                                'manufacturer': str(entp).strip(),
                                'gtin': raw.get('GTIN_CODE') or gtin
                            }
                        else:
                            # 실패 시 내용물 분석을 위해 전체 출력
                            self.logger.warning(f"상자 안의 내용물: {list(raw.keys())}")
            except Exception as e:
                self.logger.error(f"접속 오류: {e}")
        
        return None

    def sync_with_local_db(self, api_data: Dict, local_data: Dict) -> Dict:
        synced = local_data.copy()
        if api_data:
            synced['name'] = api_data.get('name') or local_data.get('name')
            synced['power'] = api_data.get('power') or local_data.get('power')
        return synced
