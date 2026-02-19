import os
import requests
import re
import urllib.parse
import json
from typing import Dict, Optional, Any
from dotenv import load_dotenv

load_dotenv()

class APIClient:
    """JSON과 XML을 동시에 처리하여 렌즈 정보를 기어코 찾아내는 클라이언트"""

    def __init__(self):
        self.api_key = os.getenv("LENS_API_KEY", "").strip()
        # 기본 주소 정리
        base = os.getenv("LENS_API_BASE_URL", "").split('/Mdeq')[0]
        self.service_url = f"{base}/MdeqStdCdUnityInfoService01"

    def _extract_from_raw(self, content: str) -> Optional[Dict[str, str]]:
        """텍스트 뭉치에서 제품명과 도수를 정규표현식으로 뽑아냅니다."""
        # 1. 상세 설명(PRDT_ADD_EXPL) 필드 찾기
        # JSON용 패턴: "PRDT_ADD_EXPL":"내용"
        # XML용 패턴: <PRDT_ADD_EXPL>내용</PRDT_ADD_EXPL>
        match = re.search(r'PRDT_ADD_EXPL["\>\]\s:]+([^"<\n]+)', content, re.IGNORECASE)
        
        # 2. 모델명(MODEL_NM) 필드 찾기 (상세 설명이 없을 경우)
        model_match = re.search(r'MODEL_NM["\>\]\s:]+([^"<\n]+)', content, re.IGNORECASE)
        
        raw_text = None
        if match:
            raw_text = match.group(1).strip()
        elif model_match:
            raw_text = model_match.group(1).strip()
            
        if not raw_text or "NORMAL SERVICE" in raw_text:
            return None

        # 도수 추출 (-7.00, +1.50 등)
        power_match = re.search(r'([+-]?\d+\.\d{2})', raw_text)
        power = power_match.group(1) if power_match else "N/A"
        
        # 이름 정리
        name = raw_text.replace(power, "")
        name = re.sub(r'\(.*?\)', '', name).strip("- ").strip()
        
        return {"name": name, "power": power}

    def fetch_product_info(self, identifier: str) -> Optional[Dict]:
        """모든 서랍과 모든 형식을 뒤져서 정보를 가져옵니다."""
        if not identifier: return None
        
        # 바코드 번호 정리 (14자리, 13자리)
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
                    # 인증키 변형 방지를 위해 직접 조립
                    full_url = f"{url}?serviceKey={self.api_key}&type=json&pageNo=1&numOfRows=1&{p_name}={target_id}"
                    
                    try:
                        print(f"🔎 조회 중: {endpoint} ({target_id})")
                        response = requests.get(full_url, timeout=10)
                        if response.status_code == 200:
                            content = response.text
                            
                            # 데이터가 실제로 있는지 확인 (totalCount가 0이면 건너뜀)
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
                    except Exception as e:
                        print(f"❌ 오류: {e}")
        
        return None

    def sync_with_local_db(self, api_data: Dict, local_data: Dict) -> Dict:
        synced = local_data.copy()
        if api_data:
            synced['name'] = api_data.get('name') or local_data.get('name')
            synced['power'] = api_data.get('power') or local_data.get('power')
        return synced
