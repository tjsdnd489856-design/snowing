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
    """식약처 의료기기 표준코드 정보(제품명/도수) 전용 클라이언트"""

    def __init__(self):
        raw_key = os.getenv("LENS_API_KEY")
        self.api_key = urllib.parse.unquote(raw_key) if raw_key else ""
        self.base_url = os.getenv("LENS_API_BASE_URL")
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.logger = logging.getLogger("APIClient")
        logging.basicConfig(level=logging.INFO)

    def fetch_product_info(self, identifier: str) -> Optional[Dict]:
        """정부 DB의 '표준코드 정보 조회' 기능을 사용하여 이름과 도수를 가져옵니다."""
        if not identifier: return None
        
        # 14자리 GTIN 규격으로 보정
        gtin = identifier.zfill(14)
        
        # [중요] 제품명과 규격이 들어있는 정확한 기능명으로 변경
        endpoint = "getMdeqStdCdInq01" 
        # 베이스 URL 주소 정리
        base = self.base_url.split('/MdeqStdCdUnityInfoService01')[0]
        url = f"{base}/MdeqStdCdUnityInfoService01/{endpoint}"

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
                        target = item_list[0]
                        # ITEM 상자 안에 정보가 한 번 더 포장되어 있을 경우를 위해
                        if isinstance(target, dict) and (target.get('ITEM') or target.get('item')):
                            target = target.get('ITEM') or target.get('item')

                        # 모든 키를 대문자로 변환하여 분석
                        raw = {str(k).upper(): v for k, v in target.items()}
                        
                        # [확인된 필드 매핑]
                        # MODEL_NM: 모델명(브랜드명), PRDLST_NM: 품목명, SPEC_NM: 상세규격(도수)
                        model = raw.get('MODEL_NM') or raw.get('MODELNM') or ""
                        prdlst = raw.get('PRDLST_NM') or raw.get('MDEQ_PRDLST_NM') or ""
                        spec = raw.get('SPEC_NM') or raw.get('SPECNM') or "N/A"
                        entp = raw.get('ENTP_NM') or raw.get('ENTPNM') or "N/A"
                        
                        # 이름 결정: [모델명] 품목명 형태
                        name = ""
                        if model and prdlst: name = f"[{model}] {prdlst}"
                        elif model: name = model
                        elif prdlst: name = prdlst
                        else: name = "이름 정보 없음"

                        if name != "이름 정보 없음":
                            self.logger.info(f"성공: {name} / 도수: {spec}")
                            return {
                                'name': str(name).strip(),
                                'power': str(spec).strip(),
                                'manufacturer': str(entp).strip(),
                                'gtin': raw.get('GTIN_CODE') or gtin
                            }
                        else:
                            self.logger.warning(f"데이터는 찾았으나 제품명 필드가 비어있음. 필드목록: {list(raw.keys())}")
                else:
                    self.logger.error(f"API 오류 코드: {response.status_code}")
            except Exception as e:
                self.logger.error(f"접속 중 예외 발생: {e}")
        
        return None

    def sync_with_local_db(self, api_data: Dict, local_data: Dict) -> Dict:
        synced = local_data.copy()
        if api_data:
            synced['name'] = api_data.get('name') or local_data.get('name')
            synced['power'] = api_data.get('power') or local_data.get('power')
        return synced
