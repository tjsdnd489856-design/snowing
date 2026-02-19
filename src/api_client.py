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
    """식약처 표준코드 DB에서 제품명과 도수를 반드시 찾아내는 클라이언트"""

    def __init__(self):
        raw_key = os.getenv("LENS_API_KEY")
        # 공공데이터포털 인증키는 복호화된 상태로 사용해야 오류가 없습니다.
        self.api_key = urllib.parse.unquote(raw_key) if raw_key else ""
        self.base_url = os.getenv("LENS_API_BASE_URL")
        self.logger = logging.getLogger("APIClient")
        logging.basicConfig(level=logging.INFO)

    def fetch_product_info(self, identifier: str) -> Optional[Dict]:
        """정부 DB의 '표준코드 기본정보' 서랍을 열어 제품명과 도수를 가져옵니다."""
        if not identifier: return None
        
        # 14자리 GTIN 규격 보정
        gtin = identifier.zfill(14)
        
        # [핵심] 404 에러 방지를 위해 사용자님이 주신 주소에 기능을 직접 연결
        # 기본주소: https://apis.data.go.kr/1471000/MdeqStdCdUnityInfoService01
        # 기능명: getMdeqStdCdInq01 (이것이 제품명/도수가 있는 진짜 서랍입니다)
        url = self.base_url.rstrip('/') + '/getMdeqStdCdInq01'

        # GTIN_CODE와 UDI_CODE 두 가지 파라미터로 모두 찔러봅니다.
        for param_name in ["gtin_code", "udi_code"]:
            params = {
                "serviceKey": self.api_key,
                "type": "json",
                "pageNo": "1",
                "numOfRows": "1",
                param_name: gtin
            }

            try:
                # 공공데이터 API는 HTTPS 보안 인증에 민감할 수 있어 timeout을 넉넉히 잡습니다.
                response = requests.get(url, params=params, timeout=15)
                
                if response.status_code == 200:
                    try:
                        result = response.json()
                        body = result.get('body', {})
                        items_wrapper = body.get('items', {})
                        
                        # 아이템 추출 (리스트 또는 단일 객체 대응)
                        item_list = []
                        if isinstance(items_wrapper, dict):
                            item_data = items_wrapper.get('item', [])
                            item_list = item_data if isinstance(item_data, list) else [item_data]
                        elif isinstance(items_wrapper, list):
                            item_list = items_wrapper

                        if item_list and len(item_list) > 0:
                            data = item_list[0]
                            # 대소문자 구분 없이 모든 키를 뒤집니다.
                            raw = {str(k).upper(): v for k, v in data.items()}
                            
                            # [우리가 찾는 진짜 정보]
                            # MODEL_NM: 제품 브랜드명 (예: 클라렌)
                            # PRDLST_NM: 품목명 (예: 소프트콘택트렌즈)
                            # SPEC_NM: 도수/곡률 (예: -3.00)
                            model = raw.get('MODEL_NM') or raw.get('ITEM_NM') or ""
                            prdlst = raw.get('PRDLST_NM') or raw.get('MDEQ_PRDLST_NM') or ""
                            spec = raw.get('SPEC_NM') or "N/A"
                            
                            name = f"[{model}] {prdlst}".strip() if model and prdlst else (model or prdlst)
                            
                            if name:
                                self.logger.info(f"성공! 제품명: {name} / 도수: {spec}")
                                return {
                                    'name': str(name),
                                    'power': str(spec),
                                    'manufacturer': str(raw.get('ENTP_NM', 'N/A')),
                                    'gtin': gtin
                                }
                            else:
                                # 찾았는데 이름이 없는 경우, 전체 데이터를 찍어서 분석합니다.
                                self.logger.warning(f"데이터를 찾았으나 이름 필드가 없습니다: {json.dumps(raw, ensure_ascii=False)}")
                    except Exception as e:
                        self.logger.error(f"응답 해석 중 오류: {e}")
                elif response.status_code == 404:
                    self.logger.error(f"404 에러: 주소({url})를 서버가 찾을 수 없습니다.")
                else:
                    self.logger.error(f"서버 응답 에러: {response.status_code}")
                    
            except Exception as e:
                self.logger.error(f"연결 오류: {e}")
        
        return None

    def sync_with_local_db(self, api_data: Dict, local_data: Dict) -> Dict:
        synced = local_data.copy()
        if api_data:
            synced['name'] = api_data.get('name') or local_data.get('name')
            synced['power'] = api_data.get('power') or local_data.get('power')
        return synced
