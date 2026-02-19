import os
import requests
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Optional, Any, List
from dotenv import load_dotenv

load_dotenv()

class APIClient:
    """모든 단계의 진행 과정을 투명하게 출력하는 정밀 진단 클라이언트"""

    def __init__(self):
        self.api_key = os.getenv("LENS_API_KEY", "").strip()
        self.base_url = "https://apis.data.go.kr/1471000"

    def _clean_val(self, val: Any) -> str:
        if not val or str(val).lower() in ["null", "none", "nan", "평가되지", "평가되지 않음"]:
            return ""
        return str(val).strip().replace('"', '').replace('}', '').replace(',', '')

    def _extract_from_content(self, content: str) -> Optional[Dict[str, str]]:
        """어떤 형식(JSON/XML)에서든 제품명과 도수를 추출하는 정밀 파서"""
        fields = ["PRDT_ADD_EXPL", "MODEL_NM", "PRDT_NM", "ITEM_NM", "MDEQ_PRDLST_NM"]
        
        for field in fields:
            match = re.search(rf'{field}["\>\]\s:]+([^"<\n]+)', content, re.IGNORECASE)
            if match:
                text = self._clean_val(match.group(1))
                if len(text) > 1:
                    # 도수 추출 시도
                    power_match = re.search(r'([+-]?\d+\.\d{2})', text)
                    power = power_match.group(1) if power_match else "N/A"
                    # 이름 정리
                    name = text.replace(power, "")
                    name = re.sub(r'\(.*?\)', '', name).strip("- ").strip()
                    if len(name) >= 2:
                        return {"name": name, "power": power, "field": field}
        return None

    def _try_request(self, service: str, endpoint: str, param: str, val: str) -> Optional[str]:
        """단일 API 요청을 수행하고 상세 과정을 출력합니다."""
        url = f"{self.base_url}/{service}/{endpoint}"
        full_url = f"{url}?serviceKey={self.api_key}&type=json&pageNo=1&numOfRows=1&{param}={val}"
        
        # API 키 일부만 노출하여 보안 유지
        key_hint = self.api_key[:5] + "..." if self.api_key else "None"
        print(f"  [요청] {service} > {endpoint} ({param}={val})")
        
        try:
            response = requests.get(full_url, timeout=7)
            status = response.status_code
            
            if status == 200:
                content = response.text
                # 결과 0건 체크
                if '"totalCount":0' in content or '<totalCount>0' in content:
                    print(f"  [결과] {endpoint}: 검색 결과 0건 (서버에 데이터 없음)")
                    return None
                print(f"  [결과] {endpoint}: 데이터 수신 성공 (200 OK)")
                return content
            elif status == 401:
                print(f"  [에러] {endpoint}: 인증 실패 (401) - API 키가 만료되었거나 승인 대기 중입니다.")
            elif status == 404:
                print(f"  [에러] {endpoint}: 주소를 찾을 수 없음 (404)")
            else:
                print(f"  [에러] {endpoint}: 서버 응답 오류 ({status})")
        except Exception as e:
            print(f"  [에러] {endpoint}: 연결 실패 ({str(e)})")
        return None

    def fetch_product_info(self, identifier: str) -> Optional[Dict]:
        """모든 과정을 화면에 출력하며 정보를 추적합니다."""
        if not identifier: return None
        target_id = identifier.zfill(14)
        print(f"\n--- 🛰️ 식약처 DB 정밀 추적 시작 (ID: {target_id}) ---")

        # --- 1단계: 식별자 확보 (MsUdedi) ---
        print(f"\n[1단계] 고유 식별자(UDI-DI) 확보 시도")
        list_content = self._try_request("MsUdediInfoService", "getUdediList", "UDIDI_CD", target_id)
        
        udidi_cd = None
        if list_content:
            match = re.search(r'UDIDI_CD["\>\]\s:]+([^"<\n]+)', list_content, re.IGNORECASE)
            if match:
                udidi_cd = self._clean_val(match.group(1))
                print(f"  🎯 식별자 발견: {udidi_cd}")
            else:
                print("  ⚠️ 데이터는 받았으나 UDIDI_CD 필드를 추출하지 못했습니다.")

        final_di = udidi_cd if udidi_cd else target_id
        if not udidi_cd:
            print(f"  ℹ️ 식별자를 못 찾아 입력값({target_id})으로 2단계를 진행합니다.")

        # --- 2단계: 상세 정보 병렬 조회 ---
        print(f"\n[2단계] 상세 정보 금고 동시 조회 시작")
        tasks = [
            ("MsUdediInfoService", "getUdediInfo", "UDIDI_CD"),
            ("MdeqStdCdUnityInfoService01", "getMdeqStdCdUnityInfoInq01", "UDIDI_CD"),
            ("MdeqStdCdUnityInfoService01", "getMdeqStdCdUnityInfoInq01", "udi_code"),
            ("MdvUdiInfoService", "getMdvUdiInfoInq01", "UDIDI_CD")
        ]

        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_task = {executor.submit(self._try_request, *task, final_di): task for task in tasks}
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                content = future.result()
                if content:
                    info = self._extract_from_content(content)
                    if info:
                        print(f"\n[성공] '{info['field']}' 필드에서 최종 정보 추출 완료!")
                        print(f"  📦 제품명: {info['name']}")
                        print(f"  💎 도수: {info['power']}")
                        print(f"--- 🛰️ 정밀 추적 종료 ---\n")
                        return {
                            'name': info['name'],
                            'power': info['power'],
                            'manufacturer': "식약처 등록 제품",
                            'gtin': final_di
                        }
                    else:
                        print(f"  ⚠️ {task[1]}: 데이터를 받았으나 유효한 제품명/도수 파싱에 실패했습니다.")

        print(f"\n[실패] 모든 서랍을 뒤졌으나 정보를 찾지 못했습니다.")
        print(f"--- 🛰️ 정밀 추적 종료 ---\n")
        return None

    def sync_with_local_db(self, api_data: Dict, local_data: Dict) -> Dict:
        synced = local_data.copy()
        if api_data:
            synced['name'] = api_data.get('name') or local_data.get('name')
            synced['power'] = api_data.get('power') or local_data.get('power')
        return synced
