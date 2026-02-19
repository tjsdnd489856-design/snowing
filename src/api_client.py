import os
import requests
import re
import urllib.parse
from typing import Dict, Optional, Any, List
from dotenv import load_dotenv

load_dotenv()

class APIClient:
    """MsUdedi 2단계 공정을 최우선으로 하되 모든 서랍을 뒤지는 정밀 진단 클라이언트"""

    def __init__(self):
        self.api_key = os.getenv("LENS_API_KEY", "").strip()
        self.base_url = "https://apis.data.go.kr/1471000"

    def _is_garbage(self, text: str) -> bool:
        if not text or len(text) < 2: return True
        garbage = ["null", "none", "nan", "평가되지", "undefined", "미등록", "미지정", "n/a"]
        return text.lower() in garbage

    def _clean_val(self, val: Any) -> str:
        if not val: return ""
        # 쉼표, 따옴표 등 모든 불순물 제거 후 순수 텍스트만 추출
        return str(val).strip().replace('"', '').replace('}', '').replace(',', '').replace(';', '')

    def _extract_info(self, content: str) -> Optional[Dict[str, str]]:
        """데이터 뭉치에서 제품명과 도수 추출"""
        fields = ["PRDT_NM", "PRDT_NM_CONT", "PRDT_ADD_EXPL", "MODEL_NM", "ITEM_NM"]
        for f in fields:
            match = re.search(rf'{f}["\>\]\s:]+([^"<\n]+)', content, re.IGNORECASE)
            if match:
                raw = self._clean_val(match.group(1))
                if not self._is_garbage(raw):
                    power_match = re.search(r'([+-]?\d+\.\d{2})', raw)
                    power = power_match.group(1) if power_match else "N/A"
                    name = raw.replace(power, "").strip("- ").strip()
                    if not self._is_garbage(name):
                        return {"name": name, "power": power, "field": f}
        return None

    def fetch_product_info(self, identifier: str) -> Optional[Dict]:
        if not identifier: return None
        target_id = identifier.zfill(14)
        print(f"\n--- 🛰️ [진단 시작] UDI 정밀 추적 ({target_id}) ---")

        # --- [STEP 1] MsUdediInfoService (목록 조회) ---
        print(f"\n📍 [체크포인트 1: 목록 조회 (getUdediList)]")
        list_url = f"{self.base_url}/MsUdediInfoService/getUdediList"
        # 목록 조회는 pageNo 필수
        list_full = f"{list_url}?serviceKey={self.api_key}&type=json&pageNo=1&numOfRows=1&UDIDI_CD={target_id}"
        
        udidi_from_list = None
        try:
            res = requests.get(list_full, timeout=7)
            if res.status_code == 200 and '"totalCount":0' not in res.text:
                match = re.search(r'UDIDI_CD["\>\]\s:]+([^"<\n]+)', res.text, re.IGNORECASE)
                if match:
                    udidi_from_list = self._clean_val(match.group(1))
                    print(f"  ✅ 성공: 식별자({udidi_from_list}) 확보 완료")
            else:
                print(f"  ❌ 결과: 목록에 정보가 없습니다.")
        except Exception as e:
            print(f"  ⚠️ 오류: 목록 조회 접속 실패 ({str(e)})")

        # --- [STEP 2] MsUdediInfoService (상세 조회) ---
        # 식별자를 찾았거나, 못 찾았더라도 원본 ID로 상세 조회 시도
        final_di = udidi_from_list if udidi_from_list else target_id
        print(f"\n📍 [체크포인트 2: 상세 정보 조회 (getUdediInfo)]")
        info_url = f"{self.base_url}/MsUdediInfoService/getUdediInfo"
        # 상세 조회는 pageNo 제외 (500 에러 방지)
        info_full = f"{info_url}?serviceKey={self.api_key}&type=json&UDIDI_CD={final_di}"
        
        try:
            res_i = requests.get(info_full, timeout=7)
            if res_i.status_code == 200 and '"totalCount":0' not in res_i.text:
                info = self._extract_info(res_i.text)
                if info:
                    print(f"  ✅ 성공: {info['name']} ({info['power']})")
                    return {'name': info['name'], 'power': info['power'], 'manufacturer': "식약처 정식 등록", 'gtin': final_di}
            print(f"  ❌ 결과: 상세 정보가 비어있습니다.")
        except Exception:
            print(f"  ⚠️ 오류: 상세 조회 접속 실패")

        # --- [STEP 3] MdeqStdCdUnityInfoService01 (최종 폴백) ---
        print(f"\n📍 [체크포인트 3: 통합정보망 최종 확인]")
        u_url = f"{self.base_url}/MdeqStdCdUnityInfoService01/getMdeqStdCdUnityInfoInq01"
        u_full = f"{u_url}?serviceKey={self.api_key}&type=json&pageNo=1&numOfRows=1&UDIDI_CD={target_id}"
        
        try:
            res_u = requests.get(u_full, timeout=7)
            if res_u.status_code == 200 and '"totalCount":0' not in res_u.text:
                info = self._extract_info(res_u.text)
                if info:
                    print(f"  ✅ 성공: {info['name']} ({info['power']})")
                    return {'name': info['name'], 'power': info['power'], 'manufacturer': "식약처 통합 등록", 'gtin': target_id}
        except Exception: pass

        print("\n❌ [최종 실패] 모든 경로에 유효한 데이터가 없습니다.")
        print(f"--- 🛰️ [진단 종료] ---\n")
        return None

    def sync_with_local_db(self, api_data: Dict, local_data: Dict) -> Dict:
        synced = local_data.copy()
        if api_data:
            synced['name'] = api_data.get('name') or local_data.get('name')
            synced['power'] = api_data.get('power') or local_data.get('power')
        return synced
