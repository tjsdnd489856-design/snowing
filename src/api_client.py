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
    """식약처 의료기기 표준코드 통합정보 API 정밀 클라이언트"""

    def __init__(self):
        raw_key = os.getenv("LENS_API_KEY")
        # 공공데이터포털 특유의 인증키 인코딩/복호화 이슈 해결
        self.api_key = urllib.parse.unquote(raw_key) if raw_key else ""
        self.base_url = os.getenv("LENS_API_BASE_URL")
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.logger = logging.getLogger("APIClient")
        logging.basicConfig(level=logging.INFO)

    def fetch_product_info(self, identifier: str) -> Optional[Dict]:
        """모든 검색 필드를 동원하여 제품명과 도수를 찾아냅니다."""
        if not identifier: return None
        
        # GTIN 표준인 14자리로 보정 (예: 880 -> 0880)
        gtin = identifier.zfill(14)
        
        # 검색할 파라미터 후보군 (정부 API의 다양한 검색 필드)
        search_candidates = ["gtin_code", "udi_code", "udi_di"]
        
        endpoint = "getMdeqStdCdUnityInfoInq01"
        url = self.base_url.rstrip('/') + '/' + endpoint

        for param_name in search_candidates:
            params = {
                "serviceKey": self.api_key,
                "type": "json",
                "pageNo": "1",
                "numOfRows": "1",
                param_name: gtin
            }

            try:
                # 타임아웃을 늘리고 명확하게 호출
                response = requests.get(url, params=params, timeout=15)
                
                if response.status_code == 200:
                    try:
                        result = response.json()
                        # 정부 API 특유의 복잡한 body.items.item 구조 파싱
                        body = result.get('body', {})
                        items = body.get('items', [])
                        
                        if items:
                            item = items[0] if isinstance(items, list) else items
                            
                            # 1. 이름 추출 (모델명 우선, 없으면 품목명)
                            brand_name = item.get('MODEL_NM') or ""
                            product_type = item.get('PRDLST_NM') or item.get('MDEQ_PRDLST_NM') or ""
                            full_name = f"[{brand_name}] {product_type}".strip() if brand_name else product_type
                            
                            # 2. 도수(Power) 추출 (규격 정보에서 추출)
                            spec = item.get('SPEC_NM') or "N/A"
                            
                            self.logger.info(f"데이터 발견! [{param_name}] 기반 검색 성공")
                            return {
                                'name': full_name or "이름 미등록 제품",
                                'power': spec,
                                'manufacturer': item.get('ENTP_NM', 'N/A'),
                                'gtin': item.get('GTIN_CODE') or identifier
                            }
                    except json.JSONDecodeError:
                        self.logger.error("정부 API가 JSON이 아닌 HTML(에러페이지)을 반환했습니다. 인증키를 확인하세요.")
                elif response.status_code == 401:
                    self.logger.error("인증 오류(401): API 키가 유효하지 않거나 승인 대기 중입니다.")
            except Exception as e:
                self.logger.error(f"접속 시도 중 오류 발생: {e}")
        
        self.logger.warning(f"정부 DB에서 {identifier}에 해당하는 정보를 찾을 수 없습니다.")
        return None

    def sync_with_local_db(self, api_data: Dict, local_data: Dict) -> Dict:
        synced = local_data.copy()
        if api_data:
            synced['name'] = api_data.get('name') or local_data.get('name')
            synced['power'] = api_data.get('power') or local_data.get('power')
            synced['gtin'] = api_data.get('gtin') or local_data.get('gtin')
            synced['source'] = 'api'
        return synced
