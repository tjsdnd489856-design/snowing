import os
import requests
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Optional, Any, List
from dotenv import load_dotenv

load_dotenv()

class APIClient:
    """1단계 식별자 확보 후 2단계 상세조회를 수행하는 정밀 하이브리드 클라이언트"""

    def __init__(self):
        self.api_key = os.getenv("LENS_API_KEY", "").strip()
        self.base_url = "https://apis.data.go.kr/1471000"

    def _clean_val(self, val: Any) -> str:
        if not val or str(val).lower() in ["null", "none", "nan", "평가되지", "평가되지 않음"]:
            return ""
        return str(val).strip().replace('"', '').replace('}', '').replace(',', '').replace(';', '')

    def _extract_info(self, content: str) -> Optional[Dict[str, str]]:
        """데이터 뭉치에서 제품명과 도수 정밀 추출"""
        fields = ["PRDT_NM", "PRDT_ADD_EXPL", "MODEL_NM", "ITEM_NM", "PRDLST_NM"]
        for f in fields:
            # 필드명 뒤의 값을 캡처하는 정규표현식
            match = re.search(rf'{f}["\>\]\s:]+([^"<\n]+)', content, re.IGNORECASE)
            if match:
                raw = self._clean_val(match.group(1))
                if len(raw) >= 2:
                    # 도수 추출 (-7.00, +1.50 등)
                    p_match = re.search(r'([+-]?\d+\.\d{2})', raw)
                    power = p_match.group(1) if p_match else "N/A"
                    name = raw.replace(power, "").strip("- ").strip()
                    if len(name) >= 2:
                        return {"name": name, "power": power, "field": f}
        return None

    def _try_request(self, service: str, endpoint: str, param: str, val: str, use_page: bool = False) -> Optional[str]:
        """API 호출 및 진행 상황 출력"""
        url = f"{self.base_url}/{service}/{endpoint}"
        page_param = "&pageNo=1&numOfRows=1" if use_page else ""
        full_url = f"{url}?serviceKey={self.api_key}&type=json{page_param}&{param}={val}"
        
        try:
            response = requests.get(full_url, timeout=6)
            if response.status_code == 200:
                if '"totalCount":0' in response.text or '<totalCount>0' in response.text:
                    return None
                return response.text
        except Exception: pass
        return None

    def fetch_product_info(self, identifier: str) -> Optional[Dict]:
        if not identifier: return None
        target_id = identifier.zfill(14)
        print(f"\n--- 🛰️ [정밀 공정 시작] UDI-DI 기반 추적 ({target_id}) ---")

        # [1단계] 목록 조회 (getUdediList) - 식별자 확보
        print(f"➡️ 1단계: 목록 조회 중 (UDI-DI 확보)...")
        list_content = self._try_request("MsUdediInfoService", "getUdediList", "UDIDI_CD", target_id, use_page=True)
        
        udidi_cd = None
        if list_content:
            match = re.search(r'UDIDI_CD["\>\]\s:]+([^"<\n]+)', list_content, re.IGNORECASE)
            if match:
                udidi_cd = self._clean_val(match.group(1))
                print(f"  🎯 식별자 확보 성공: {udidi_cd}")

        # [2단계] 상세 조회 (getUdediInfo) - 알맹이 추출
        # 1단계에서 찾은 코드가 있으면 그것을 쓰고, 없으면 바코드를 직접 씁니다.
        final_di = udidi_cd if udidi_cd else target_id
        print(f"➡️ 2단계: 상세 정보 조회 중 (알맹이 추출)...")
        
        # 상세 조회는 여러 파라미터 명칭을 병렬로 시도 (500 에러 방지 및 성공률 극대화)
        detail_tasks = [
            ("MsUdediInfoService", "getUdediInfo", "UDIDI_CD"),
            ("MsUdediInfoService", "getUdediInfo", "udi"),
            ("MdeqStdCdUnityInfoService01", "getMdeqStdCdUnityInfoInq01", "UDIDI_CD"),
            ("MdeqStdCdUnityInfoService01", "getMdeqStdCdUnityInfoInq01", "udi_code")
        ]

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(self._try_request, *task, final_di) for task in detail_tasks]
            for future in as_completed(futures):
                content = future.result()
                if content:
                    info = self._extract_info(content)
                    if info:
                        print(f"✅ 최종 정보 획득: {info['name']} / {info['power']}")
                        print(f"--- 🛰️ 공정 종료 ---\n")
                        return {'name': info['name'], 'power': info['power'], 'manufacturer': "식약처 등록 제품", 'gtin': final_di}

        print("\n❌ 모든 공정을 시도했으나 정보를 찾지 못했습니다.")
        print(f"--- 🛰️ 공정 종료 ---\n")
        return None

    def sync_with_local_db(self, api_data: Dict, local_data: Dict) -> Dict:
        synced = local_data.copy()
        if api_data:
            synced['name'] = api_data.get('name') or local_data.get('name')
            synced['power'] = api_data.get('power') or local_data.get('power')
        return synced
