import os
import requests
import re
import urllib.parse
from typing import Dict, Optional, Any, List
from dotenv import load_dotenv

load_dotenv()

class APIClient:
    """1단계 식별자 확보 후 2단계 상세정보를 조회하는 정밀 체인 클라이언트"""

    def __init__(self):
        self.api_key = os.getenv("LENS_API_KEY", "").strip()
        self.base_url = "https://apis.data.go.kr/1471000"

    def _is_garbage(self, text: str) -> bool:
        if not text: return True
        garbage = ["null", "none", "평가되지", "undefined", "nan", "미등록"]
        return any(kw in text.lower() for kw in garbage)

    def _extract_info(self, text: str) -> Dict[str, str]:
        """상세설명 텍스트에서 제품명과 도수 분리"""
        power_match = re.search(r'([+-]?\d+\.\d{2})', text)
        power = power_match.group(1) if power_match else "N/A"
        name = text.replace(power, "")
        name = re.sub(r'\(.*?\)', '', name).strip("- ").strip()
        return {"name": name, "power": power}

    def _get_udidi_cd(self, identifier: str) -> Optional[str]:
        """[1단계] 표준코드 조회를 통해 고유 식별자(UDIDI_CD)를 확보합니다."""
        url = f"{self.base_url}/MdeqStdCdUnityInfoService01/getMdeqStdCdInq01"
        target_id = identifier.zfill(14)
        
        for param in ["gtin_code", "udi_code"]:
            full_url = f"{url}?serviceKey={self.api_key}&type=json&pageNo=1&numOfRows=1&{param}={target_id}"
            try:
                print(f"🔍 1단계: 표준코드 조회 중... ({param})")
                response = requests.get(full_url, timeout=7)
                if response.status_code == 200:
                    content = response.text
                    # UDIDI_CD 또는 UDIDI_CD 태그 내의 값 추출
                    match = re.search(r'UDIDI_CD["\>\]\s:]+([^"<\n]+)', content, re.IGNORECASE)
                    if match:
                        udidi = match.group(1).strip().replace('"', '').replace('}', '').replace(',', '')
                        if not self._is_garbage(udidi):
                            print(f"🎯 식별자 확보 성공: {udidi}")
                            return udidi
            except Exception: continue
        return None

    def _get_detailed_info(self, udidi_cd: str) -> Optional[Dict]:
        """[2단계] 확보된 UDIDI_CD로 상세정보(PRDT_ADD_EXPL)를 조회합니다."""
        # 시도할 상세정보 서비스 목록
        services = [
            {"s": "MdeqStdCdUnityInfoService01", "e": "getMdeqStdCdUnityInfoInq01"},
            {"s": "MsUdediInfoService", "e": "getUdediInfo"}
        ]
        
        for svc in services:
            url = f"{self.base_url}/{svc['s']}/{svc['e']}"
            full_url = f"{url}?serviceKey={self.api_key}&type=json&pageNo=1&numOfRows=1&UDIDI_CD={udidi_cd}"
            
            try:
                print(f"📖 2단계: 상세정보 조회 중... ({svc['e']})")
                response = requests.get(full_url, timeout=7)
                if response.status_code == 200:
                    content = response.text
                    # PRDT_ADD_EXPL 필드 집중 검색
                    match = re.search(r'PRDT_ADD_EXPL["\>\]\s:]+([^"<\n]+)', content, re.IGNORECASE)
                    if match:
                        raw_text = match.group(1).strip().replace('"', '').replace('}', '')
                        if not self._is_garbage(raw_text):
                            info = self._extract_info(raw_text)
                            return {
                                'name': info['name'],
                                'power': info['power'],
                                'manufacturer': "식약처 등록 제품",
                                'gtin': udidi_cd
                            }
            except Exception: continue
        return None

    def fetch_product_info(self, identifier: str) -> Optional[Dict]:
        """식별자 확보 -> 상세조회 순서로 실행합니다."""
        if not identifier: return None
        
        # 1. 고유 식별자(DI) 먼저 찾기
        udidi_cd = self._get_udidi_cd(identifier)
        
        if udidi_cd:
            # 2. 식별자로 상세 내용 가져오기
            result = self._get_detailed_info(udidi_cd)
            if result:
                print(f"✅ 최종 정보 획득: {result['name']} / {result['power']}")
                return result
        
        print("📭 상세 정보를 찾을 수 없어 수동 입력이 필요합니다.")
        return None

    def sync_with_local_db(self, api_data: Dict, local_data: Dict) -> Dict:
        synced = local_data.copy()
        if api_data:
            synced['name'] = api_data.get('name') or local_data.get('name')
            synced['power'] = api_data.get('power') or local_data.get('power')
        return synced
