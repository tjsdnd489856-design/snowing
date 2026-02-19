# 👓 콘택트렌즈 유통기한 관리 시스템 (PC 실행용)

이 프로그램은 파이썬(Python)으로 제작된 PC용 관리 도구입니다. 바코드 스캐너를 연결하여 렌즈의 유통기한을 효율적으로 관리할 수 있습니다.

## 🚀 로컬 PC에서 시작하기 (초보자용 가이드)

### 1. 필수 도구 설치
1. [Python](https://www.python.org/downloads/) 설치 (설치 시 'Add Python to PATH' 체크 필수!)
2. [Git](https://git-scm.com/downloads) 설치

### 2. 코드 다운로드 및 준비
컴퓨터의 터미널(CMD 또는 PowerShell)을 열고 아래 명령어를 순서대로 입력하세요.

```bash
# 1. 코드 복제
git clone https://github.com/tjsdnd489856-design/snowing.git

# 2. 폴더 이동
cd snowing

# 3. 필요한 도구 설치
pip install -r requirements.txt

# 4. 설정 파일 만들기
copy .env.example .env
```

### 3. 프로그램 실행
```bash
python -m src.main
```

## 🛠 주요 기능
- **바코드 스캔**: USB 바코드 스캐너를 찍으면 자동으로 제품명, 도수, 유통기한이 입력됩니다.
- **유통기한 알림**: 
  - [X] **빨간색**: 유통기한이 지난 제품 (즉시 폐기)
  - [!] **노란색**: 만료 30일 이내 제품
- **데이터 저장**: `products.sqlite3` 파일에 모든 정보가 안전하게 저장됩니다.

## 📁 파일 구조
- `src/`: 프로그램 실행 핵심 코드
- `requirements.txt`: 실행에 필요한 도구 목록
- `products.sqlite3`: 내 렌즈 데이터가 담긴 데이터베이스 파일
