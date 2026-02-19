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
    """모든 필드명을 자동 검색하는 초정밀 API 클라이언트"""

    def __init__(self):
        raw_key = os.getenv("LENS_API_KEY")
        self.api_key = urllib.parse.unquote(raw_key) if raw_key else ""
        self.base_url = os.getenv("LENS_API_BASE_URL")
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.logger = logging.getLogger("APIClient")
        logging.basicConfig(level=logging.INFO)

    def fetch_product_info(self, identifier: str) -> Optional[Dict]:
        """정부 응답의 모든 필드를 뒤져서 이름과 도수를 찾아냅니다."""
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
                        item = item_list[0]
                        
                        # 모든 필드명을 대문자로 통일하여 검색 (변종 대응)
                        raw = {str(k).upper(): v for k, v in item.items()}
                        
                        # 1. 제품명 찾기 (가능한 모든 후보군)
                        model = raw.get('MODEL_NM') or raw.get('MODELNM') or raw.get('ITEM_NM') or raw.get('PRD_NM') or ""
                        prdlst = raw.get('PRDLST_NM') or raw.get('MDEQ_PRDLST_NM') or raw.get('MDEQPRDLSTNM') or ""
                        entp = raw.get('ENTP_NM') or raw.get('ENTPNM') or ""
                        
                        # 2. 도수/규격 찾기
                        spec = raw.get('SPEC_NM') or raw.get('SPECNM') or raw.get('SPEC') or "N/A"
                        
                        # 이름 조립
                        name = ""
                        if model and prdlst: name = f"[{model}] {prdlst}"
                        elif model: name = model
                        elif prdlst: name = prdlst
                        else: name = "이름 정보 없음"

                        self.logger.info(f"데이터 추출 성공: {name} ({spec})")
                        
                        # 만약 여전히 이름이 없으면 필드 목록을 출력하여 디버깅 도움
                        if name == "이름 정보 없음":
                            self.logger.warning(f"사용 가능한 필드들: {list(raw.keys())}")

                        return {
                            'name': str(name).strip(),
                            'power': str(spec).strip(),
                            'manufacturer': str(entp).strip(),
                            'gtin': raw.get('GTIN_CODE') or gtin
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
