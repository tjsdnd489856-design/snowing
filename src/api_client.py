import os
import requests
import re
import urllib.parse
from typing import Dict, Optional, Any
from dotenv import load_dotenv

load_dotenv()

class APIClient:
    """정부 DB의 모든 서랍을 뒤져서 렌즈 정보를 찾아내는 클라이언트"""

    def __init__(self):
        self.api_key = os.getenv("LENS_API_KEY", "").strip()
        # 기본 주소에서 서비스 명칭까지만 추출
        base = os.getenv("LENS_API_BASE_URL", "").split('/Mdeq')[0]
        self.service_url = f"{base}/MdeqStdCdUnityInfoService01"

    def _clean_text(self, text: str) -> Dict[str, str]:
        """텍스트에서 제품명과 도수를 분리"""
        power_match = re.search(r'([+-]?\d+\.\d{2})', text)
        power = power_match.group(1) if power_match else "N/A"
        name = text.replace(power, "")
        name = re.sub(r'\(.*?\)', '', name).strip("- ").strip()
        return {"name": name, "power": power}

    def fetch_product_info(self, identifier: str) -> Optional[Dict]:
        """결과가 0개라도 다른 엔드포인트를 순환하며 끝까지 찾습니다."""
        if not identifier: return None
        
        # 14자리 GTIN 추출 (바코드의 핵심 식별 번호)
        target_id = identifier.zfill(14)
        if len(identifier) > 14: # GS1-128인 경우 앞의 01 뒤 14자리 추출
            match = re.search(r'01(\d{14})', identifier)
            if match: target_id = match.group(1)

        # 뒤져볼 서랍(엔드포인트) 목록
        endpoints = ["getMdeqStdCdUnityInfoInq01", "getMdeqStdCdInq01"]
        # 시도할 파라미터 목록
        params_to_try = ["UDIDI_CD", "udi_code", "gtin_code"]

        for endpoint in endpoints:
            url = f"{self.service_url}/{endpoint}"
            for p_name in params_to_try:
                full_url = f"{url}?serviceKey={self.api_key}&type=json&pageNo=1&numOfRows=1&{p_name}={target_id}"
                
                try:
                    print(f"🔎 {endpoint} 서랍 뒤지는 중... ({target_id})")
                    response = requests.get(full_url, timeout=10)
                    if response.status_code == 200:
                        content = response.text
                        
                        # 결과가 있는지 확인 (totalCount가 0이 아니어야 함)
                        count_match = re.search(r'<totalCount>([^<]+)</totalCount>', content)
                        if count_match and count_match.group(1) == '0':
                            continue # 다음 파라미터나 서랍으로 이동

                        # 정보 추출 (PRDT_ADD_EXPL 또는 MODEL_NM)
                        res_text = None
                        # 1순위: 상세 설명 필드
                        match = re.search(r'PRDT_ADD_EXPL[^\>]*\>([^<]+)\<', content)
                        if match:
                            res_text = match.group(1)
                            info = self._clean_text(res_text)
                            print(f"✅ 상세 정보 발견: {res_text}")
                            return {
                                'name': info['name'],
                                'power': info['power'],
                                'manufacturer': "정부 DB 등록 제품",
                                'gtin': target_id
                            }
                        
                        # 2순위: 모델명 필드
                        model_match = re.search(r'MODEL_NM[^\>]*\>([^<]+)\<', content)
                        if model_match:
                            model_nm = model_match.group(1)
                            print(f"✅ 모델명 발견: {model_nm}")
                            return {
                                'name': model_nm,
                                'power': "N/A",
                                'manufacturer': "정부 DB 등록 제품",
                                'gtin': target_id
                            }
                
                except Exception as e:
                    print(f"❌ 접속 오류: {e}")
        
        print("📭 모든 서랍을 뒤졌으나 정보를 찾지 못했습니다.")
        return None

    def sync_with_local_db(self, api_data: Dict, local_data: Dict) -> Dict:
        synced = local_data.copy()
        if api_data:
            synced['name'] = api_data.get('name') or local_data.get('name')
            synced['power'] = api_data.get('power') or local_data.get('power')
        return synced
