# 콘택트렌즈 유통기한 관리 시스템

본 프로그램은 UDI 바코드를 기반으로 콘택트렌즈의 제품 정보와 유통기한을 효율적으로 관리할 수 있는 도구입니다.

## 주요 기능
- **UDI 파싱**: GS1-128 표준 바코드를 분석하여 GTIN, 유통기한, LOT 등을 자동 추출합니다.
- **다양한 입력 지원**: USB 바코드 스캐너, 이미지 파일, 카메라(확장 가능) 입력을 지원합니다.
- **외부 API 연동**: 제품 정보가 부족할 경우 외부 API를 통해 메타데이터를 보완하며, 캐싱 및 재시도 로직을 포함합니다.
- **유통기한 관리**: 만료 30일 이내 제품(노란색) 및 만료 제품(빨간색)을 시각적으로 강조합니다.
- **데이터베이스**: SQLite를 사용하여 모든 데이터를 영구 저장합니다.

## 설치 및 실행 방법

### 1. 환경 설정
```bash
# 의존성 설치
pip install -r requirements.txt

# 환경 변수 설정
cp .env.example .env
# .env 파일을 열어 실제 API 키를 입력하세요.
```

### 2. 실행
```bash
python -m src.main
```

### 3. 테스트 실행
```bash
pytest tests/
```

## 외부 API 스펙 예시

### Request (GET)
`HTTPS https://api.example.com/v1/products/{gtin}`
- **Headers**: `Authorization: Bearer {API_KEY}`

### Response (JSON)
```json
{
  "gtin": "08801234567890",
  "name": "아큐브 모이스트 원데이",
  "power": "-3.25",
  "manufacturer": "Johnson & Johnson"
}
```

## 실행 예시 (Console)
1. 메인 메뉴에서 `1`을 선택합니다.
2. 스캐너로 바코드를 찍거나 이미지 경로를 입력합니다. (예: `(01)08801234567890(17)261231(10)LOT123`)
3. 시스템이 정보를 분석하여 DB에 저장하고 성공 메시지를 띄웁니다.
4. `3`번 메뉴를 통해 유통기한 임박 항목을 확인합니다.

## 디렉토리 구조
- `src/`: 소스 코드 (db, parser, api, ui, main)
- `tests/`: 유닛 테스트
- `products.sqlite3`: 로컬 데이터베이스 파일 (실행 시 생성)
