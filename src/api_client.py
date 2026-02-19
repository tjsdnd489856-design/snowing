import os
import requests
import re
import urllib.parse
from typing import Dict, Optional, Any
from dotenv import load_dotenv

load_dotenv()

class APIClient:
    """통합정보 확인 후 UDI 서비스로 상세정보를 가져오는 2단계 정밀 클라이언트"""

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

    def _extract_power(self, text: str) -> str:
        """텍스트에서 도수(-7.00 등) 추출"""
        if not text: return "N/A"
        match = re.search(r'([+-]?\d+\.\d{2})', text)
        return match.group(1) if power_match else text

    def fetch_product_info(self, identifier: str) -> Optional[Dict]:
        """[1단계: 통합정보 확인] -> [2단계: UDI 상세조회] 순서로 진행"""
        if not identifier: return None
        target_id = identifier.zfill(14)
        print(f"\n--- 🛰️ 2단계 연쇄 추적 시작: {target_id} ---")

        # --- 1단계: MdeqStdCdUnityInfoService01 (기본정보 확인) ---
        print(f"\n[1단계] 통합정보 서비스에서 기본 레코드 확인 중...")
        u_url = f"{self.base_url}/MdeqStdCdUnityInfoService01/getMdeqStdCdUnityInfoInq01"
        u_full = f"{u_url}?serviceKey={self.api_key}&type=json&pageNo=1&numOfRows=1&UDIDI_CD={target_id}"
        
        has_record = False
        try:
            res = requests.get(u_full, timeout=7)
            if res.status_code == 200 and '"totalCount":0' not in res.text and '<totalCount>0' not in res.text:
                print(f"  ✅ 1단계 성공: 레코드 확인됨")
                has_record = True
            else:
                # udi_code 파라미터로 한 번 더 시도
                u_full_alt = f"{u_url}?serviceKey={self.api_key}&type=json&pageNo=1&numOfRows=1&udi_code={target_id}"
                res_alt = requests.get(u_full_alt, timeout=7)
                if res_alt.status_code == 200 and '"totalCount":0' not in res_alt.text:
                    print(f"  ✅ 1단계 성공: 레코드 확인됨 (udi_code)")
                    has_record = True
        except Exception as e:
            print(f"  ⚠️ 1단계 접속 오류: {e}")

        # --- 2단계: MdvUdiInfoService (상세정보 조회) ---
        # 1단계 성공 여부와 상관없이 조회를 시도하여 성공률을 높입니다.
        print(f"\n[2단계] UDI 정보 서비스에서 상세 스펙(제품명/도수) 추출 중...")
        d_url = f"{self.base_url}/MdvUdiInfoService/getMdvUdiInfoInq01"
        d_full = f"{d_url}?serviceKey={self.api_key}&type=json&pageNo=1&numOfRows=1&UDIDI_CD={target_id}"
        
        try:
            res_d = requests.get(d_full, timeout=7)
            if res_d.status_code == 200:
                content = res_d.text
                if '"totalCount":0' in content or '<totalCount>0' in content:
                    print(f"  ❌ 2단계 결과 없음: 상세 서랍이 비어있습니다.")
                else:
                    # 상세 정보 필드 추출 (PRDT_NM, SPEC, PRDT_ADD_EXPL 등)
                    fields = ["PRDT_NM", "MODEL_NM", "PRDT_ADD_EXPL", "ITEM_NM"]
                    for f in fields:
                        match = re.search(rf'{f}["\>\]\s:]+([^"<\n]+)', content, re.IGNORECASE)
                        if match:
                            raw_name = self._clean_val(match.group(1))
                            if not self._is_garbage(raw_name):
                                # 도수 및 규격 추출
                                spec_match = re.search(r'SPEC["\>\]\s:]+([^"<\n]+)', content, re.IGNORECASE)
                                spec = self._clean_val(spec_match.group(1)) if spec_match else "N/A"
                                
                                # 도수만 따로 정밀 추출
                                power = "N/A"
                                p_match = re.search(r'([+-]?\d+\.\d{2})', f"{raw_name} {spec}")
                                if p_match: power = p_match.group(1)
                                
                                name = raw_name.replace(power, "").strip("- ").strip()
                                
                                print(f"✅ 최종 정보 획득 성공!")
                                print(f"  📦 제품명: {name}")
                                print(f"  💎 도수: {power}")
                                return {
                                    'name': name,
                                    'power': power,
                                    'manufacturer': "식약처 UDI 등록 제품",
                                    'gtin': target_id
                                }
        except Exception as e:
            print(f"  ⚠️ 2단계 접속 오류: {e}")

        print("\n❌ 모든 단계를 거쳤으나 유효한 제품 정보를 찾지 못했습니다.")
        return None

    def sync_with_local_db(self, api_data: Dict, local_data: Dict) -> Dict:
        synced = local_data.copy()
        if api_data:
            synced['name'] = api_data.get('name') or local_data.get('name')
            synced['power'] = api_data.get('power') or local_data.get('power')
        return synced
