import pytest
from unittest.mock import patch, MagicMock
from src.api_client import APIClient

@pytest.fixture
def api_client():
    return APIClient()

def test_cache_logic(api_client):
    """캐시 저장 및 불러오기 테스트"""
    gtin = "8801234567890"
    data = {"name": "Test Lens", "power": "-2.00"}
    
    api_client._save_to_cache(gtin, data)
    cached = api_client._get_from_cache(gtin)
    
    assert cached == data
    assert gtin in api_client.cache

@patch('requests.get')
def test_fetch_product_info_success(mock_get, api_client):
    """API 호출 성공 시나리오 테스트"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"name": "Biofinity", "power": "-3.50"}
    mock_get.return_value = mock_response

    result = api_client.fetch_product_info("12345")
    assert result["name"] == "Biofinity"
    assert mock_get.call_count == 1

@patch('requests.get')
def test_fetch_product_info_retry_on_500(mock_get, api_client):
    """500 에러 발생 시 재시도 로직 테스트"""
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_get.return_value = mock_response

    # fetch_product_info 내의 time.sleep 속도를 높이기 위해 patch 가능하나 여기선 기본값으로 진행
    result = api_client.fetch_product_info("12345", retries=2)
    assert result is None
    assert mock_get.call_count == 2

def test_sync_policy(api_client):
    """데이터 동기화 정책 테스트"""
    api_data = {"name": "New Name", "power": "-1.00"}
    local_data = {"name": "Old Name", "power": "-1.00", "source": "manual"}
    
    synced = api_client.sync_with_local_db(api_data, local_data)
    assert synced['name'] == "New Name"
    assert synced['source'] == "api"
