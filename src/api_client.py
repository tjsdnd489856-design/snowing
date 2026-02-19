import os
import requests
import re
import urllib.parse
from typing import Dict, Optional, Any
from dotenv import load_dotenv

load_dotenv()

class APIClient:
    """정부 DB의 가짜 데이터를 걸러내고 실제 정보만 추출하는 정밀 클라이언트"""

    def __init__(self):
        self.api_key = os.getenv("LENS_API_KEY", "").strip()
        base = os.getenv("LENS_API_BASE_URL", "").split('/Mdeq')[0]
        self.service_url = f"{base}/MdeqStdCdUnityInfoService01"

    def _is_garbage_name(self, name: str) -> bool:
        """추출된 이름이 null, none 등 가짜 데이터인지 확인합니다."""
        if not name: return True
        
        # 1. 길이 검사 (최소 2자 이상)
        clean_name = name.strip()
        if len(clean_name) < 2: return True
        
        # 2. 금지 단어 목록 (대소문자 무관)
        garbage_keywords = ["null", "none", "평가되지", "undefined", "nan", "n/a", "미지정", "미등록"]
        lower_name = clean_name.lower()
        
        for kw in garbage_keywords:
            if kw in lower_name:
                return True
        
        # 3. 유의미한 문자(한글/영문/숫자) 포함 여부 확인
        if not re.search(r'[a-zA-Z가-힣0-9]', clean_name):
            return True
            
        return False

    def _extract_from_raw(self, content: str) -> Optional[Dict[str, str]]:
        """텍스트에서 정보를 뽑아내고 유효성을 검사합니다."""
        # 상세설명 또는 모델명 필드 추출
        match = re.search(r'PRDT_ADD_EXPL["\>\]\s:]+([^"<\n]+)', content, re.IGNORECASE)
        model_match = re.search(r'MODEL_NM["\>\]\s:]+([^"<\n]+)', content, re.IGNORECASE)
        
        raw_text = (match.group(1) if match else (model_match.group(1) if model_match else "")).strip()
        
        if not raw_text or self._is_garbage_name(raw_text):
            return None

        # 도수 추출
        power_match = re.search(r'([+-]?\d+\.\d{2})', raw_text)
        power = power_match.group(1) if power_match else "N/A"
        
        # 이름 정리
        name = raw_text.replace(power, "")
        name = re.sub(r'\(.*?\)', '', name).strip("- ").strip()
        
        if self._is_garbage_name(name):
            return None

        return {"name": name, "power": power}

    def fetch_product_info(self, identifier: str) -> Optional[Dict]:
        """모든 서랍을 뒤져서 '진짜' 정보가 나올 때만 반환합니다."""
        if not identifier: return None
        
        target_ids = [identifier.zfill(14), identifier[-13:]]
        if len(identifier) > 14:
            m = re.search(r'01(\d{14})', identifier)
            if m: target_ids.insert(0, m.group(1))
        
        endpoints = ["getMdeqStdCdUnityInfoInq01", "getMdeqStdCdInq01"]
        params = ["UDIDI_CD", "udi_code", "gtin_code"]

        for endpoint in endpoints:
            url = f"{self.service_url}/{endpoint}"
            for target_id in list(set(target_ids)):
                for p_name in params:
                    full_url = f"{url}?serviceKey={self.api_key}&type=json&pageNo=1&numOfRows=1&{p_name}={target_id}"
                    try:
                        response = requests.get(full_url, timeout=10)
                        if response.status_code == 200:
                            content = response.text
                            # 0개 결과 명시적 처리
                            if '"totalCount":0' in content or '<totalCount>0' in content:
                                continue

                            info = self._extract_from_raw(content)
                            if info:
                                print(f"✅ 유효한 데이터 발견: {info['name']} / {info['power']}")
                                return {
                                    'name': info['name'],
                                    'power': info['power'],
                                    'manufacturer': "정부 DB 등록 제품",
                                    'gtin': target_id
                                }
                    except Exception:
                        continue
        return None

    def sync_with_local_db(self, api_data: Dict, local_data: Dict) -> Dict:
        synced = local_data.copy()
        if api_data:
            synced['name'] = api_data.get('name') or local_data.get('name')
            synced['power'] = api_data.get('power') or local_data.get('power')
        return synced
