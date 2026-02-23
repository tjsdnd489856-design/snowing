import sqlite3
import sys
from datetime import datetime
from typing import List, Dict, Any, Optional

class Database:
    """
    콘택트렌즈 정보를 SQLite 데이터베이스에 저장하고 관리하는 클래스입니다.
    """

    def __init__(self, db_path: str = "products.sqlite3"):
        self.db_path = db_path
        self.conn = None
        self._connect()
        self._setup_database()

    def _connect(self):
        """데이터베이스 연결을 설정합니다."""
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
        except sqlite3.Error as e:
            sys.stderr.write(f"데이터베이스 연결 실패: {e}\n")

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
            with self.conn:
                self.conn.execute(query)
        except sqlite3.Error as e:
            sys.stderr.write(f"테이블 생성 중 오류 발생: {e}\n")

    def get_product_by_udi(self, udi: str) -> Optional[Dict[str, Any]]:
        """UDI 번호로 등록된 제품이 있는지 확인합니다."""
        query = "SELECT * FROM products WHERE udi = ?"
        try:
            cursor = self.conn.execute(query, (udi,))
            row = cursor.fetchone()
            return dict(row) if row else None
        except sqlite3.Error:
            return None

    def upsert_product(self, data: Dict[str, Any]) -> bool:
        """제품 정보를 저장하거나 업데이트합니다."""
        if 'expire_date' in data:
            try:
                datetime.strptime(data['expire_date'], "%Y-%m-%d")
            except ValueError:
                sys.stderr.write(f"유효하지 않은 날짜 형식입니다: {data['expire_date']}\n")
                return False

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
            with self.conn:
                self.conn.execute(query, params)
            return True
        except sqlite3.Error as e:
            sys.stderr.write(f"제품 저장/업데이트 중 오류 발생: {e}\n")
            return False

    def list_products(self) -> List[Dict[str, Any]]:
        """저장된 전체 제품 목록을 조회합니다."""
        query = "SELECT * FROM products ORDER BY name ASC"
        try:
            cursor = self.conn.execute(query)
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error:
            return []

    def get_expiring_products(self, days: int = 30) -> Dict[str, List[Dict[str, Any]]]:
        """유통기한 상태 확인"""
        today = datetime.now().date().isoformat()
        future_date_query = f"date('now', '+{days} days')"
        
        try:
            expired = self.conn.execute(
                "SELECT * FROM products WHERE expire_date < ?", 
                (today,)
            ).fetchall()
            
            expiring = self.conn.execute(
                f"SELECT * FROM products WHERE expire_date >= ? AND expire_date <= {future_date_query}", 
                (today,)
            ).fetchall()
            
            return {
                "expired": [dict(row) for row in expired], 
                "expiring": [dict(row) for row in expiring]
            }
        except sqlite3.Error as e:
            sys.stderr.write(f"유통기한 조회 중 오류 발생: {e}\n")
            return {"expired": [], "expiring": []}

    def delete_product(self, product_id: int) -> bool:
        """제품 삭제"""
        try:
            with self.conn:
                self.conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
            return True
        except sqlite3.Error:
            return False

    def close(self):
        """데이터베이스 연결을 닫습니다."""
        if self.conn:
            self.conn.close()

    def __del__(self):
        self.close()
