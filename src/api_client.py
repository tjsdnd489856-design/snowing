import os
import time
import requests
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
from dotenv import load_dotenv

load_dotenv()

class APIClient:
    """공공데이터포털 전용 수동 URL 조립 클라이언트"""

    def __init__(self):
        self.api_key = os.getenv("LENS_API_KEY")
        self.base_url = os.getenv("LENS_API_BASE_URL").rstrip('/')
        self.logger = logging.getLogger("APIClient")
        logging.basicConfig(level=logging.INFO)

    def fetch_product_info(self, identifier: str) -> Optional[Dict]:
        """인증키 변형을 막기 위해 URL을 수동으로 조립하여 호출합니다."""
        if not identifier or not self.api_key:
            self.logger.error("API 키 또는 식별자가 없습니다.")
            return None
        
        # 13자리와 14자리 두 가지 버전을 준비
        gtin_14 = identifier.zfill(14)
        gtin_13 = identifier[-13:] if len(identifier) >= 13 else identifier

        # 시도할 엔드포인트와 파라미터 조합
        endpoints = [
            f"{self.base_url}/getMdeqStdCdInq01",
            f"{self.base_url}/getMdeqStdCdUnityInfoInq01",
            self.base_url
        ]
        
        for url in endpoints:
            for gtin_val in [gtin_14, gtin_13]:
                for param_name in ["gtin_code", "udi_code"]:
                    # [핵심] requests의 params를 쓰지 않고 URL을 직접 조립 (인증키 변형 방지)
                    full_url = (
                        f"{url}?serviceKey={self.api_key}"
                        f"&type=json&pageNo=1&numOfRows=1"
                        f"&{param_name}={gtin_val}"
                    )
                    
                    try:
                        self.logger.info(f"요청 시도: {url.split('/')[-1]} ({param_name}={gtin_val})")
                        response = requests.get(full_url, timeout=10)
                        
                        if response.status_code == 200:
                            # 응답 내용 확인
                            try:
                                result = response.json()
                                header = result.get('header', {})
                                if header.get('resultCode') != '00':
                                    self.logger.warning(f"서버 응답 결과 코드 오류: {header.get('resultMsg')}")
                                    continue

                                body = result.get('body', {})
                                items_wrapper = body.get('items')
                                item_list = []
                                
                                if isinstance(items_wrapper, dict):
                                    item_data = items_wrapper.get('item', [])
                                    item_list = item_data if isinstance(item_data, list) else [item_data]
                                elif isinstance(items_wrapper, list):
                                    item_list = items_wrapper

                                if item_list and len(item_list) > 0:
                                    # 모든 계층의 데이터를 통합하여 추출
                                    target = item_list[0]
                                    raw = {str(k).upper(): v for k, v in target.items()}
                                    
                                    # ITEM 내부 중첩 확인
                                    nested = target.get('ITEM') or target.get('item')
                                    if isinstance(nested, dict):
                                        for nk, nv in nested.items(): raw[str(nk).upper()] = nv

                                    model = raw.get('MODEL_NM') or raw.get('MODELNM') or ""
                                    prdlst = raw.get('PRDLST_NM') or raw.get('MDEQ_PRDLST_NM') or ""
                                    spec = raw.get('SPEC_NM') or raw.get('SPECNM') or "N/A"
                                    
                                    name = f"[{model}] {prdlst}".strip() if model and prdlst else (model or prdlst)
                                    
                                    if name:
                                        self.logger.info(f"성공! 제품명: {name}")
                                        return {
                                            'name': str(name),
                                            'power': str(spec),
                                            'manufacturer': str(raw.get('ENTP_NM', 'N/A')),
                                            'gtin': gtin_val
                                        }
                            except Exception as e:
                                self.logger.error(f"데이터 파싱 중 오류: {e}")
                        elif response.status_code == 401:
                            self.logger.error("401 인증 오류: API 키가 잘못되었거나 아직 활성화되지 않았습니다.")
                            return None # 인증 오류는 더 시도하지 않음
                        elif response.status_code != 404:
                            self.logger.warning(f"서버 응답 오류 ({response.status_code})")
                            
                    except Exception as e:
                        self.logger.error(f"연결 오류: {e}")
                        continue
        
        return None

    def sync_with_local_db(self, api_data: Dict, local_data: Dict) -> Dict:
        synced = local_data.copy()
        if api_data:
            synced['name'] = api_data.get('name') or local_data.get('name')
            synced['power'] = api_data.get('power') or local_data.get('power')
        return synced
