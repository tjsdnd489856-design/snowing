import os
import requests
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Optional, Any, List
from dotenv import load_dotenv

load_dotenv()

class APIClient:
    """가짜 데이터(null)를 완벽하게 차단하고 정밀 검색을 수행하는 마스터 클라이언트"""

    def __init__(self):
        self.api_key = os.getenv("LENS_API_KEY", "").strip()
        self.base_url = "https://apis.data.go.kr/1471000"

    def _is_garbage(self, text: str) -> bool:
        """텍스트에 가짜 정보(null 등)가 포함되어 있는지 엄격하게 확인"""
        if not text or len(text.strip()) < 2: return True
        
        # 차단할 단어 목록 (하나라도 포함되면 차단)
        garbage_keywords = ["null", "none", "nan", "평가되지", "undefined", "미등록", "미지정", "n/a", "해당사항"]
        lower_text = text.lower()
        
        # 키워드 포함 여부 확인
        for kw in garbage_keywords:
            if kw in lower_text: return True
            
        # 의미 없는 특수문자만 있는 경우 차단
        if not re.search(r'[a-zA-Z가-힣0-9]', text): return True
            
        return False

    def _clean_val(self, val: Any) -> str:
        if not val: return ""
        # 쉼표, 따옴표, 괄호 등 불필요한 기호 제거
        return str(val).strip().replace('"', '').replace('}', '').replace(',', '').replace(';', '')

    def _extract_info(self, content: str) -> Optional[Dict[str, str]]:
        """데이터 뭉치에서 실제 제품명과 도수를 추출"""
        fields = ["PRDT_NM", "PRDT_ADD_EXPL", "MODEL_NM", "ITEM_NM", "PRDT_NM_CONT", "PRDLST_NM"]
        
        for f in fields:
            match = re.search(rf'{f}["\>\]\s:]+([^"<\n]+)', content, re.IGNORECASE)
            if match:
                raw = self._clean_val(match.group(1))
                # 가짜 데이터가 아니어야 함
                if not self._is_garbage(raw):
                    # 도수 추출 (-7.00 등)
                    p_match = re.search(r'([+-]?\d+\.\d{2})', raw)
                    power = p_match.group(1) if p_match else "N/A"
                    # 이름에서 도수 제거 및 정리
                    name = raw.replace(power, "").strip("- ").strip()
                    # 정리된 이름이 다시 한 번 가짜인지 확인
                    if not self._is_garbage(name):
                        return {"name": name, "power": power, "field": f}
        return None

    def _try_request(self, service: str, endpoint: str, param: str, val: str, use_page: bool = False) -> Optional[str]:
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
        print(f"\n--- 🛰️ [추적] {target_id} 정보 검색 중... ---")

        # [1단계] 목록 조회로 진짜 식별자 확보 시도
        list_content = self._try_request("MsUdediInfoService", "getUdediList", "UDIDI_CD", target_id, use_page=True)
        udidi_cd = None
        if list_content:
            match = re.search(r'UDIDI_CD["\>\]\s:]+([^"<\n]+)', list_content, re.IGNORECASE)
            if match: udidi_cd = self._clean_val(match.group(1))

        final_di = udidi_cd if udidi_cd else target_id

        # [2단계] 상세 조회 (여러 경로 병렬 시도)
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
                        print(f"✅ 발견: {info['name']} ({info['power']})")
                        return {'name': info['name'], 'power': info['power'], 'manufacturer': "식약처 정식 등록", 'gtin': final_di}

        print("📭 유효한 정보를 찾지 못했습니다.")
        return None

    def sync_with_local_db(self, api_data: Dict, local_data: Dict) -> Dict:
        synced = local_data.copy()
        if api_data:
            synced['name'] = api_data.get('name') or local_data.get('name')
            synced['power'] = api_data.get('power') or local_data.get('power')
        return synced
