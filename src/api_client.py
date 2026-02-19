import os
import requests
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Optional, Any, List
from dotenv import load_dotenv

load_dotenv()

class APIClient:
    """모든 파라미터 명칭을 시도하여 500 에러를 피하고 정보를 찾아내는 최종 클라이언트"""

    def __init__(self):
        self.api_key = os.getenv("LENS_API_KEY", "").strip()
        self.base_url = "https://apis.data.go.kr/1471000"

    def _is_garbage(self, text: str) -> bool:
        if not text or len(text) < 2: return True
        garbage = ["null", "none", "nan", "평가되지", "undefined", "미등록", "미지정", "n/a"]
        return text.lower() in garbage

    def _clean_val(self, val: Any) -> str:
        if not val: return ""
        return str(val).strip().replace('"', '').replace('}', '').replace(',', '').replace(';', '')

    def _extract_info(self, content: str) -> Optional[Dict[str, str]]:
        """데이터에서 실제 정보를 추출하고 검증"""
        fields = ["PRDT_NM", "PRDT_ADD_EXPL", "MODEL_NM", "ITEM_NM", "PRDLST_NM"]
        for f in fields:
            match = re.search(rf'{field}["\>\]\s:]+([^"<\n]+)', content, re.IGNORECASE) if 'field' not in locals() else re.search(rf'{f}["\>\]\s:]+([^"<\n]+)', content, re.IGNORECASE)
            if match:
                raw = self._clean_val(match.group(1))
                if not self._is_garbage(raw):
                    p_match = re.search(r'([+-]?\d+\.\d{2})', raw)
                    power = p_match.group(1) if p_match else "N/A"
                    name = raw.replace(power, "").strip("- ").strip()
                    if not self._is_garbage(name):
                        return {"name": name, "power": power, "field": f}
        return None

    def _try_request(self, service: str, endpoint: str, param: str, val: str) -> Optional[str]:
        """상세 로그를 남기며 API를 호출합니다."""
        url = f"{self.base_url}/{service}/{endpoint}"
        # 상세 조회용 주소 (pageNo 제외)
        full_url = f"{url}?serviceKey={self.api_key}&type=json&{param}={val}"
        
        print(f"  🔎 조회: {endpoint} ({param}={val})")
        try:
            response = requests.get(full_url, timeout=6)
            if response.status_code == 200:
                if '"totalCount":0' in response.text or '<totalCount>0' in response.text:
                    return None
                return response.text
            elif response.status_code == 500:
                print(f"    ⚠️ {endpoint}: 500 에러 (파라미터 '{param}' 불일치 가능성)")
        except Exception: pass
        return None

    def fetch_product_info(self, identifier: str) -> Optional[Dict]:
        if not identifier: return None
        target_id = identifier.zfill(14)
        print(f"\n--- 🛰️ [최종 추적] 렌즈 정보 정밀 검색 시작 ({target_id}) ---")

        # 시도할 모든 경로와 파라미터 조합 (가장 확률 높은 순)
        # MsUdedi(신규)와 Mdeq(기존)를 모두 포함
        tasks = [
            ("MsUdediInfoService", "getUdediInfo", "UDIDI_CD"),
            ("MsUdediInfoService", "getUdediInfo", "udi"),
            ("MsUdediInfoService", "getUdediInfo", "udi_di"),
            ("MdeqStdCdUnityInfoService01", "getMdeqStdCdUnityInfoInq01", "UDIDI_CD"),
            ("MdeqStdCdUnityInfoService01", "getMdeqStdCdUnityInfoInq01", "udi_code"),
            ("MdeqStdCdUnityInfoService01", "getMdeqStdCdInq01", "gtin_code")
        ]

        # 병렬로 모든 가능성을 동시에 찔러봅니다.
        with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
            future_to_task = {executor.submit(self._try_request, *task, target_id): task for task in tasks}
            
            for future in as_completed(future_to_task):
                content = future.result()
                if content:
                    info = self._extract_info(content)
                    if info:
                        print(f"\n✅ 성공: {info['name']} ({info['power']})")
                        print(f"--- 🛰️ 추적 종료 ---\n")
                        return {'name': info['name'], 'power': info['power'], 'manufacturer': "식약처 등록 제품", 'gtin': target_id}

        print("\n❌ 모든 경로와 파라미터로 시도했으나 유효한 데이터를 찾지 못했습니다.")
        print(f"--- 🛰️ 추적 종료 ---\n")
        return None

    def sync_with_local_db(self, api_data: Dict, local_data: Dict) -> Dict:
        synced = local_data.copy()
        if api_data:
            synced['name'] = api_data.get('name') or local_data.get('name')
            synced['power'] = api_data.get('power') or local_data.get('power')
        return synced
