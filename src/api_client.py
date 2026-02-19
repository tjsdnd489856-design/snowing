import os
import requests
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Optional, Any, List
from dotenv import load_dotenv

load_dotenv()

class APIClient:
    """2단계 체인 검색을 수행하되, 이전 서비스까지 모두 포괄하는 하이브리드 클라이언트"""

    def __init__(self):
        self.api_key = os.getenv("LENS_API_KEY", "").strip()
        self.base_url = "https://apis.data.go.kr/1471000"

    def _clean_val(self, val: Any) -> str:
        if not val or str(val).lower() in ["null", "none", "nan", "평가되지", "평가되지 않음"]:
            return ""
        return str(val).strip().replace('"', '').replace('}', '').replace(',', '')

    def _extract_from_content(self, content: str) -> Optional[Dict[str, str]]:
        """어떤 형식(JSON/XML)에서든 제품명과 도수를 추출하는 무적 파서"""
        # 검색할 핵심 필드들
        fields = ["PRDT_ADD_EXPL", "MODEL_NM", "PRDT_NM", "ITEM_NM", "MDEQ_PRDLST_NM"]
        raw_text = ""
        
        for field in fields:
            match = re.search(rf'{field}["\>\]\s:]+([^"<\n]+)', content, re.IGNORECASE)
            if match:
                text = self._clean_val(match.group(1))
                if len(text) > 1:
                    raw_text = text
                    break
        
        if not raw_text: return None

        # 도수 추출 (-7.00, +1.50 등)
        power_match = re.search(r'([+-]?\d+\.\d{2})', raw_text)
        power = power_match.group(1) if power_match else "N/A"
        
        # 이름 정리
        name = raw_text.replace(power, "")
        name = re.sub(r'\(.*?\)', '', name).strip("- ").strip()
        
        if len(name) < 2: return None
        return {"name": name, "power": power}

    def _try_request(self, service: str, endpoint: str, param: str, val: str) -> Optional[str]:
        """단일 API 요청을 보내고 원본 텍스트를 반환"""
        url = f"{self.base_url}/{service}/{endpoint}"
        full_url = f"{url}?serviceKey={self.api_key}&type=json&pageNo=1&numOfRows=1&{param}={val}"
        try:
            response = requests.get(full_url, timeout=5)
            if response.status_code == 200:
                return response.text
        except Exception:
            pass
        return None

    def fetch_product_info(self, identifier: str) -> Optional[Dict]:
        """[2단계 체인] + [멀티 서비스 폴백] 통합 로직"""
        if not identifier: return None
        target_id = identifier.zfill(14)

        # --- 1단계: 신규 서비스에서 UDI-DI 식별자 확보 시도 ---
        print(f"🔍 1단계: 신규 서비스(MsUdedi)에서 식별자 찾는 중...")
        list_content = self._try_request("MsUdediInfoService", "getUdediList", "UDIDI_CD", target_id)
        
        udidi_cd = None
        if list_content:
            match = re.search(r'UDIDI_CD["\>\]\s:]+([^"<\n]+)', list_content, re.IGNORECASE)
            if match:
                udidi_cd = self._clean_val(match.group(1))

        # 식별자를 못 찾았다면 입력값 자체를 식별자로 사용
        final_di = udidi_cd if udidi_cd else target_id

        # --- 2단계: 확보된 식별자로 모든 서랍 동시에 뒤지기 (병렬) ---
        print(f"📖 2단계: 상세 정보 금고 여는 중... (DI: {final_di})")
        
        # 병렬로 뒤져볼 서비스와 엔드포인트 조합
        tasks = [
            ("MsUdediInfoService", "getUdediInfo", "UDIDI_CD"),
            ("MdeqStdCdUnityInfoService01", "getMdeqStdCdUnityInfoInq01", "UDIDI_CD"),
            ("MdeqStdCdUnityInfoService01", "getMdeqStdCdUnityInfoInq01", "udi_code"),
            ("MdvUdiInfoService", "getMdvUdiInfoInq01", "UDIDI_CD")
        ]

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(self._try_request, *task, final_di) for task in tasks]
            for future in as_completed(futures):
                content = future.result()
                if content and '"totalCount":0' not in content and '<totalCount>0' not in content:
                    info = self._extract_from_content(content)
                    if info:
                        print(f"✅ 최종 정보 획득 성공!")
                        return {
                            'name': info['name'],
                            'power': info['power'],
                            'manufacturer': "식약처 등록 제품",
                            'gtin': final_di
                        }

        print("📭 모든 경로를 시도했으나 정보를 찾지 못했습니다.")
        return None

    def sync_with_local_db(self, api_data: Dict, local_data: Dict) -> Dict:
        synced = local_data.copy()
        if api_data:
            synced['name'] = api_data.get('name') or local_data.get('name')
            synced['power'] = api_data.get('power') or local_data.get('power')
        return synced
