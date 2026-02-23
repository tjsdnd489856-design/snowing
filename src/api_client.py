import os
import requests
import re
import sys
from typing import Dict, Optional, Any, List
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

# 엑셀 기능을 위한 pandas (설치되어 있지 않으면 None 처리)
try:
    import pandas as pd
except ImportError:
    pd = None

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
        if pd is None:
            sys.stderr.write("pandas 라이브러리가 없어 엑셀 기능을 사용할 수 없습니다.\n")
            return

        try:
            # pandas를 사용하여 엑셀 파일 읽기 (스타일 무시, 값만 읽음)
            # engine='openpyxl'을 명시적으로 지정하되, pandas가 내부적으로 오류를 잘 처리함
            # dtype={'바코드': str}: 바코드 열을 문자열로 읽도록 강제 (매우 중요!)
            # 하지만 컬럼 이름을 모르니 일단 다 읽고 처리해야 함.
            df = pd.read_excel(self.file_path, dtype=str)
            
            # 헤더 매핑 (대소문자 무시, 한글 지원)
            # 컬럼 이름의 공백 제거
            df.columns = [str(col).strip() for col in df.columns]
            col_map = {str(col).upper(): col for col in df.columns}
            
            # 필요한 열 이름 찾기
            col_gtin = col_map.get('GTIN') or col_map.get('바코드')
            col_name = col_map.get('NAME') or col_map.get('품명') or col_map.get('제품명')
            
            if not col_gtin:
                sys.stderr.write(f"엑셀 파일({self.file_path})에 '바코드' 또는 'GTIN' 열이 없습니다.\n")
                return

            # 데이터 로드
            count = 0
            for _, row in df.iterrows():
                gtin_raw = row[col_gtin]
                if pd.isna(gtin_raw) or str(gtin_raw).strip() == "":
                    continue
                
                # 바코드 문자열 변환 (소수점 제거 등)
                gtin = str(gtin_raw).strip()
                # 엑셀에서 숫자로 읽혀서 '880...0.0' 처럼 될 수 있음 -> 정수부만 취함
                if '.' in gtin:
                    try:
                        gtin = str(int(float(gtin)))
                    except: pass
                
                # 품명 읽기
                if col_name and not pd.isna(row[col_name]):
                    full_name = str(row[col_name]).strip()
                else:
                    full_name = "Unknown Product"
                
                name, power = self._parse_name_and_power(full_name)
                
                self.data_cache[gtin] = {
                    "name": name,
                    "power": power
                }
                count += 1
            
            print(f"[DEBUG] 엑셀 로드 완료 (pandas): {count}개의 데이터가 캐시되었습니다.")
                
        except Exception as e:
            sys.stderr.write(f"엑셀 파일 로드 실패 (pandas): {self.file_path} ({e})\n")

    def _parse_name_and_power(self, full_name: str) -> tuple[str, str]:
        """
        품명 문자열에서 도수를 추출합니다.
        예: "바이오피니티 -3.00" -> ("바이오피니티", "-3.00")
        예: "아큐브 오아시스 +1.25" -> ("아큐브 오아시스", "+1.25")
        """
        # 도수 패턴: + 또는 - 부호가 있거나 없으며, 숫자.숫자 형식 (예: -3.00, +1.25, 0.00)
        # 또는 단순 정수형 도수 (예: -3, +2)
        power_pattern = r'([+-]?\d+\.\d{2}|[+-]?\d+\.\d+|[+-]\d+)'
        
        match = re.search(power_pattern, full_name)
        if match:
            power = match.group(1)
            # 도수를 제외한 나머지 문자열을 제품명으로 사용
            name = full_name.replace(power, "").strip().strip("-_, ")
            return name, power
        
        return full_name, "N/A"

    def fetch(self, gtin: str) -> Optional[Dict[str, Any]]:
        # 1. 있는 그대로 검색 (14자리 또는 13자리)
        print(f"[DEBUG] 엑셀 검색 시도 (원본): {gtin}")
        data = self.data_cache.get(gtin)
        if data:
            print(f"[DEBUG] 엑셀 검색 성공 (원본): {data['name']}")
            return data
            
        # 2. 만약 입력된 바코드가 14자리이고 0으로 시작하면, 13자리로 변환해서 재검색
        # (엑셀에는 13자리로 저장되어 있을 가능성이 높음)
        if len(gtin) == 14 and gtin.startswith('0'):
            gtin_13 = gtin[1:]
            print(f"[DEBUG] 엑셀 재검색 시도 (13자리): {gtin_13}")
            data = self.data_cache.get(gtin_13)
            if data:
                print(f"[DEBUG] 엑셀 검색 성공 (13자리): {data['name']}")
                return data
            
        print("[DEBUG] 엑셀 검색 실패: 데이터 없음")
        return None

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
        # 기본값으로 'product_list.xlsx'도 확인하도록 수정
        excel_path = os.getenv("LENS_EXCEL_PATH", "product_list.xlsx").strip()
        if excel_path and os.path.exists(excel_path):
            print(f"[DEBUG] 엑셀 파일 로드 시도: {excel_path}")
            self.providers.append(ExcelProvider(excel_path))
        else:
            print(f"[DEBUG] 엑셀 파일을 찾을 수 없음: {excel_path}")
        
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
