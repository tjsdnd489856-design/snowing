import os
import requests
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Optional, Any, List
from dotenv import load_dotenv

load_dotenv()

class APIClient:
    """기존 서비스와 새로운 UDI/EDI 서비스를 통합하여 검색하는 병렬 클라이언트"""

    def __init__(self):
        self.api_key = os.getenv("LENS_API_KEY", "").strip()
        # 공공데이터포털 기본 베이스 주소
        self.base_url = "https://apis.data.go.kr/1471000"
        
        # 통합 검색할 서비스 및 엔드포인트 목록
        self.search_configs = [
            # 1. 의료기기 표준코드 통합정보 서비스 (기존)
            {"service": "MdeqStdCdUnityInfoService01", "endpoints": ["getMdeqStdCdUnityInfoInq01", "getMdeqStdCdInq01"]},
            # 2. 의료기기 UDI/EDI 정보 조회 서비스 (신규)
            {"service": "MdvUdiInfoService", "endpoints": ["getMdvUdiInfoInq01"]}
        ]

    def _is_garbage_name(self, name: str) -> bool:
        if not name: return True
        clean_name = name.strip()
        if len(clean_name) < 2: return True
        garbage_keywords = ["null", "none", "평가되지", "undefined", "nan", "n/a", "미지정", "미등록"]
        lower_name = clean_name.lower()
        return any(kw in lower_name for kw in garbage_keywords) or not re.search(r'[a-zA-Z가-힣0-9]', clean_name)

    def _extract_from_raw(self, content: str) -> Optional[Dict[str, str]]:
        """텍스트 뭉치에서 제품명과 도수를 추출합니다."""
        # 1. PRDT_ADD_EXPL(상세설명), MODEL_NM(모델명), ITEM_NM(품목명) 순서로 검색
        fields = ["PRDT_ADD_EXPL", "MODEL_NM", "ITEM_NM", "MDEQ_PRDLST_NM"]
        raw_text = None
        
        for field in fields:
            match = re.search(rf'{field}["\>\]\s:]+([^"<\n]+)', content, re.IGNORECASE)
            if match:
                val = match.group(1).strip()
                if not self._is_garbage_name(val):
                    raw_text = val
                    break
        
        if not raw_text: return None

        # 도수 추출 (-7.00, +1.50 등)
        power_match = re.search(r'([+-]?\d+\.\d{2})', raw_text)
        power = power_match.group(1) if power_match else "N/A"
        
        # 이름 정리
        name = raw_text.replace(power, "")
        name = re.sub(r'\(.*?\)', '', name).strip("- ").strip()
        
        return {"name": name, "power": power} if not self._is_garbage_name(name) else None

    def _make_request(self, service: str, endpoint: str, p_name: str, target_id: str) -> Optional[Dict]:
        """개별 API 요청 워커"""
        url = f"{self.base_url}/{service}/{endpoint}"
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
                        'manufacturer': "식약처 등록 제품",
                        'gtin': target_id,
                        'source_service': service
                    }
        except Exception:
            pass
        return None

    def fetch_product_info(self, identifier: str) -> Optional[Dict]:
        """모든 식약처 서비스를 동시에 뒤져서 정보를 가져옵니다."""
        if not identifier: return None
        
        target_ids = list(set([identifier.zfill(14), identifier[-13:], identifier]))
        params = ["UDIDI_CD", "udi_code", "gtin_code"]

        tasks = []
        for config in self.search_configs:
            for endpoint in config["endpoints"]:
                for tid in target_ids:
                    for p in params:
                        tasks.append((config["service"], endpoint, p, tid))

        # 병렬 실행 (최대 15개 스레드)
        with ThreadPoolExecutor(max_workers=15) as executor:
            future_to_task = {executor.submit(self._make_request, *task): task for task in tasks}
            
            for future in as_completed(future_to_task):
                result = future.result()
                if result:
                    print(f"⚡ [{result['source_service']}] 검색 성공: {result['name']}")
                    return result

        print("📭 모든 식약처 서비스를 조회했으나 유효한 정보를 찾지 못했습니다.")
        return None

    def sync_with_local_db(self, api_data: Dict, local_data: Dict) -> Dict:
        synced = local_data.copy()
        if api_data:
            synced['name'] = api_data.get('name') or local_data.get('name')
            synced['power'] = api_data.get('power') or local_data.get('power')
        return synced
