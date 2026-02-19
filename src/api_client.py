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
    """정부 API 데이터를 끝까지 추적하여 제품명을 찾아내는 최종 클라이언트"""

    def __init__(self):
        self.api_key = os.getenv("LENS_API_KEY")
        # 인증키 복호화 처리 (인코딩 문제 방지)
        self.api_key_unquoted = urllib.parse.unquote(self.api_key) if self.api_key else ""
        self.base_url = os.getenv("LENS_API_BASE_URL").rstrip('/')
        self.logger = logging.getLogger("APIClient")
        logging.basicConfig(level=logging.INFO)

    def _flatten_dict(self, d: Any, parent_key: str = '', sep: str = '_') -> Dict:
        """중첩된 모든 계층을 한 층으로 펼쳐서 검색을 쉽게 만듭니다."""
        items = {}
        if isinstance(d, dict):
            for k, v in d.items():
                new_key = f"{parent_key}{sep}{k}" if parent_key else k
                if isinstance(v, (dict, list)):
                    items.update(self._flatten_dict(v, new_key, sep=sep))
                else:
                    items[new_key.upper()] = v
        elif isinstance(d, list):
            for i, v in enumerate(d):
                new_key = f"{parent_key}{sep}{i}" if parent_key else str(i)
                if isinstance(v, (dict, list)):
                    items.update(self._flatten_dict(v, new_key, sep=sep))
                else:
                    items[new_key.upper()] = v
        return items

    def _find_value(self, flat_dict: Dict, keywords: list) -> Optional[Any]:
        """평면화된 데이터에서 키워드가 포함된 가장 적절한 값을 찾습니다."""
        for k, v in flat_dict.items():
            if any(kw.upper() in k for kw in keywords) and v:
                # 너무 짧거나 의미 없는 값 제외
                if len(str(v)) > 1: return v
        return None

    def fetch_product_info(self, identifier: str) -> Optional[Dict]:
        """모든 경로를 뚫고 제품명과 도수를 기어코 가져옵니다."""
        if not identifier: return None
        
        # 이전 로그에서 작동이 확인된 정확한 주소
        url = f"{self.base_url}/getMdeqStdCdUnityInfoInq01"
        
        # 검색어 후보군 (원본, 14자리, 13자리)
        search_values = [identifier, identifier.zfill(14), identifier[-13:]]
        search_values = list(dict.fromkeys(search_values)) # 중복 제거

        for val in search_values:
            for param in ["udi_code", "gtin_code", "udi_di"]:
                # 인증키 변형 방지를 위한 수동 URL 조립
                full_url = f"{url}?serviceKey={self.api_key_unquoted}&type=json&pageNo=1&numOfRows=1&{param}={val}"
                
                try:
                    self.logger.info(f"정부 DB 추적 중... ({param}={val})")
                    response = requests.get(full_url, timeout=12)
                    
                    if response.status_code == 200:
                        res_json = response.json()
                        # 데이터 전체 해체 (어디에 있든 찾아냄)
                        flat = self._flatten_dict(res_json)
                        
                        # 1. 제품명 찾기 (모델명 -> 제품명 -> 품목명 순)
                        name = (
                            self._find_value(flat, ["MODEL_NM", "MODELNM"]) or 
                            self._find_value(flat, ["PRDLST_NM", "PRDLSTNM"]) or 
                            self._find_value(flat, ["ITEM_NM", "ITEMNM"]) or
                            self._find_value(flat, ["MDEQ_PRDLST_NM"])
                        )
                        
                        # 2. 도수/규격 찾기
                        spec = self._find_value(flat, ["SPEC_NM", "SPECNM", "SPEC"]) or "N/A"
                        
                        if name:
                            # 브랜드명이 있으면 앞에 붙여서 가독성 향상
                            brand = self._find_value(flat, ["MODEL_NM", "MODELNM"])
                            full_name = f"[{brand}] {name}" if brand and brand != name else name
                            
                            self.logger.info(f"성공! 제품명: {full_name} / 도수: {spec}")
                            return {
                                'name': str(full_name).strip(),
                                'power': str(spec).strip(),
                                'manufacturer': self._find_value(flat, ["ENTP_NM", "ENTPNM"]) or "N/A",
                                'gtin': self._find_value(flat, ["GTIN_CODE"]) or val
                            }
                        elif len(flat) > 5:
                            self.logger.warning("데이터는 존재하나 이름 필드를 추출하지 못했습니다.")
                except Exception:
                    continue
        
        return None

    def sync_with_local_db(self, api_data: Dict, local_data: Dict) -> Dict:
        synced = local_data.copy()
        if api_data:
            synced['name'] = api_data.get('name') or local_data.get('name')
            synced['power'] = api_data.get('power') or local_data.get('power')
        return synced
