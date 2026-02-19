import os
import requests
import re
import urllib.parse
from typing import Dict, Optional, Any, List
from dotenv import load_dotenv

load_dotenv()

class APIClient:
    """모든 상세 서랍을 순차적으로 뒤져서 문제 지점을 찾아내는 정밀 진단 클라이언트"""

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
        """데이터 뭉치에서 제품명과 도수를 추출"""
        fields = ["PRDT_ADD_EXPL", "MODEL_NM", "PRDT_NM", "ITEM_NM", "PRDLST_NM"]
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
        """[체크포인트 1~4]를 거치며 어느 서랍에 정보가 있는지 추적합니다."""
        if not identifier: return None
        target_id = identifier.zfill(14)
        print(f"\n--- 🛰️ [진단 시작] 렌즈 정보 정밀 추적 ({target_id}) ---")

        # 1. 존재 확인 (Mdeq)
        print(f"\n📍 [체크포인트 1: 통합 DB 존재 여부 확인]")
        u_url = f"{self.base_url}/MdeqStdCdUnityInfoService01/getMdeqStdCdUnityInfoInq01"
        u_full = f"{u_url}?serviceKey={self.api_key}&type=json&pageNo=1&numOfRows=1&UDIDI_CD={target_id}"
        
        try:
            res = requests.get(u_full, timeout=7)
            if res.status_code == 200 and ('"totalCount":0' not in res.text and '<totalCount>0' not in res.text):
                print(f"  ✅ 확인: 통합 DB에 등록된 제품입니다. 상세 조회를 시작합니다.")
            else:
                print(f"  ❌ 확인: 통합 DB에 정보가 없습니다. (미등록 번호일 가능성)")
        except Exception as e:
            print(f"  ⚠️ 오류: 통합 DB 접속 실패 ({str(e)})")

        # 2. 상세 서랍 탐색 목록
        drawers = [
            {"name": "최신 UDI/EDI 서랍 (MsUdedi)", "svc": "MsUdediInfoService", "end": "getUdediInfo"},
            {"name": "통합 상세 서랍 (Mdeq)", "svc": "MdeqStdCdUnityInfoService01", "end": "getMdeqStdCdUnityInfoInq01"},
            {"name": "기본 표준코드 서랍 (Mdeq)", "svc": "MdeqStdCdUnityInfoService01", "end": "getMdeqStdCdInq01"},
            {"name": "구형 UDI 서랍 (Mdv)", "svc": "MdvUdiInfoService", "end": "getMdvUdiInfoInq01"}
        ]

        print(f"\n📍 [체크포인트 2: 모든 상세 서랍 순차 탐색]")
        for dr in drawers:
            url = f"{self.base_url}/{dr['svc']}/{dr['end']}"
            full_url = f"{url}?serviceKey={self.api_key}&type=json&pageNo=1&numOfRows=1&UDIDI_CD={target_id}"
            
            print(f"  🔎 {dr['name']} 여는 중...")
            try:
                response = requests.get(full_url, timeout=7)
                if response.status_code == 200:
                    content = response.text
                    if '"totalCount":0' in content or '<totalCount>0' in content:
                        print(f"    📭 결과: 이 서랍은 비어있습니다.")
                        continue
                    
                    # 3. 알맹이 추출 및 검증
                    info = self._extract_info(content)
                    if info:
                        print(f"    ✅ 성공: '{info['field']}' 필드에서 정보를 찾았습니다!")
                        print(f"\n🎉 [진단 완료] 정보 획득 성공!")
                        print(f"  📦 제품명: {info['name']}")
                        print(f"  💎 도수: {info['power']}")
                        return {'name': info['name'], 'power': info['power'], 'manufacturer': "식약처 등록 제품", 'gtin': target_id}
                    else:
                        print(f"    ⚠️ 경고: 데이터는 있으나 유효한 이름이 없습니다. (null 등)")
                else:
                    print(f"    ❌ 에러: 서버 응답 오류 ({response.status_code})")
            except Exception as e:
                print(f"    ❌ 오류: 접속 실패 ({str(e)})")

        print("\n❌ [최종 실패] 모든 서랍을 뒤졌으나 유효한 제품명을 찾지 못했습니다.")
        print(f"--- 🛰️ [진단 종료] ---\n")
        return None

    def sync_with_local_db(self, api_data: Dict, local_data: Dict) -> Dict:
        synced = local_data.copy()
        if api_data:
            synced['name'] = api_data.get('name') or local_data.get('name')
            synced['power'] = api_data.get('power') or local_data.get('power')
        return synced
