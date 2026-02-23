import pytest
import os
from unittest.mock import patch, MagicMock
from src.api_client import APIClient, MFDSProvider

@pytest.fixture
def api_client():
    # 환경 변수가 없어도 테스트가 가능하도록 APIClient 생성 후 Provider를 수동으로 추가하거나
    # 환경 변수를 설정한 상태에서 생성해야 함.
    # 여기서는 생성 후 Provider를 주입하는 방식을 사용.
    client = APIClient()
    if not client.providers:
        client.providers.append(MFDSProvider("dummy_key"))
    return client

@patch('src.api_client.MFDSProvider.fetch')
def test_fetch_product_info_success(mock_fetch, api_client):
    """API 호출 성공 시나리오 테스트"""
    # 가짜 응답 데이터 설정
    mock_data = {"name": "Test Lens", "power": "-2.00"}
    mock_fetch.return_value = mock_data

    # 테스트 실행
    result = api_client.fetch_product_info("8801234567890")
    
    # 검증
    assert result is not None, "API 결과가 None입니다. Providers 설정이 올바른지 확인하세요."
    assert result['name'] == "Test Lens"
    assert result['power'] == "-2.00"
    assert result['gtin'] == "8801234567890"
    # source는 provider 클래스 이름이므로 'MFDSProvider'가 되어야 함
    assert result['source'] == "MFDSProvider"

@patch('src.api_client.MFDSProvider.fetch')
def test_fetch_product_info_failure(mock_fetch, api_client):
    """API 호출 실패 시나리오 테스트 (데이터 없음)"""
    mock_fetch.return_value = None

    result = api_client.fetch_product_info("9999999999999")
    
    assert result is None

def test_sync_with_local_db(api_client):
    """데이터 동기화 정책 테스트"""
    # API에서 가져온 데이터 (이름과 도수가 있음)
    api_data = {"name": "New Name", "power": "-1.00"}
    
    # 로컬 DB에 있던 기존 데이터
    local_data = {
        "udi": "test_udi",
        "name": "Old Name", 
        "power": "-1.00", 
        "source": "manual",
        "qty": 5
    }
    
    # 동기화 실행
    synced = api_client.sync_with_local_db(api_data, local_data)
    
    # 검증: API 데이터로 업데이트되었는지 확인
    assert synced['name'] == "New Name"
    # 검증: 로컬 데이터(수량 등)는 유지되었는지 확인
    assert synced['qty'] == 5
    assert synced['udi'] == "test_udi"

def test_sync_with_local_db_no_api_data(api_client):
    """API 데이터가 없을 때 로컬 데이터 유지 테스트"""
    api_data = None
    local_data = {"name": "Old Name", "power": "-1.00", "source": "manual"}
    
    synced = api_client.sync_with_local_db(api_data, local_data)
    
    assert synced['name'] == "Old Name"
