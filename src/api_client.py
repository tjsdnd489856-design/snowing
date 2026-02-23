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
                # 엑셀은 중복되는 문자열을 별도 파일에 저장하고 인덱스로 참조합니다.
                shared_strings = []
                if 'xl/sharedStrings.xml' in z.namelist():
                    with z.open('xl/sharedStrings.xml') as f:
                        # XML 파싱 (iterparse를 사용하여 메모리 효율성 높임)
                        for event, elem in ET.iterparse(f):
                            if elem.tag.endswith('t'): # <t> 태그 (텍스트)
                                shared_strings.append(elem.text or "")
                            elif elem.tag.endswith('si'): # <si> 태그 (문자열 항목)
                                # 하나의 si 안에는 하나의 t만 있다고 가정 (간단한 처리)
                                pass

                # 2. 첫 번째 시트(sheet1) 데이터 로드
                # 보통 데이터는 sheet1에 있습니다.
                sheet_path = 'xl/worksheets/sheet1.xml'
                if sheet_path not in z.namelist():
                    # sheet1.xml이 없으면 xl/workbook.xml을 뒤져야 하지만
                    # 대부분의 간단한 엑셀은 sheet1.xml에 데이터가 있습니다.
                    sys.stderr.write(f"엑셀 파일 구조를 인식할 수 없습니다 (sheet1.xml 없음): {self.file_path}\n")
                    return

                # 데이터 파싱
                rows = []
                with z.open(sheet_path) as f:
                    tree = ET.parse(f)
                    root = tree.getroot()
                    # 네임스페이스 무시하고 태그 이름으로만 찾기 위해 정규식이나 endswith 사용이 편하지만
                    # 여기서는 간단히 namespace를 정의합니다.
                    ns = {'ns': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                    
                    for row in root.findall('.//ns:row', ns):
                        row_vals = []
                        # 셀(c) 순회
                        for c in row.findall('ns:c', ns):
                            # r 속성(예: "A1")을 보고 컬럼 인덱스를 정확히 맞춰야 하지만
                            # 여기서는 순서대로 데이터가 있다고 가정하고 append 합니다.
                            # (빈 셀 처리가 완벽하지 않을 수 있지만, 일반적인 리스트 파일에는 충분함)
                            
                            val = ""
                            cell_type = c.get('t')
                            v_tag = c.find('ns:v', ns)
                            
                            if v_tag is not None:
                                raw_val = v_tag.text
                                if cell_type == 's': # Shared String
                                    try:
                                        idx = int(raw_val)
                                        if idx < len(shared_strings):
                                            val = shared_strings[idx]
                                    except: pass
                                else: # Number or other
                                    val = raw_val
                            
                            row_vals.append(val)
                        rows.append(row_vals)

            if not rows:
                sys.stderr.write(f"엑셀 파일에 데이터가 없습니다: {self.file_path}\n")
                return

            # 3. 헤더 매핑 및 데이터 캐싱
            header = [str(h).strip() for h in rows[0]] # 첫 번째 행을 헤더로
            
            # 헤더 매핑
            col_map = {h.upper(): i for i, h in enumerate(header) if h}
            
            idx_gtin = col_map.get('GTIN') or col_map.get('바코드')
            idx_name = col_map.get('NAME') or col_map.get('품명') or col_map.get('제품명')
            
            if idx_gtin is None:
                sys.stderr.write(f"엑셀 파일({self.file_path})에 '바코드' 또는 'GTIN' 열이 없습니다. (인식된 헤더: {header})\n")
                return

            # 데이터 로드 (두 번째 줄부터)
            count = 0
            for row in rows[1:]:
                # 인덱스 범위 체크
                if idx_gtin >= len(row): continue
                
                gtin_raw = row[idx_gtin]
                if not gtin_raw: continue
                
                # 바코드 전처리
                gtin = str(gtin_raw).strip()
                # 소수점 제거 (엑셀 숫자형 처리)
                if '.' in gtin:
                    try:
                        gtin = str(int(float(gtin)))
                    except: pass
                
                # 품명 전처리
                name_raw = row[idx_name] if idx_name is not None and idx_name < len(row) else ""
                full_name = str(name_raw).strip() if name_raw else "Unknown Product"
                
                name, power = self._parse_name_and_power(full_name)
                
                self.data_cache[gtin] = {
                    "name": name,
                    "power": power
                }
                count += 1
            
            print(f"[DEBUG] 엑셀 로드 완료 (Raw XML): {count}개의 데이터가 캐시되었습니다.")
                
        except Exception as e:
            sys.stderr.write(f"엑셀 파일 로드 실패 (Raw XML): {self.file_path} ({e})\n")
            import traceback
            traceback.print_exc()

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
