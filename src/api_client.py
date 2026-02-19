import os
import time
import requests
import logging
import urllib.parse
import re
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
from dotenv import load_dotenv

load_dotenv()

class APIClient:
    """정부 API의 모든 구석을 뒤져서 제품명을 찾아내는 무차별 추출 클라이언트"""

    def __init__(self):
        raw_key = os.getenv("LENS_API_KEY")
        self.api_key = urllib.parse.unquote(raw_key) if raw_key else ""
        self.base_url = os.getenv("LENS_API_BASE_URL").rstrip('/')
        self.logger = logging.getLogger("APIClient")
        logging.basicConfig(level=logging.INFO)

    def _deep_search(self, data: Any) -> Dict[str, str]:
        """JSON 데이터 전체를 훑어서 가장 이름/도수 같은 데이터를 뽑아냅니다."""
        found = {"name": "", "power": "", "all_texts": []}
        
        def walk(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    # 키 이름에 NM, NAME, MODEL, SPEC, PRD 등이 있으면 우선 순위
                    k_upper = str(k).upper()
                    if any(kw in k_upper for kw in ["NM", "NAME", "MODEL", "PRD"]):
                        if v and len(str(v)) > 1 and not found["name"]:
                            found["name"] = str(v)
                    if any(kw in k_upper for kw in ["SPEC", "SIZE", "VOL"]):
                        if v and not found["power"]:
                            found["power"] = str(v)
                    walk(v)
            elif isinstance(obj, list):
                for item in obj: walk(item)
            elif isinstance(obj, str):
                if len(obj) > 1: found["all_texts"].append(obj)

        walk(data)
        
        # 만약 전용 키로 못 찾았다면, 한글이 포함된 가장 긴 텍스트를 이름으로 추정
        if not found["name"] and found["all_texts"]:
            ko_texts = [t for t in found["all_texts"] if re.search("[가-힣]", t)]
            if ko_texts:
                found["name"] = max(ko_texts, key=len)
        
        return found

    def fetch_product_info(self, identifier: str) -> Optional[Dict]:
        """정부 서버가 주는 모든 텍스트를 분석하여 정보를 추출합니다."""
        if not identifier: return None
        
        # 모든 가능한 검색 번호 조합
        search_vals = [identifier.zfill(14), identifier[-13:], identifier]
        search_vals = list(dict.fromkeys(search_vals))
        
        # 시도할 주소 목록 (표준코드 조회 우선)
        endpoints = [
            f"{self.base_url}/getMdeqStdCdInq01",
            f"{self.base_url}/getMdeqStdCdUnityInfoInq01",
            self.base_url
        ]

        for url in endpoints:
            for val in search_vals:
                for param in ["gtin_code", "udi_code", "udi_di"]:
                    full_url = f"{url}?serviceKey={self.api_key}&type=json&pageNo=1&numOfRows=1&{param}={val}"
                    try:
                        response = requests.get(full_url, timeout=10)
                        if response.status_code == 200:
                            res_data = response.json()
                            
                            # 데이터가 비어있는지 확인
                            if "body" not in str(res_data).lower(): continue
                            
                            # 무차별 심층 검색 시작
                            result = self._deep_search(res_data)
                            
                            if result["name"]:
                                self.logger.info(f"데이터 추출 성공! 제품명: {result['name']}")
                                return {
                                    'name': result['name'].strip(),
                                    'power': result['power'].strip() or "N/A",
                                    'manufacturer': "정부 DB 등록 제품",
                                    'gtin': val
                                }
                            else:
                                # 데이터를 받았는데도 이름을 못 찾은 경우 원본 로그 출력
                                self.logger.warning(f"데이터는 받았으나 분석 실패. 응답 요약: {str(res_data)[:200]}...")
                    except Exception:
                        continue
        
        return None

    def sync_with_local_db(self, api_data: Dict, local_data: Dict) -> Dict:
        synced = local_data.copy()
        if api_data:
            synced['name'] = api_data.get('name') or local_data.get('name')
            synced['power'] = api_data.get('power') or local_data.get('power')
        return synced
