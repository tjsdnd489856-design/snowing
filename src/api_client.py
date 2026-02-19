import os
import requests
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Optional, Any, List
from dotenv import load_dotenv

load_dotenv()

class APIClient:
    """모든 식약처 서비스를 그물망처럼 뒤져 정보를 찾아내는 초정밀 클라이언트"""

    def __init__(self):
        self.api_key = os.getenv("LENS_API_KEY", "").strip()
        self.base_url = "https://apis.data.go.kr/1471000"

    def _is_garbage(self, text: str) -> bool:
        """가짜 데이터 필터링 (null, 평가되지 않음 등)"""
        if not text or len(text.strip()) < 2: return True
        garbage = ["null", "none", "nan", "평가되지", "undefined", "미등록", "미지정", "n/a", "해당사항"]
        lower_text = text.lower()
        return any(kw in lower_text for kw in garbage)

    def _clean_val(self, val: Any) -> str:
        if not val: return ""
        return str(val).strip().replace('"', '').replace('}', '').replace(',', '').replace(';', '')

    def _extract_best_info(self, content: str) -> Optional[Dict[str, str]]:
        """수많은 필드 중 가장 정확한 제품명과 도수를 우선순위에 따라 추출"""
        # 우선순위 필드 목록
        fields = ["PRDT_NM", "PRDT_ADD_EXPL", "MODEL_NM", "PRDT_NM_CONT", "ITEM_NM", "MDEQ_PRDLST_NM", "PRDLST_NM"]
        
        for f in fields:
            match = re.search(rf'{f}["\>\]\s:]+([^"<\n]+)', content, re.IGNORECASE)
            if match:
                raw = self._clean_val(match.group(1))
                if not self._is_garbage(raw):
                    # 도수(-7.00 등) 정밀 추출
                    p_match = re.search(r'([+-]?\d+\.\d{2})', raw)
                    power = p_match.group(1) if p_match else "N/A"
                    # 도수 정보가 포함되어 있다면 제거하여 순수 이름 확보
                    name = raw.replace(power, "").strip("- ").strip()
                    if not self._is_garbage(name):
                        return {"name": name, "power": power, "field": f}
        return None

    def _worker_request(self, service: str, endpoint: str, param: str, val: str) -> Optional[str]:
        """개별 경로에 대한 요청을 수행하고 진행 상황을 보고합니다."""
        url = f"{self.base_url}/{service}/{endpoint}"
        full_url = f"{url}?serviceKey={self.api_key}&type=json&pageNo=1&numOfRows=1&{param}={val}"
        
        try:
            response = requests.get(full_url, timeout=6)
            if response.status_code == 200:
                if '"totalCount":0' in response.text or '<totalCount>0' in response.text:
                    return None
                return response.text
        except Exception:
            pass
        return None

    def fetch_product_info(self, identifier: str) -> Optional[Dict]:
        if not identifier: return None
        # 탐색 대상 번호들 (원본, 14자리, 13자리)
        ids = list(set([identifier.zfill(14), identifier[-13:], identifier]))
        
        print(f"\n--- 📡 [그물망 추적 시작] 모든 서비스 전수 조사 ({identifier}) ---")

        # 탐색할 경로 조합 (서비스, 엔드포인트, 파라미터명)
        # 모든 업체/브랜드 케이스를 포괄하도록 설계
        tasks_config = [
            # 최신 UDI/EDI 서비스 계열
            ("MsUdediInfoService", "getUdediInfo", "UDIDI_CD"),
            ("MsUdediInfoService", "getUdediList", "UDIDI_CD"),
            # 통합정보 서비스 계열
            ("MdeqStdCdUnityInfoService01", "getMdeqStdCdUnityInfoInq01", "UDIDI_CD"),
            ("MdeqStdCdUnityInfoService01", "getMdeqStdCdUnityInfoInq01", "udi_code"),
            ("MdeqStdCdUnityInfoService01", "getMdeqStdCdInq01", "gtin_code"),
            # 구형/기타 UDI 서비스 계열
            ("MdvUdiInfoService", "getMdvUdiInfoInq01", "UDIDI_CD"),
            ("MdvUdiInfoService", "getMdvUdiInfoInq01", "udi")
        ]

        # 모든 조합 생성 (최대 수십 개)
        all_tasks = []
        for svc, end, param in tasks_config:
            for target_id in ids:
                all_tasks.append((svc, end, param, target_id))

        print(f"📊 [상태] 총 {len(all_tasks)}개의 잠재적 데이터 경로 탐색 중...")

        # 병렬 가속 실행 (최대 15개 스레드)
        with ThreadPoolExecutor(max_workers=15) as executor:
            future_to_info = {executor.submit(self._worker_request, *t): t for t in all_tasks}
            
            completed_count = 0
            for future in as_completed(future_to_info):
                completed_count += 1
                task = future_to_info[future]
                
                # 진행률 표시
                if completed_count % 5 == 0 or completed_count == len(all_tasks):
                    print(f"  ⏳ 진행률: {completed_count}/{len(all_tasks)} (현재: {task[1]})")
                
                content = future.result()
                if content:
                    info = self._extract_best_info(content)
                    if info:
                        print(f"\n✨ [성공] '{task[1]}' 서랍의 '{info['field']}' 필드에서 알맹이 발견!")
                        print(f"  📦 제품명: {info['name']}")
                        print(f"  💎 도수: {info['power']}")
                        print(f"--- 🏁 [추적 종료] ---\n")
                        return {
                            'name': info['name'],
                            'power': info['power'],
                            'manufacturer': "식약처 정식 등록 제품",
                            'gtin': task[3]
                        }

        print("\n📭 [실패] 모든 식약처 서비스를 뒤졌으나 유효한 정보를 찾지 못했습니다.")
        print(f"--- 🏁 [추적 종료] ---\n")
        return None

    def sync_with_local_db(self, api_data: Dict, local_data: Dict) -> Dict:
        synced = local_data.copy()
        if api_data:
            synced.update({
                'name': api_data.get('name') or local_data.get('name'),
                'power': api_data.get('power') or local_data.get('power')
            })
        return synced
