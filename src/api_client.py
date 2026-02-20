import os
import requests
import re
from typing import Dict, Optional, Any, List
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

load_dotenv()

class BaseProvider:
    def fetch(self, gtin: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError()

class MFDSProvider(BaseProvider):
    """[식약처 API 공급자] 병렬 호출을 사용하여 속도를 극대화합니다."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://apis.data.go.kr/1471000"

    def fetch(self, gtin: str) -> Optional[Dict[str, Any]]:
        # 두 개의 엔드포인트를 동시에 호출하여 속도 향상
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_base = executor.submit(self._call, "MdeqStdCdUnityInfoService01", "getMdeqStdCdUnityInfoInq01", gtin)
            future_detail = executor.submit(self._call, "MdvUdiInfoService", "getMdvUdiInfoInq01", gtin)
            
            content_base = future_base.result()
            content_detail = future_detail.result()

        final_content = content_detail if content_detail else content_base
        if not final_content:
            return None

        return self._extract(final_content)

    def _call(self, service: str, endpoint: str, gtin: str) -> Optional[str]:
        url = f"{self.base_url}/{service}/{endpoint}"
        params = {'serviceKey': self.api_key, 'type': 'json', 'pageNo': 1, 'numOfRows': 1, 'UDIDI_CD': gtin}
        try:
            resp = requests.get(url, params=params, timeout=5) # 타임아웃 단축
            if resp.status_code == 200 and '"totalCount":0' not in resp.text:
                return resp.text
        except: pass
        return None

    def _extract(self, content: str) -> Optional[Dict[str, Any]]:
        fields = ["PRDT_ADD_EXPL", "PRDT_NM", "MODEL_NM"]
        for f in fields:
            m = re.search(rf'{f}["\>\]\s:]+([^"<\n]+)', content, re.IGNORECASE)
            if m:
                raw = m.group(1).strip().strip('"} ,;')
                p_m = re.search(r'([+-]?\d+\.\d{2})', raw)
                power = p_m.group(1) if p_m else "N/A"
                name = raw.replace(power, "").strip("- ").strip()
                return {"name": name or "식약처 등록 제품", "power": power}
        return None

class APIClient:
    def __init__(self):
        self.providers: List[BaseProvider] = []
        mfds_key = os.getenv("LENS_API_KEY", "").strip()
        if mfds_key:
            self.providers.append(MFDSProvider(mfds_key))

    def fetch_product_info(self, gtin: str) -> Optional[Dict[str, Any]]:
        if not gtin: return None
        for provider in self.providers:
            info = provider.fetch(gtin)
            if info:
                return {**info, 'gtin': gtin, 'source': provider.__class__.__name__}
        return None

    def sync_with_local_db(self, api_data: Dict, local_data: Dict) -> Dict:
        synced = local_data.copy()
        if api_data:
            synced.update({'name': api_data.get('name'), 'power': api_data.get('power')})
        return synced
