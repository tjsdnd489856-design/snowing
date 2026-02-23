import pytest
import sqlite3
from datetime import datetime, timedelta
from src.db import Database

@pytest.fixture
def db():
    """테스트용 메모리 데이터베이스 생성"""
    # 실제 파일 대신 메모리 DB 사용
    database = Database(":memory:")
    return database

def test_upsert_product_new(db):
    """새로운 제품 등록 테스트"""
    data = {
        "udi": "test_udi_1",
        "name": "Test Lens",
        "expire_date": "2025-12-31",
        "qty": 10
    }
    assert db.upsert_product(data) is True
    
    product = db.get_product_by_udi("test_udi_1")
    assert product is not None
    assert product['name'] == "Test Lens"
    assert product['qty'] == 10

def test_upsert_product_update(db):
    """기존 제품 업데이트 테스트 (수량 증가)"""
    # 1. 초기 데이터 등록
    data = {
        "udi": "test_udi_2",
        "name": "Test Lens 2",
        "expire_date": "2025-12-31",
        "qty": 5
    }
    db.upsert_product(data)
    
    # 2. 같은 UDI로 데이터 다시 등록 (수량 추가)
    new_data = {
        "udi": "test_udi_2",
        "name": "Updated Name", # 이름 변경 시도
        "expire_date": "2025-12-31",
        "qty": 3 # 3개 추가
    }
    db.upsert_product(new_data)
    
    # 3. 확인
    product = db.get_product_by_udi("test_udi_2")
    assert product['name'] == "Updated Name"
    assert product['qty'] == 8 # 5 + 3 = 8

def test_get_expiring_products(db):
    """유통기한 상태별 조회 테스트"""
    today = datetime.now().date()
    yesterday = (today - timedelta(days=1)).isoformat()
    tomorrow = (today + timedelta(days=1)).isoformat()
    future = (today + timedelta(days=100)).isoformat()
    
    # 1. 만료된 제품
    db.upsert_product({"udi": "expired", "name": "Expired Lens", "expire_date": yesterday})
    
    # 2. 임박한 제품 (내일 만료)
    db.upsert_product({"udi": "expiring", "name": "Expiring Lens", "expire_date": tomorrow})
    
    # 3. 넉넉한 제품 (100일 후 만료)
    db.upsert_product({"udi": "fresh", "name": "Fresh Lens", "expire_date": future})
    
    # 조회
    result = db.get_expiring_products(days=30)
    
    # 검증
    expired_names = [p['name'] for p in result['expired']]
    expiring_names = [p['name'] for p in result['expiring']]
    
    assert "Expired Lens" in expired_names
    assert "Expiring Lens" in expiring_names
    assert "Fresh Lens" not in expired_names
    assert "Fresh Lens" not in expiring_names

def test_delete_product(db):
    """제품 삭제 테스트"""
    db.upsert_product({"udi": "todelete", "name": "To Delete", "expire_date": "2099-12-31"})
    product = db.get_product_by_udi("todelete")
    
    assert db.delete_product(product['id']) is True
    assert db.get_product_by_udi("todelete") is None
