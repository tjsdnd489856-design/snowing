import sqlite3
from datetime import datetime
from typing import List, Dict, Optional, Any

class Database:
    """SQLite 데이터베이스 관리 클래스 (제품 CRUD 및 유통기한 조회)"""

    def __init__(self, db_path: str = "products.sqlite3"):
        self.db_path = db_path
        self.init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def init_db(self):
        """테이블 스키마 생성 및 마이그레이션"""
        with self._get_connection() as conn:
            conn.execute("""
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
            """)
            conn.commit()

    def upsert_product(self, data: Dict[str, Any]) -> bool:
        """제품 정보 저장 또는 업데이트 (UDI 중복 시 업데이트)"""
        now = datetime.now().isoformat()
        sql = """
            INSERT INTO products (
                udi, gtin, name, power, lot, manufacture_date, expire_date, 
                qty, note, source, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(udi) DO UPDATE SET
                gtin=excluded.gtin,
                name=excluded.name,
                power=excluded.power,
                lot=excluded.lot,
                manufacture_date=excluded.manufacture_date,
                expire_date=excluded.expire_date,
                qty=products.qty + excluded.qty,
                source=excluded.source,
                change_log='Updated via API/Sync',
                updated_at=excluded.updated_at
        """
        params = (
            data.get('udi'), data.get('gtin'), data.get('name'),
            data.get('power'), data.get('lot'), data.get('manufacture_date'),
            data.get('expire_date'), data.get('qty', 1), data.get('note'),
            data.get('source', 'manual'), now
        )
        try:
            with self._get_connection() as conn:
                conn.execute(sql, params)
                conn.commit()
            return True
        except Exception as e:
            print(f"DB 저장 오류: {e}")
            return False

    def list_products(self, search: str = "") -> List[Dict]:
        """제품 전체 목록 조회 (검색어 포함 가능)"""
        sql = "SELECT * FROM products"
        params = ()
        if search:
            sql += " WHERE name LIKE ? OR udi LIKE ? OR lot LIKE ?"
            params = (f"%{search}%", f"%{search}%", f"%{search}%")
        
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_expiring_products(self, days: int = 30) -> Dict[str, List[Dict]]:
        """만료 임박 및 만료된 제품 조회"""
        now = datetime.now().date().isoformat()
        
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            # 만료됨
            expired = conn.execute(
                "SELECT * FROM products WHERE expire_date < ?", (now,)
            ).fetchall()
            # 임박함 (현재 ~ N일 후)
            expiring = conn.execute(
                "SELECT * FROM products WHERE expire_date >= ? AND expire_date <= date('now', ?)",
                (now, f'+{days} days')
            ).fetchall()
            
            return {
                "expired": [dict(row) for row in expired],
                "expiring": [dict(row) for row in expiring]
            }

    def delete_product(self, product_id: int) -> bool:
        """제품 삭제"""
        try:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
                conn.commit()
            return True
        except Exception:
            return False
