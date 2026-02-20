import os
import requests
import re
from typing import Dict, Optional, Any, List
from dotenv import load_dotenv

load_dotenv()

class BaseProvider:
    """모든 데이터 공급자(API/DB)가 상속받아야 할 기본 규칙입니다."""
    def fetch(self, gtin: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError("각 공급자는 fetch 메서드를 구현해야 합니다.")

class MFDSProvider(BaseProvider):
    """[식약처 API 공급자] 기존 식약처 API를 통한 조회를 담당합니다."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://apis.data.go.kr/1471000"

    def fetch(self, gtin: str) -> Optional[Dict[str, Any]]:
        print(f"  🔍 [식약처] 데이터 요청 중... (ID: {gtin})")
        # 1단계: 기본 정보 확인
        content = self._call("MdeqStdCdUnityInfoService01", "getMdeqStdCdUnityInfoInq01", gtin)
        if not content: return None

        # 2단계: 상세 스펙 조회
        detail = self._call("MdvUdiInfoService", "getMdvUdiInfoInq01", gtin)
        final_content = detail if detail else content

        return self._extract(final_content)

    def _call(self, service: str, endpoint: str, gtin: str) -> Optional[str]:
        url = f"{self.base_url}/{service}/{endpoint}"
        params = {'serviceKey': self.api_key, 'type': 'json', 'pageNo': 1, 'numOfRows': 1, 'UDIDI_CD': gtin}
        try:
            resp = requests.get(url, params=params, timeout=10)
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
                return {"name": name or "식약처 제품", "power": power}
        return None

class APIClient:
    """여러 데이터 공급자를 관리하고 정보를 통합적으로 조회하는 매니저 클래스입니다."""

    def __init__(self):
        self.providers: List[BaseProvider] = []
        
        # 1. 기존 식약처 API 공급자 등록
        mfds_key = os.getenv("LENS_API_KEY", "").strip()
        if mfds_key:
            self.providers.append(MFDSProvider(mfds_key))
        
        # [준비 완료] 나중에 새로운 API/DB 연동 시 아래처럼 추가만 하면 됩니다.
        # if os.getenv("NEW_DB_KEY"):
        #     self.providers.append(NewDBProvider(os.getenv("NEW_DB_KEY")))

    def fetch_product_info(self, gtin: str) -> Optional[Dict[str, Any]]:
        """등록된 모든 공급자를 순회하며 정보를 찾아옵니다."""
        if not gtin: return None
        
        print(f"\n--- 🚀 통합 정보 검색 시작 (ID: {gtin}) ---")
        
        for provider in self.providers:
            info = provider.fetch(gtin)
            if info:
                print(f"  🎉 정보를 찾았습니다: {info['name']} ({info['power']})")
                return {**info, 'gtin': gtin, 'source': provider.__class__.__name__}
        
        print("  ❌ 모든 공급자로부터 정보를 찾지 못했습니다.")
        return None

    def sync_with_local_db(self, api_data: Dict, local_data: Dict) -> Dict:
        """가져온 정보로 로컬 데이터를 동기화합니다."""
        synced = local_data.copy()
        if api_data:
            synced.update({'name': api_data.get('name'), 'power': api_data.get('power')})
        return synced
