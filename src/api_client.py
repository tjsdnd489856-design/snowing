import os
import requests
import re
import urllib.parse
from typing import Dict, Optional, Any
from dotenv import load_dotenv

load_dotenv()

class APIClient:
    """식약처 UDI 데이터베이스 정밀 분석 클라이언트"""

    def __init__(self):
        self.api_key = os.getenv("LENS_API_KEY", "").strip()
        self.base_url = os.getenv("LENS_API_BASE_URL", "").rstrip('/')

    def _clean_text(self, text: str) -> Dict[str, str]:
        """텍스트에서 제품명과 도수를 분리 (예: PURSFIT 1DAY AIRCLEAR(10P) -7.00)"""
        # 1. 도수 추출 (예: -7.00)
        power_match = re.search(r'([+-]?\d+\.\d{2})', text)
        power = power_match.group(1) if power_match else "N/A"
        
        # 2. 제품명 추출 및 정리
        name = text.replace(power, "").replace("(10P)", "").replace("(30P)", "")
        name = re.sub(r'\(.*?\)', '', name) # 괄호 내용 제거
        name = name.strip("- ").strip()
        
        return {"name": name, "power": power}

    def fetch_product_info(self, identifier: str) -> Optional[Dict]:
        """UDIDI_CD 필드를 사용하여 정확한 제품 정보를 가져옵니다."""
        if not identifier: return None
        
        # 바코드에서 추출한 14자리 GTIN/UDI-DI
        target_udi = identifier.zfill(14)
        url = f"{self.base_url}/getMdeqStdCdUnityInfoInq01"
        
        # 정부 DB의 실제 필드명인 UDIDI_CD와 udi_code 등을 교차 시도
        for param_name in ["UDIDI_CD", "udidi_cd", "udi_code", "gtin_code"]:
            full_url = f"{url}?serviceKey={self.api_key}&type=json&pageNo=1&numOfRows=1&{param_name}={target_udi}"
            
            try:
                print(f"🔍 검색 시도 중: {param_name}={target_udi}")
                response = requests.get(full_url, timeout=10)
                
                if response.status_code == 200:
                    content = response.text
                    
                    # 검색 결과가 우리가 찾는 UDI와 일c치하는지 확인
                    if target_udi in content:
                        # PRDT_ADD_EXPL 필드에서 알맹이 추출 (JSON/XML 공통)
                        match = re.search(r'PRDT_ADD_EXPL[^\>]*\>([^<]+)\<', content) # XML 형태
                        if not match:
                            match = re.search(r'"PRDT_ADD_EXPL"\s*:\s*"([^"]+)"', content) # JSON 형태
                        
                        if match:
                            raw_text = match.group(1)
                            print(f"✅ 데이터 발견: {raw_text}")
                            info = self._clean_text(raw_text)
                            return {
                                'name': info['name'],
                                'power': info['power'],
                                'manufacturer': "정부 DB 등록 제품",
                                'gtin': target_udi
                            }
                
            except Exception as e:
                print(f"❌ 연결 오류: {e}")
        
        return None

    def sync_with_local_db(self, api_data: Dict, local_data: Dict) -> Dict:
        synced = local_data.copy()
        if api_data:
            synced['name'] = api_data.get('name') or local_data.get('name')
            synced['power'] = api_data.get('power') or local_data.get('power')
        return synced
