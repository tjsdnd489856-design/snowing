import os
import requests
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from typing import Dict, Optional, Any, List
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

load_dotenv()

class BaseProvider:
    def fetch(self, gtin: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError()

class ExcelProvider(BaseProvider):
    """[엑셀 파일 공급자] 로컬 엑셀 파일에서 제품 정보를 검색합니다. (Raw XML 파싱 사용)"""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.data_cache = {} # 성능을 위해 한 번 읽은 데이터는 메모리에 캐싱
        self._load_excel_raw()

    def _load_excel_raw(self):
        """
        openpyxl/pandas를 사용하지 않고 ZIP/XML을 직접 파싱하여 
        'fillID' 같은 스타일 오류를 원천 차단합니다.
        """
        try:
            with zipfile.ZipFile(self.file_path, 'r') as z:
                # 1. 공유 문자열(Shared Strings) 로드
                shared_strings = []
                if 'xl/sharedStrings.xml' in z.namelist():
                    with z.open('xl/sharedStrings.xml') as f:
                        for event, elem in ET.iterparse(f):
                            if elem.tag.endswith('t'):
                                shared_strings.append(elem.text or "")
                            elif elem.tag.endswith('si'):
                                pass

                # 2. 첫 번째 시트(sheet1) 데이터 로드
                sheet_path = 'xl/worksheets/sheet1.xml'
                if sheet_path not in z.namelist():
                    sys.stderr.write(f"엑셀 파일 구조를 인식할 수 없습니다 (sheet1.xml 없음): {self.file_path}\n")
                    return

                # 데이터 파싱
                rows = []
                with z.open(sheet_path) as f:
                    tree = ET.parse(f)
                    root = tree.getroot()
                    ns = {'ns': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                    
                    for row in root.findall('.//ns:row', ns):
                        row_vals = []
                        for c in row.findall('ns:c', ns):
                            val = ""
                            cell_type = c.get('t')
                            v_tag = c.find('ns:v', ns)
                            
                            if v_tag is not None:
                                raw_val = v_tag.text
                                if cell_type == 's': 
                                    try:
                                        idx = int(raw_val)
                                        if idx < len(shared_strings):
                                            val = shared_strings[idx]
                                    except: pass
                                else: 
                                    val = raw_val
                            
                            row_vals.append(val)
                        rows.append(row_vals)

            if not rows:
                return

            # 3. 헤더 매핑 및 데이터 캐싱
            header = [str(h).strip() for h in rows[0]] 
            
            col_map = {h.upper(): i for i, h in enumerate(header) if h}
            
            idx_gtin = col_map.get('GTIN') or col_map.get('바코드')
            idx_name = col_map.get('NAME') or col_map.get('품명') or col_map.get('제품명')
            
            if idx_gtin is None:
                return

            count = 0
            for row in rows[1:]:
                if idx_gtin >= len(row): continue
                
                gtin_raw = row[idx_gtin]
                if not gtin_raw: continue
                
                gtin = str(gtin_raw).strip()
                if '.' in gtin:
                    try:
                        gtin = str(int(float(gtin)))
                    except: pass
                
                # 지수 표현 처리
                if 'E+' in gtin:
                    try:
                        gtin = str(int(float(gtin)))
                    except: pass
                
                name_raw = row[idx_name] if idx_name is not None and idx_name < len(row) else ""
                full_name = str(name_raw).strip() if name_raw else "Unknown Product"
                
                name, power = self._parse_name_and_power(full_name)
                
                self.data_cache[gtin] = {
                    "name": name,
                    "power": power
                }
                count += 1
            
            print(f"[INFO] 엑셀 데이터 {count}건 로드 완료")
                
        except Exception as e:
            sys.stderr.write(f"엑셀 파일 로드 실패: {e}\n")

    def _parse_name_and_power(self, full_name: str) -> tuple[str, str]:
        power_pattern = r'([+-]?\d+\.\d{2}|[+-]?\d+\.\d+|[+-]\d+)'
        match = re.search(power_pattern, full_name)
        if match:
            power = match.group(1)
            name = full_name.replace(power, "").strip().strip("-_, ")
            return name, power
        return full_name, "N/A"

    def fetch(self, gtin: str) -> Optional[Dict[str, Any]]:
        # 1. 있는 그대로 검색
        data = self.data_cache.get(gtin)
        if data:
            return data
            
        # 2. 13자리 검색
        if len(gtin) == 14 and gtin.startswith('0'):
            gtin_13 = gtin[1:]
            data = self.data_cache.get(gtin_13)
            if data:
                return data
            
        return None

class MFDSProvider(BaseProvider):
    """[식약처 API 공급자] 병렬 호출을 사용하여 속도를 극대화합니다."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://apis.data.go.kr/1471000"

    def fetch(self, gtin: str) -> Optional[Dict[str, Any]]:
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
        # URL 인코딩 문제 방지를 위해 requests가 처리하도록 함 (ServiceKey는 이미 인코딩된 경우 주의)
        # 보통 공공데이터포털 키는 이미 인코딩되어 있으므로, params에 넣지 않고 URL에 직접 붙이거나
        # requests가 다시 인코딩하지 않도록 주의해야 함.
        # 여기서는 params에 넣어서 테스트해보고, 안 되면 URL에 직접 붙이는 방식으로 수정해야 할 수 있음.
        
        # 키에 '%'가 포함되어 있지 않다면(Decoding된 키라면) params 사용 OK.
        # 키에 '%'가 포함되어 있다면(Encoding된 키라면) requests가 또 인코딩하면 안 됨.
        
        params = {'serviceKey': self.api_key, 'type': 'json', 'pageNo': 1, 'numOfRows': 1, 'UDIDI_CD': gtin}
        
        # requests는 params의 값을 자동으로 인코딩함.
        # 만약 self.api_key가 이미 인코딩된 키라면 이중 인코딩 문제가 발생할 수 있음.
        # 공공데이터포털 일반 인증키(Decoding)를 사용하는 것이 안전함.
        
        try:
            resp = requests.get(url, params=params, timeout=5)
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
        
        # 1. 엑셀 파일 우선 검색
        excel_path = os.getenv("LENS_EXCEL_PATH", "product_list.xlsx").strip()
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
