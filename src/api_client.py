import os
import requests
import re
import urllib.parse
from typing import Dict, Optional, Any
from dotenv import load_dotenv

load_dotenv()

class APIClient:
    """식약처 정석 2단계 조회를 수행하는 전용 클라이언트"""

    def __init__(self):
        # 인증키 인코딩 이슈를 방지하기 위해 unquote 후 다시 quote 관리하거나 원본 그대로 사용
        self.api_key = os.getenv("LENS_API_KEY", "").strip()
        self.base_url = "https://apis.data.go.kr/1471000"

    def _is_garbage(self, text: str) -> bool:
        if not text or len(text.strip()) < 2: return True
        garbage = ["null", "none", "nan", "평가되지", "undefined", "미등록", "미지정", "n/a"]
        return any(kw in text.lower() for kw in garbage)

    def _clean_val(self, val: Any) -> str:
        if not val: return ""
        return str(val).strip().replace('"', '').replace('}', '').replace(',', '').replace(';', '')

    def _extract_info(self, content: str) -> Optional[Dict[str, str]]:
        """응답 텍스트에서 제품명과 도수 추출"""
        fields = ["PRDT_NM", "PRDT_ADD_EXPL", "MODEL_NM", "ITEM_NM"]
        for f in fields:
            match = re.search(rf'{f}["\>\]\s:]+([^"<\n]+)', content, re.IGNORECASE)
            if match:
                raw = self._clean_val(match.group(1))
                if not self._is_garbage(raw):
                    # 도수(-7.00 등) 추출
                    p_match = re.search(r'([+-]?\d+\.\d{2})', raw)
                    power = p_match.group(1) if p_match else "N/A"
                    name = raw.replace(power, "").strip("- ").strip()
                    if not self._is_garbage(name):
                        return {"name": name, "power": power}
        return None

    def _call_api(self, service: str, endpoint: str, udidi: str) -> Optional[str]:
        """정확한 UDIDI_CD 파라미터를 사용하여 API 호출"""
        url = f"{self.base_url}/{service}/{endpoint}"
        # URL 인코딩된 키를 안전하게 전달하기 위해 직접 URL 구성
        full_url = f"{url}?serviceKey={self.api_key}&type=json&pageNo=1&numOfRows=1&UDIDI_CD={udidi}"
        
        try:
            print(f"  📡 호출 중: {endpoint}...")
            response = requests.get(full_url, timeout=10)
            if response.status_code == 200:
                if '"totalCount":0' in response.text or '<totalCount>0' in response.text:
                    print(f"    📭 결과: 데이터 없음")
                    return None
                return response.text
            else:
                print(f"    ❌ 에러: 서버 응답 오류 ({response.status_code})")
        except Exception as e:
            print(f"    ⚠️ 오류: 연결 실패 ({str(e)})")
        return None

    def fetch_product_info(self, identifier: str) -> Optional[Dict]:
        if not identifier: return None
        # 바코드 파서에서 이미 GTIN(14자리)을 추출해 보내준다고 가정
        udidi = identifier.zfill(14)
        print(f"\n--- 🚀 식약처 정석 추적 시작 (UDI-DI: {udidi}) ---")

        # 1단계: MdeqStdCdUnityInfoService01 (기본정보 확인)
        print("\n[1단계] 통합정보 서비스 확인 중...")
        content_1 = self._call_api("MdeqStdCdUnityInfoService01", "getMdeqStdCdUnityInfoInq01", udidi)
        
        if content_1:
            print("  ✅ 1단계 성공: 레코드 발견")
            # 2단계: MdvUdiInfoService (상세정보 조회)
            print("\n[2단계] UDI 상세정보 조회 중...")
            content_2 = self._call_api("MdvUdiInfoService", "getMdvUdiInfoInq01", udidi)
            
            # 2단계 결과가 있으면 사용, 없으면 1단계 결과라도 분석
            final_content = content_2 if content_2 else content_1
            info = self._extract_info(final_content)
            
            if info:
                print(f"\n🎉 최종 정보 획득: {info['name']} / {info['power']}")
                return {
                    'name': info['name'],
                    'power': info['power'],
                    'manufacturer': "식약처 등록 제품",
                    'gtin': udidi
                }

        print("\n❌ 정보 조회 실패: 수동 입력이 필요합니다.")
        return None

    def sync_with_local_db(self, api_data: Dict, local_data: Dict) -> Dict:
        synced = local_data.copy()
        if api_data:
            synced.update({
                'name': api_data.get('name') or local_data.get('name'),
                'power': api_data.get('power') or local_data.get('power')
            })
        return synced
