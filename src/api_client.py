import os
import requests
import re
import urllib.parse
from typing import Dict, Optional, Any
from dotenv import load_dotenv

load_dotenv()

class APIClient:
    """JSON과 XML을 동시에 처리하며 가짜 데이터를 걸러내는 최종 클라이언트"""

    def __init__(self):
        self.api_key = os.getenv("LENS_API_KEY", "").strip()
        base = os.getenv("LENS_API_BASE_URL", "").split('/Mdeq')[0]
        self.service_url = f"{base}/MdeqStdCdUnityInfoService01"

    def _extract_from_raw(self, content: str) -> Optional[Dict[str, str]]:
        """텍스트 뭉치에서 제품명과 도수를 정규표현식으로 뽑아내고 가짜 데이터를 필터링합니다."""
        # 1. 상세 설명(PRDT_ADD_EXPL) 또는 모델명(MODEL_NM) 필드 찾기
        match = re.search(r'PRDT_ADD_EXPL["\>\]\s:]+([^"<\n]+)', content, re.IGNORECASE)
        model_match = re.search(r'MODEL_NM["\>\]\s:]+([^"<\n]+)', content, re.IGNORECASE)
        
        raw_text = None
        if match:
            raw_text = match.group(1).strip()
        elif model_match:
            raw_text = model_match.group(1).strip()
            
        # 가짜 데이터(null, none, 평가되지 않음 등) 필터링
        if not raw_text:
            return None
        
        clean_val = raw_text.lower().replace(",", "").replace(";", "").strip()
        if clean_val in ["null", "none", "평가되지 않음", "nan", "undefined", "null,"]:
            return None

        # 도수 추출 (-7.00, +1.50 등)
        power_match = re.search(r'([+-]?\d+\.\d{2})', raw_text)
        power = power_match.group(1) if power_match else "N/A"
        
        # 이름 정리
        name = raw_text.replace(power, "")
        name = re.sub(r'\(.*?\)', '', name).strip("- ").strip()
        
        # 이름이 너무 짧거나 여전히 null 계열이면 제외
        if len(name) < 2 or name.lower() in ["null", "none"]:
            return None

        return {"name": name, "power": power}

    def fetch_product_info(self, identifier: str) -> Optional[Dict]:
        """모든 서랍을 뒤져서 '진짜' 정보만 가져옵니다."""
        if not identifier: return None
        
        ids_to_try = [identifier.zfill(14), identifier[-13:]]
        if len(identifier) > 14:
            m = re.search(r'01(\d{14})', identifier)
            if m: ids_to_try.insert(0, m.group(1))
        
        endpoints = ["getMdeqStdCdUnityInfoInq01", "getMdeqStdCdInq01"]
        params = ["UDIDI_CD", "udi_code", "gtin_code"]

        for endpoint in endpoints:
            url = f"{self.service_url}/{endpoint}"
            for target_id in list(set(ids_to_try)):
                for p_name in params:
                    full_url = f"{url}?serviceKey={self.api_key}&type=json&pageNo=1&numOfRows=1&{p_name}={target_id}"
                    
                    try:
                        response = requests.get(full_url, timeout=10)
                        if response.status_code == 200:
                            content = response.text
                            if '"totalCount":0' in content or '<totalCount>0' in content:
                                continue

                            info = self._extract_from_raw(content)
                            if info and info["name"]:
                                print(f"✅ 발견: {info['name']} / {info['power']}")
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
