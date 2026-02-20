import os
import requests
import re
from typing import Dict, Optional, Any
from dotenv import load_dotenv

load_dotenv()

class APIClient:
    """
    바코드 정보를 바탕으로 식약처(공공데이터포털) API를 호출하여 
    정확한 제품명과 도수 정보를 가져오는 클래스입니다.
    """

    def __init__(self):
        self.api_key = os.getenv("LENS_API_KEY", "").strip()
        self.base_url = "https://apis.data.go.kr/1471000"

    def fetch_product_info(self, gtin: str) -> Optional[Dict[str, Any]]:
        """GTIN(UDI-DI) 코드로 식약처 2단계 조회를 수행합니다."""
        if not gtin:
            return None

        print(f"\n--- 🚀 식약처 정보 조회 시작 (ID: {gtin}) ---")

        # 1단계: 기본 정보 확인
        content = self._call_api("MdeqStdCdUnityInfoService01", "getMdeqStdCdUnityInfoInq01", gtin)
        
        # 2단계: 상세 스펙 조회 (1단계 성공 시 시도)
        if content:
            print("  ✅ 제품 등록 확인됨. 상세 정보를 가져옵니다.")
            detail_content = self._call_api("MdvUdiInfoService", "getMdvUdiInfoInq01", gtin)
            content = detail_content if detail_content else content

        # 정보 추출
        info = self._extract_product_details(content) if content else None
        
        if info:
            print(f"  🎉 정보 획득: {info['name']} ({info['power']})")
            return {**info, 'manufacturer': "식약처 등록 제품", 'gtin': gtin}

        print("  ❌ 정보를 찾을 수 없습니다. 수동 입력이 필요합니다.")
        return None

    def _call_api(self, service: str, endpoint: str, gtin: str) -> Optional[str]:
        """지정한 API 엔드포인트에 요청을 보냅니다."""
        url = f"{self.base_url}/{service}/{endpoint}"
        params = {
            'serviceKey': self.api_key,
            'type': 'json',
            'pageNo': 1,
            'numOfRows': 1,
            'UDIDI_CD': gtin
        }
        
        try:
            print(f"  📡 {endpoint} 데이터 요청 중...")
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                text = response.text
                if '"totalCount":0' in text or '<totalCount>0' in text:
                    return None
                return text
            
            print(f"    ⚠️ 서버 응답 오류 ({response.status_code})")
        except Exception as e:
            print(f"    ⚠️ 연결 실패: {str(e)}")
            
        return None

    def _extract_product_details(self, content: str) -> Optional[Dict[str, str]]:
        """응답 텍스트에서 제품명과 도수를 정밀하게 추출합니다."""
        # 찾고자 하는 데이터 필드들
        fields = ["PRDT_ADD_EXPL", "PRDT_NM", "MODEL_NM", "ITEM_NM", "PRDT_NM_CONT"]
        
        for field in fields:
            match = re.search(rf'{field}["\>\]\s:]+([^"<\n]+)', content, re.IGNORECASE)
            if match:
                raw_text = self._clean_text(match.group(1))
                if not self._is_invalid_text(raw_text):
                    return self._parse_name_and_power(raw_text)
        return None

    def _clean_text(self, text: str) -> str:
        """텍스트에서 불필요한 기호를 제거합니다."""
        return text.strip().replace('"', '').replace('}', '').replace(',', '').replace(';', '')

    def _is_invalid_text(self, text: str) -> bool:
        """가져온 텍스트가 유효하지 않은 정보(쓰레기 값)인지 확인합니다."""
        if not text or len(text.strip()) < 2:
            return True
        invalids = ["null", "none", "nan", "평가되지", "undefined", "미등록", "미지정", "n/a"]
        return text.lower() in invalids

    def _parse_name_and_power(self, text: str) -> Dict[str, str]:
        """문자열에서 도수(-7.00 등)와 제품명을 분리합니다."""
        power_match = re.search(r'([+-]?\d+\.\d{2})', text)
        power = power_match.group(1) if power_match else "N/A"
        name = text.replace(power, "").strip("- ").strip()
        
        return {
            "name": name if name else "미지정 제품",
            "power": power
        }

    def sync_with_local_db(self, api_data: Dict, local_data: Dict) -> Dict:
        """API에서 가져온 정보로 현지 데이터를 업데이트합니다."""
        synced = local_data.copy()
        if api_data:
            synced.update({
                'name': api_data.get('name'),
                'power': api_data.get('power')
            })
        return synced
