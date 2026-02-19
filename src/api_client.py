import os
import requests
import re
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Dict, Optional, Any
from dotenv import load_dotenv

load_dotenv()

class APIClient:
    """정부 API 응답을 한 글자 한 글자 분석하여 정보를 찾아내는 정밀 클라이언트"""

    def __init__(self):
        # 인증키를 변형 없이 그대로 사용합니다.
        self.api_key = os.getenv("LENS_API_KEY", "").strip()
        self.base_url = os.getenv("LENS_API_BASE_URL", "").rstrip('/')

    def _extract_from_text(self, text: str) -> Dict[str, str]:
        """텍스트에서 제품명과 도수를 추출 (예: PURSFIT 1DAY AIRCLEAR(10P) -7.00)"""
        # 도수 패턴 추출 (-7.00, +1.50 등)
        power_match = re.search(r'([+-]?\d+\.\d{2})', text)
        power = power_match.group(1) if power_match else "N/A"
        
        # 제품명 정리: 도수와 (10P) 같은 수량 정보 제거
        name = text.replace(power, "") if power != "N/A" else text
        name = re.sub(r'\(\d+P\)', '', name)
        name = name.strip("- ").strip()
        
        return {"name": name, "power": power}

    def fetch_product_info(self, identifier: str) -> Optional[Dict]:
        """서버 응답을 터미널에 직접 출력하며 정보를 추적합니다."""
        if not identifier: return None
        gtin = identifier.zfill(14)
        url = f"{self.base_url}/getMdeqStdCdUnityInfoInq01"
        
        # 세 가지 파라미터로 시도
        for param in ["udi_code", "gtin_code", "udi_di"]:
            # 공공데이터 API 전용: 인증키를 보호하기 위해 수동 URL 조립
            full_url = f"{url}?serviceKey={self.api_key}&type=json&pageNo=1&numOfRows=1&{param}={gtin}"
            
            try:
                print(f"\n[API 호출] {param}={gtin} 시도 중...")
                response = requests.get(full_url, timeout=10)
                
                if response.status_code == 200:
                    content = response.text.strip()
                    # 서버 응답 내용을 터미널에 즉시 출력 (디버깅용)
                    print(f"[서버 응답 원본 일부]: {content[:200]}...")

                    raw_info_text = None

                    # 1. XML에서 PRDT_ADD_EXPL 태그 직접 찾기
                    if '<PRDT_ADD_EXPL>' in content:
                        start = content.find('<PRDT_ADD_EXPL>') + len('<PRDT_ADD_EXPL>')
                        end = content.find('</PRDT_ADD_EXPL>')
                        raw_info_text = content[start:end]
                    
                    # 2. JSON에서 PRDT_ADD_EXPL 키 찾기
                    elif '"PRDT_ADD_EXPL"' in content:
                        match = re.search(r'"PRDT_ADD_EXPL"\s*:\s*"([^"]+)"', content)
                        if match:
                            raw_info_text = match.group(1)

                    if raw_info_text:
                        print(f"✅ 데이터 발견: {raw_info_text}")
                        info = self._extract_from_text(raw_info_text)
                        return {
                            'name': info['name'],
                            'power': info['power'],
                            'manufacturer': "정부 DB 등록 제품",
                            'gtin': gtin
                        }
                    else:
                        print("❌ 해당 파라미터에서는 제품 정보를 찾지 못했습니다.")
                else:
                    print(f"❌ 서버 에러: {response.status_code}")
            except Exception as e:
                print(f"❌ 연결 오류: {e}")
        
        return None

    def sync_with_local_db(self, api_data: Dict, local_data: Dict) -> Dict:
        synced = local_data.copy()
        if api_data:
            synced['name'] = api_data.get('name') or local_data.get('name')
            synced['power'] = api_data.get('power') or local_data.get('power')
        return synced
