import os
import requests
import re
import urllib.parse
from typing import Dict, Optional, Any
from dotenv import load_dotenv

load_dotenv()

class APIClient:
    """식별된 UDI-DI 코드로 2단계 정석 조회를 수행하는 클라이언트"""

    def __init__(self):
        self.api_key = os.getenv("LENS_API_KEY", "").strip()
        self.base_url = "https://apis.data.go.kr/1471000"

    def _is_garbage(self, text: str) -> bool:
        if not text or len(text.strip()) < 2: return True
        garbage = ["null", "none", "nan", "평가되지", "undefined", "미등록", "미지정", "n/a"]
        return text.lower() in garbage

    def _clean_val(self, val: Any) -> str:
        if not val: return ""
        return str(val).strip().replace('"', '').replace('}', '').replace(',', '').replace(';', '')

    def _extract_info(self, content: str) -> Optional[Dict[str, str]]:
        """응답 텍스트에서 제품명과 도수를 정밀 추출"""
        # 상세설명(PRDT_ADD_EXPL) 필드 우선, 없으면 품목명(PRDT_NM) 사용
        fields = ["PRDT_ADD_EXPL", "PRDT_NM", "MODEL_NM", "ITEM_NM", "PRDT_NM_CONT"]
        for f in fields:
            match = re.search(rf'{f}["\>\]\s:]+([^"<\n]+)', content, re.IGNORECASE)
            if match:
                raw = self._clean_val(match.group(1))
                if not self._is_garbage(raw):
                    # 도수(-7.00 등) 정밀 추출
                    p_match = re.search(r'([+-]?\d+\.\d{2})', raw)
                    power = p_match.group(1) if p_match else "N/A"
                    name = raw.replace(power, "").strip("- ").strip()
                    if not self._is_garbage(name):
                        return {"name": name, "power": power}
        return None

    def _call_api(self, service: str, endpoint: str, udidi: str) -> Optional[str]:
        """정확한 UDIDI_CD 파라미터로 식약처 API 호출"""
        url = f"{self.base_url}/{service}/{endpoint}"
        # 인증키 보호를 위해 URL을 문자열로 조립
        full_url = f"{url}?serviceKey={self.api_key}&type=json&pageNo=1&numOfRows=1&UDIDI_CD={udidi}"
        
        try:
            print(f"  📡 {endpoint} 조회 중...")
            response = requests.get(full_url, timeout=10)
            if response.status_code == 200:
                if '"totalCount":0' in response.text or '<totalCount>0' in response.text:
                    print(f"    📭 결과: 해당 서랍에 데이터가 없습니다.")
                    return None
                return response.text
            else:
                print(f"    ❌ 실패: 서버 응답 {response.status_code}")
        except Exception as e:
            print(f"    ⚠️ 오류: 연결 실패 ({str(e)})")
        return None

    def fetch_product_info(self, udidi: str) -> Optional[Dict]:
        """[1단계:Mdeq 확인] -> [2단계:Mdv 상세조회] 순서로 진행"""
        if not udidi: return None
        print(f"\n--- 🚀 식약처 정석 2단계 추적 시작 (ID: {udidi}) ---")

        # 1단계: MdeqStdCdUnityInfoService01 (기본정보 및 존재 확인)
        print("\n[1단계] 통합정보망에서 제품 확인")
        content_1 = self._call_api("MdeqStdCdUnityInfoService01", "getMdeqStdCdUnityInfoInq01", udidi)
        
        if content_1:
            print("  ✅ 1단계 통과: 제품이 등록되어 있습니다.")
            # 2단계: MdvUdiInfoService (상세정보/도수 조회)
            print("\n[2단계] UDI 전용 서랍에서 상세 스펙 조회")
            content_2 = self._call_api("MdvUdiInfoService", "getMdvUdiInfoInq01", udidi)
            
            # 정보 추출 (2단계 우선, 없으면 1단계 사용)
            final_content = content_2 if content_2 else content_1
            info = self._extract_info(final_content)
            
            if info:
                print(f"\n🎉 정보 획득 성공: {info['name']} / {info['power']}")
                return {'name': info['name'], 'power': info['power'], 'manufacturer': "식약처 등록 제품", 'gtin': udidi}

        print("\n❌ 정보 조회 실패: 수동 입력으로 진행합니다.")
        return None

    def sync_with_local_db(self, api_data: Dict, local_data: Dict) -> Dict:
        synced = local_data.copy()
        if api_data:
            synced.update({'name': api_data.get('name'), 'power': api_data.get('power')})
        return synced
