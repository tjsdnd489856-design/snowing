import os
import requests
import re
import sys
from typing import Dict, Optional, Any, List
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

# 엑셀 기능을 위한 openpyxl (설치되어 있지 않으면 None 처리)
try:
    from openpyxl import load_workbook
except ImportError:
    load_workbook = None

load_dotenv()

class BaseProvider:
    def fetch(self, gtin: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError()

class ExcelProvider(BaseProvider):
    """[엑셀 파일 공급자] 로컬 엑셀 파일에서 제품 정보를 검색합니다."""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.data_cache = {} # 성능을 위해 한 번 읽은 데이터는 메모리에 캐싱
        self._load_excel()

    def _load_excel(self):
        if not load_workbook:
            sys.stderr.write("openpyxl 라이브러리가 없어 엑셀 기능을 사용할 수 없습니다.\n")
            return

        try:
            wb = load_workbook(self.file_path, data_only=True)
            ws = wb.active
            
            # 헤더 찾기 (GTIN, NAME, POWER 열의 인덱스 확인)
            header = [cell.value for cell in ws[1]]
            try:
                # 대소문자 무시하고 열 이름 찾기
                col_map = {str(h).upper(): i for i, h in enumerate(header) if h}
                idx_gtin = col_map.get('GTIN')
                idx_name = col_map.get('NAME') or col_map.get('PRODUCT_NAME')
                idx_power = col_map.get('POWER') or col_map.get('Diopter')
                
                if idx_gtin is None:
                    sys.stderr.write("엑셀 파일에 'GTIN' 열이 없습니다.\n")
                    return

                # 데이터 로드
                for row in ws.iter_rows(min_row=2, values_only=True):
                    gtin = str(row[idx_gtin]).strip()
                    if not gtin: continue
                    
                    name = row[idx_name] if idx_name is not None else "Unknown Product"
                    power = row[idx_power] if idx_power is not None else "N/A"
                    
                    self.data_cache[gtin] = {
                        "name": str(name).strip(),
                        "power": str(power).strip()
                    }
            except Exception as e:
                sys.stderr.write(f"엑셀 데이터 파싱 중 오류: {e}\n")
                
        except Exception as e:
            sys.stderr.write(f"엑셀 파일 로드 실패: {self.file_path} ({e})\n")

    def fetch(self, gtin: str) -> Optional[Dict[str, Any]]:
        return self.data_cache.get(gtin)

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
        
        # 1. 엑셀 파일 우선 검색 (LENS_EXCEL_PATH 환경변수 사용)
        excel_path = os.getenv("LENS_EXCEL_PATH", "").strip()
        if excel_path and os.path.exists(excel_path):
            self.providers.append(ExcelProvider(excel_path))
        
        # 2. 식약처 API 검색
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
