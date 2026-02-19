import os
import requests
import re
import urllib.parse
from typing import Dict, Optional, Any
from dotenv import load_dotenv

load_dotenv()

class APIClient:
    """구간별 체크포인트 로그가 강화된 정밀 진단 클라이언트"""

    def __init__(self):
        self.api_key = os.getenv("LENS_API_KEY", "").strip()
        self.base_url = "https://apis.data.go.kr/1471000"

    def _is_garbage(self, text: str) -> bool:
        """가짜 데이터 필터링"""
        if not text or len(text) < 2: return True
        garbage = ["null", "none", "nan", "평가되지", "undefined", "미등록", "미지정", "n/a"]
        return text.lower() in garbage

    def _clean_val(self, val: Any) -> str:
        if not val: return ""
        return str(val).strip().replace('"', '').replace('}', '').replace(',', '').replace(';', '')

    def fetch_product_info(self, identifier: str) -> Optional[Dict]:
        """[체크포인트 1~3] 과정을 거치며 정보를 정밀 추적합니다."""
        if not identifier: return None
        target_id = identifier.zfill(14)
        print(f"\n--- 🛰️ [진단 시작] UDI 추적 레포트 ({target_id}) ---")

        # --- 1단계: Mdeq 서비스 (존재 확인) ---
        print(f"\n📍 [체크포인트 1: 통합정보망 확인]")
        u_url = f"{self.base_url}/MdeqStdCdUnityInfoService01/getMdeqStdCdUnityInfoInq01"
        u_full = f"{u_url}?serviceKey={self.api_key}&type=json&pageNo=1&numOfRows=1&UDIDI_CD={target_id}"
        
        try:
            res = requests.get(u_full, timeout=7)
            if res.status_code == 200:
                if '"totalCount":0' in res.text or '<totalCount>0' in res.text:
                    print(f"  ❌ 결과: 식약처 통합 DB에 등록되지 않은 바코드 번호입니다.")
                else:
                    print(f"  ✅ 결과: 통합 DB 등록 확인됨. 상세 조회를 계속합니다.")
            else:
                print(f"  ⚠️ 결과: 서버 접속 실패 (상태코드: {res.status_code})")
        except Exception as e:
            print(f"  ⚠️ 결과: 네트워크 오류 ({str(e)})")

        # --- 2단계: Mdv 서비스 (알맹이 추출) ---
        print(f"\n📍 [체크포인트 2: UDI 상세정보 서랍 조회]")
        d_url = f"{self.base_url}/MdvUdiInfoService/getMdvUdiInfoInq01"
        d_full = f"{d_url}?serviceKey={self.api_key}&type=json&pageNo=1&numOfRows=1&UDIDI_CD={target_id}"
        
        try:
            res_d = requests.get(d_full, timeout=7)
            if res_d.status_code == 200:
                content = res_d.text
                if '"totalCount":0' in content or '<totalCount>0' in content:
                    print(f"  ❌ 결과: UDI 상세 서랍이 비어있습니다. (데이터 미등록)")
                else:
                    print(f"  ✅ 결과: 상세 서랍 열기 성공. 데이터 분석을 시작합니다.")
                    
                    # --- 3단계: 데이터 품질 및 필드 분석 ---
                    print(f"\n📍 [체크포인트 3: 데이터 품질 및 필드 분석]")
                    fields = ["PRDT_NM", "MODEL_NM", "PRDT_ADD_EXPL", "ITEM_NM"]
                    for f in fields:
                        match = re.search(rf'{f}["\>\]\s:]+([^"<\n]+)', content, re.IGNORECASE)
                        if match:
                            raw_name = self._clean_val(match.group(1))
                            print(f"  🔎 '{f}' 필드에서 값 발견: '{raw_name}'")
                            
                            if self._is_garbage(raw_name):
                                print(f"  ⚠️ 결과: 발견된 정보가 가짜 데이터(null 등)이므로 무시합니다.")
                                continue
                            
                            # 도수 및 규격 추출
                            spec_match = re.search(r'SPEC["\>\]\s:]+([^"<\n]+)', content, re.IGNORECASE)
                            spec = self._clean_val(spec_match.group(1)) if spec_match else "N/A"
                            
                            power = "N/A"
                            p_match = re.search(r'([+-]?\d+\.\d{2})', f"{raw_name} {spec}")
                            if p_match: power = p_match.group(1)
                            
                            name = raw_name.replace(power, "").strip("- ").strip()
                            
                            print(f"\n🎉 [최종 성공] 모든 검증 통과!")
                            print(f"  📦 최종 제품명: {name}")
                            print(f"  💎 최종 도수: {power}")
                            print(f"--- 🛰️ [진단 종료] ---\n")
                            return {
                                'name': name,
                                'power': power,
                                'manufacturer': "식약처 정식 등록 제품",
                                'gtin': target_id
                            }
            else:
                print(f"  ⚠️ 결과: 상세 서버 응답 에러 ({res_d.status_code})")
        except Exception as e:
            print(f"  ⚠️ 결과: 상세 서버 연결 실패 ({str(e)})")

        print("\n❌ [최종 실패] 유효한 정보를 찾지 못했습니다. 수동 입력 단계로 넘어갑니다.")
        print(f"--- 🛰️ [진단 종료] ---\n")
        return None

    def sync_with_local_db(self, api_data: Dict, local_data: Dict) -> Dict:
        synced = local_data.copy()
        if api_data:
            synced['name'] = api_data.get('name') or local_data.get('name')
            synced['power'] = api_data.get('power') or local_data.get('power')
        return synced
