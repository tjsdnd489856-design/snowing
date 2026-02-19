import os
import requests
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Optional, Any, List
from dotenv import load_dotenv

load_dotenv()

class APIClient:
    """병렬 요청을 통해 파싱 속도를 극대화한 클라이언트"""

    def __init__(self):
        self.api_key = os.getenv("LENS_API_KEY", "").strip()
        base = os.getenv("LENS_API_BASE_URL", "").split('/Mdeq')[0]
        self.service_url = f"{base}/MdeqStdCdUnityInfoService01"

    def _is_garbage_name(self, name: str) -> bool:
        if not name: return True
        clean_name = name.strip()
        if len(clean_name) < 2: return True
        garbage_keywords = ["null", "none", "평가되지", "undefined", "nan", "n/a", "미지정", "미등록"]
        lower_name = clean_name.lower()
        return any(kw in lower_name for kw in garbage_keywords) or not re.search(r'[a-zA-Z가-힣0-9]', clean_name)

    def _extract_from_raw(self, content: str) -> Optional[Dict[str, str]]:
        match = re.search(r'PRDT_ADD_EXPL["\>\]\s:]+([^"<\n]+)', content, re.IGNORECASE)
        model_match = re.search(r'MODEL_NM["\>\]\s:]+([^"<\n]+)', content, re.IGNORECASE)
        raw_text = (match.group(1) if match else (model_match.group(1) if model_match else "")).strip()
        
        if not raw_text or self._is_garbage_name(raw_text):
            return None

        power_match = re.search(r'([+-]?\d+\.\d{2})', raw_text)
        power = power_match.group(1) if power_match else "N/A"
        name = text = raw_text.replace(power, "")
        name = re.sub(r'\(.*?\)', '', name).strip("- ").strip()
        
        return {"name": name, "power": power} if not self._is_garbage_name(name) else None

    def _make_request(self, url: str, p_name: str, target_id: str) -> Optional[Dict]:
        """단일 API 요청을 수행하는 워커 함수"""
        full_url = f"{url}?serviceKey={self.api_key}&type=json&pageNo=1&numOfRows=1&{p_name}={target_id}"
        try:
            response = requests.get(full_url, timeout=5)
            if response.status_code == 200:
                content = response.text
                if '"totalCount":0' in content or '<totalCount>0' in content:
                    return None
                
                info = self._extract_from_raw(content)
                if info:
                    return {
                        'name': info['name'],
                        'power': info['power'],
                        'manufacturer': "정부 DB 등록 제품",
                        'gtin': target_id
                    }
        except Exception:
            pass
        return None

    def fetch_product_info(self, identifier: str) -> Optional[Dict]:
        """모든 서랍을 병렬로 동시에 뒤져서 가장 빨리 찾은 결과를 반환합니다."""
        if not identifier: return None
        
        target_ids = list(set([identifier.zfill(14), identifier[-13:], identifier]))
        endpoints = [f"{self.service_url}/getMdeqStdCdUnityInfoInq01", f"{self.service_url}/getMdeqStdCdInq01"]
        params = ["UDIDI_CD", "udi_code", "gtin_code"]

        # 실행할 모든 작업 조합 생성
        tasks = []
        for endpoint in endpoints:
            for tid in target_ids:
                for p in params:
                    tasks.append((endpoint, p, tid))

        # 병렬 실행 (최대 10개의 스레드 동시 가동)
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_task = {executor.submit(self._make_request, *task): task for task in tasks}
            
            for future in as_completed(future_to_task):
                result = future.result()
                if result:
                    # 유효한 결과를 찾으면 즉시 반환 (나머지 스레드 결과는 무시됨)
                    print(f"⚡ 병렬 검색 성공: {result['name']}")
                    return result

        print("📭 모든 경로를 동시에 탐색했으나 정보를 찾지 못했습니다.")
        return None

    def sync_with_local_db(self, api_data: Dict, local_data: Dict) -> Dict:
        synced = local_data.copy()
        if api_data:
            synced['name'] = api_data.get('name') or local_data.get('name')
            synced['power'] = api_data.get('power') or local_data.get('power')
        return synced
