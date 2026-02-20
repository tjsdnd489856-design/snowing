import sqlite3
from datetime import datetime
from typing import List, Dict, Any, Optional

class Database:
    """
    콘택트렌즈 정보를 SQLite 데이터베이스에 저장하고 관리하는 클래스입니다.
    """

    def __init__(self, db_path: str = "products.sqlite3"):
        self.db_path = db_path
        self._setup_database()

    def _get_connection(self) -> sqlite3.Connection:
        """데이터베이스 연결 객체를 생성합니다."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _setup_database(self):
        """프로그램 실행에 필요한 테이블을 생성합니다."""
        query = """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                udi TEXT UNIQUE NOT NULL,
                gtin TEXT,
                name TEXT NOT NULL,
                power TEXT,
                lot TEXT,
                manufacture_date TEXT,
                expire_date TEXT NOT NULL,
                qty INTEGER DEFAULT 1,
                note TEXT,
                source TEXT DEFAULT 'manual',
                change_log TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """
        try:
            with self._get_connection() as conn:
                conn.execute(query)
        except sqlite3.Error as e:
            print(f"데이터베이스 초기화 중 오류 발생: {e}")

    def upsert_product(self, data: Dict[str, Any]) -> bool:
        """
        제품 정보를 저장하거나, 이미 존재하는 경우 업데이트합니다.
        (UDI 번호가 중복되면 기존 정보를 갱신하고 수량을 더합니다.)
        """
        now = datetime.now().isoformat()
        query = """
            INSERT INTO products (
                udi, gtin, name, power, lot, manufacture_date, expire_date, 
                qty, note, source, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(udi) DO UPDATE SET
                gtin = excluded.gtin,
                name = excluded.name,
                power = excluded.power,
                lot = excluded.lot,
                manufacture_date = excluded.manufacture_date,
                expire_date = excluded.expire_date,
                qty = products.qty + excluded.qty,
                source = excluded.source,
                change_log = '시스템에 의해 업데이트됨',
                updated_at = excluded.updated_at
        """
        params = (
            data.get('udi'), data.get('gtin'), data.get('name'),
            data.get('power'), data.get('lot'), data.get('manufacture_date'),
            data.get('expire_date'), data.get('qty', 1), data.get('note'),
            data.get('source', 'manual'), now
        )
        try:
            with self._get_connection() as conn:
                conn.execute(query, params)
            return True
        except sqlite3.Error as e:
            print(f"제품 저장/업데이트 중 오류 발생: {e}")
            return False

    def list_products(self, search: str = "") -> List[Dict[str, Any]]:
        """저장된 전체 제품 목록을 조회합니다. 검색어가 있으면 필터링합니다."""
        query = "SELECT * FROM products"
        params = ()
        
        if search:
            query += " WHERE name LIKE ? OR udi LIKE ? OR lot LIKE ?"
            params = (f"%{search}%", f"%{search}%", f"%{search}%")
        
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error:
            return []

    def get_expiring_products(self, days: int = 30) -> Dict[str, List[Dict[str, Any]]]:
        """유통기한이 지났거나 임박한 제품들을 분류하여 반환합니다."""
        today = datetime.now().date().isoformat()
        
        try:
            with self._get_connection() as conn:
                # 1. 유통기한 만료 제품
                expired = conn.execute(
                    "SELECT * FROM products WHERE expire_date < ?", (today,)
                ).fetchall()
                
                # 2. 유통기한 임박 제품 (현재부터 N일 이내)
                expiring = conn.execute(
                    "SELECT * FROM products WHERE expire_date >= ? AND expire_date <= date('now', ?)",
                    (today, f'+{days} days')
                ).fetchall()
                
                return {
                    "expired": [dict(row) for row in expired],
                    "expiring": [dict(row) for row in expiring]
                }
        except sqlite3.Error:
            return {"expired": [], "expiring": []}

    def delete_product(self, product_id: int) -> bool:
        """지정한 ID의 제품을 삭제합니다."""
        try:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
            return True
        except sqlite3.Error:
            return False
