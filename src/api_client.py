import os
import requests
import re
import urllib.parse
from typing import Dict, Optional, Any
from dotenv import load_dotenv

load_dotenv()

class APIClient:
    """MsUdediInfoService를 이용한 2단계(목록->상세) 정밀 조회 클라이언트"""

    def __init__(self):
        self.api_key = os.getenv("LENS_API_KEY", "").strip()
        self.base_url = "https://apis.data.go.kr/1471000/MsUdediInfoService"

    def _clean_text(self, text: Any) -> str:
        if not text or str(text).lower() in ["null", "none", "nan", "평가되지"]:
            return ""
        return str(text).strip()

    def _extract_power(self, spec: str) -> str:
        """규격(SPEC) 텍스트에서 도수만 추출 (예: -7.00)"""
        if not spec: return "N/A"
        match = re.search(r'([+-]?\d+\.\d{2})', spec)
        return match.group(1) if match else spec

    def _step1_get_udidi_list(self, identifier: str) -> Optional[str]:
        """[1단계] getUdediList 호출하여 정확한 UDIDI_CD 확보"""
        url = f"{self.base_url}/getUdediList"
        target_id = identifier.zfill(14)
        
        params = {
            "serviceKey": self.api_key,
            "type": "json",
            "pageNo": "1",
            "numOfRows": "1",
            "UDIDI_CD": target_id
        }
        
        try:
            print(f"🔍 1단계: 목록 조회 중 (UDI-DI 확보)...")
            # 인증키 보호를 위해 URL 수동 조립
            full_url = f"{url}?serviceKey={self.api_key}&type=json&pageNo=1&numOfRows=1&UDIDI_CD={target_id}"
            response = requests.get(full_url, timeout=10)
            
            if response.status_code == 200:
                res_data = response.json()
                items = res_data.get('body', {}).get('items', [])
                if not items:
                    # 리스트 형태가 아닐 경우 대비
                    items = [res_data.get('body', {}).get('item')] if res_data.get('body', {}).get('item') else []
                
                if items and items[0]:
                    item = items[0]
                    # 목록에서 UDIDI_CD 추출
                    udidi = self._clean_text(item.get('UDIDI_CD'))
                    if udidi:
                        print(f"🎯 1단계 성공: 식별자 {udidi} 확보")
                        return udidi
        except Exception as e:
            print(f"❌ 1단계 오류: {e}")
        return None

    def _step2_get_udidi_info(self, udidi_cd: str) -> Optional[Dict]:
        """[2단계] getUdediInfo 호출하여 제품명 및 상세 스펙 확보"""
        url = f"{self.base_url}/getUdediInfo"
        
        try:
            print(f"📖 2단계: 상세정보 조회 중 (스펙 확인)...")
            full_url = f"{url}?serviceKey={self.api_key}&type=json&UDIDI_CD={udidi_cd}"
            response = requests.get(full_url, timeout=10)
            
            if response.status_code == 200:
                res_data = response.json()
                items = res_data.get('body', {}).get('items', [])
                if not items:
                    items = [res_data.get('body', {}).get('item')] if res_data.get('body', {}).get('item') else []
                
                if items and items[0]:
                    item = items[0]
                    # 제품명(PRDT_NM) 및 규격(SPEC/SPCLT) 추출
                    name = self._clean_text(item.get('PRDT_NM'))
                    spec = self._clean_text(item.get('SPEC') or item.get('SPCLT'))
                    
                    if name:
                        return {
                            'name': name,
                            'power': self._extract_power(spec),
                            'manufacturer': self._clean_text(item.get('ENTRPS_NM', '식약처 등록 업체')),
                            'gtin': udidi_cd
                        }
        except Exception as e:
            print(f"❌ 2단계 오류: {e}")
        return None

    def fetch_product_info(self, identifier: str) -> Optional[Dict]:
        """목록조회 -> 상세조회 연쇄 실행"""
        if not identifier: return None
        
        # 1. 목록 조회로 정확한 식별자 확보
        udidi_cd = self._step1_get_udidi_list(identifier)
        
        # 만약 목록에서 못 찾으면 바코드 번호를 직접 식별자로 간주하고 2단계 시도
        search_id = udidi_cd if udidi_cd else identifier.zfill(14)
        
        # 2. 상세 정보 조회
        result = self._step2_get_udidi_info(search_id)
        
        if result:
            print(f"✅ 최종 정보 획득: {result['name']} (도수: {result['power']})")
            return result
        
        print("📭 상세 정보를 찾을 수 없습니다.")
        return None

    def sync_with_local_db(self, api_data: Dict, local_data: Dict) -> Dict:
        synced = local_data.copy()
        if api_data:
            synced['name'] = api_data.get('name') or local_data.get('name')
            synced['power'] = api_data.get('power') or local_data.get('power')
        return synced
