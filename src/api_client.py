import os
import requests
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Optional, Any, List
from dotenv import load_dotenv

load_dotenv()

class APIClient:
    """가짜 데이터를 완벽 차단하고 상세 과정을 출력하는 정밀 클라이언트"""

    def __init__(self):
        self.api_key = os.getenv("LENS_API_KEY", "").strip()
        self.base_url = "https://apis.data.go.kr/1471000"

    def _is_garbage(self, text: str) -> bool:
        """깨끗해진 텍스트가 여전히 가짜 정보인지 확인"""
        if not text or len(text) < 2: return True
        garbage = ["null", "none", "nan", "평가되지", "undefined", "미등록", "미지정", "n/a"]
        return text.lower() in garbage

    def _extract_from_content(self, content: str) -> Optional[Dict[str, str]]:
        """어떤 형식에서든 알맹이만 쏙 뽑아내는 로직"""
        fields = ["PRDT_ADD_EXPL", "MODEL_NM", "PRDT_NM", "ITEM_NM", "MDEQ_PRDLST_NM", "PRDLST_NM"]
        
        for field in fields:
            match = re.search(rf'{field}["\>\]\s:]+([^"<\n]+)', content, re.IGNORECASE)
            if match:
                # 먼저 불순물 제거
                raw = match.group(1).strip().replace('"', '').replace('}', '').replace(',', '').replace(';', '')
                if not self._is_garbage(raw):
                    # 도수 분리
                    power_match = re.search(r'([+-]?\d+\.\d{2})', raw)
                    power = power_match.group(1) if power_match else "N/A"
                    name = raw.replace(power, "").strip("- ").strip()
                    if not self._is_garbage(name):
                        return {"name": name, "power": power, "field": field}
        return None

    def _try_request(self, service: str, endpoint: str, param: str, val: str) -> Optional[str]:
        """API 요청 및 상태 출력"""
        url = f"{self.base_url}/{service}/{endpoint}"
        full_url = f"{url}?serviceKey={self.api_key}&type=json&pageNo=1&numOfRows=1&{param}={val}"
        
        print(f"  [요청] {endpoint} ({param}={val})")
        try:
            response = requests.get(full_url, timeout=7)
            if response.status_code == 200:
                # 0건 결과는 None 반환
                if '"totalCount":0' in response.text or '<totalCount>0' in response.text:
                    print(f"  [결과] {endpoint}: 데이터 없음")
                    return None
                return response.text
            else:
                print(f"  [실패] {endpoint}: 상태코드 {response.status_code}")
        except Exception:
            pass
        return None

    def fetch_product_info(self, identifier: str) -> Optional[Dict]:
        """모든 단계를 거쳐 진짜 정보만 가져옵니다."""
        if not identifier: return None
        target_id = identifier.zfill(14)
        print(f"\n--- 🛰️ 정밀 추적 시작: {target_id} ---")

        # 1단계: MsUdediInfoService 우선 조회
        print("\n[1단계] 최신 UDI/EDI 서비스 확인")
        tasks = [
            ("MsUdediInfoService", "getUdediInfo", "UDIDI_CD"),
            ("MsUdediInfoService", "getUdediList", "UDIDI_CD")
        ]
        
        for svc, end, param in tasks:
            content = self._try_request(svc, end, param, target_id)
            if content:
                info = self._extract_from_content(content)
                if info:
                    print(f"✅ 발견! ({info['field']})")
                    return {'name': info['name'], 'power': info['power'], 'manufacturer': "정부 DB 등록 제품", 'gtin': target_id}

        # 2단계: 통합정보 서비스 폴백 (병렬)
        print("\n[2단계] 표준코드 통합 서비스 동시 확인")
        fallback_tasks = [
            ("MdeqStdCdUnityInfoService01", "getMdeqStdCdUnityInfoInq01", "UDIDI_CD"),
            ("MdeqStdCdUnityInfoService01", "getMdeqStdCdUnityInfoInq01", "udi_code"),
            ("MdeqStdCdUnityInfoService01", "getMdeqStdCdInq01", "gtin_code")
        ]

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(self._try_request, *task, target_id) for task in fallback_tasks]
            for future in as_completed(futures):
                content = future.result()
                if content:
                    info = self._extract_from_content(content)
                    if info:
                        print(f"✅ 발견! ({info['field']})")
                        return {'name': info['name'], 'power': info['power'], 'manufacturer': "정부 DB 등록 제품", 'gtin': target_id}

        print("\n❌ 유효한 정보를 찾지 못했습니다. (수동 입력 필요)")
        return None

    def sync_with_local_db(self, api_data: Dict, local_data: Dict) -> Dict:
        synced = local_data.copy()
        if api_data:
            synced['name'] = api_data.get('name') or local_data.get('name')
            synced['power'] = api_data.get('power') or local_data.get('power')
        return synced
