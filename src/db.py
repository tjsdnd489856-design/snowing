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

    def get_product_by_gtin(self, gtin: str) -> Optional[Dict[str, Any]]:
        """GTIN(상품번호)으로 등록된 제품이 있는지 확인합니다."""
        query = "SELECT * FROM products WHERE gtin = ? LIMIT 1"
        try:
            cursor = self.conn.execute(query, (gtin,))
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

    def get_expiring_products(self, days: int = 90) -> Dict[str, List[Dict[str, Any]]]:
        """
        유통기한 상태 확인 (제품별 차등 적용)
        - 기본: 3개월(90일) 이내
        - 특정 제품(클래리티, 토탈원, 피니티, 프로클리어): 9개월(270일) 이내
        """
        today = datetime.now().date()
        expired = []
        expiring = []
        
        # 특정 제품 키워드 (오래 남았어도 빨리 팔아야 하는 제품들)
        long_term_keywords = ["클래리티", "토탈원", "피니티", "프로클리어"]
        long_term_days = 270 # 9개월 (약 270일)

        try:
            # 모든 제품을 가져와서 파이썬에서 필터링 (복잡한 조건 처리 위함)
            # 재고가 0 초과인 제품만 유통기한 알림 대상에 포함
            with self.conn:
                cursor = self.conn.execute("SELECT * FROM products WHERE qty > 0")
                all_products = [dict(row) for row in cursor.fetchall()]

            for p in all_products:
                try:
                    expire_str = p['expire_date']
                    if not expire_str or expire_str == '9999-12-31':
                        continue
                        
                    expire_date = datetime.strptime(expire_str, "%Y-%m-%d").date()
                    days_left = (expire_date - today).days
                    
                    if days_left < 0:
                        p['days_left'] = days_left
                        expired.append(p)
                        continue
                    
                    # 제품명 확인
                    name = p['name'] or ""
                    # 키워드가 하나라도 포함되어 있는지 확인
                    is_long_term = any(k in name for k in long_term_keywords)
                    
                    limit_days = long_term_days if is_long_term else days
                    
                    if days_left <= limit_days:
                        p['days_left'] = days_left # 남은 일수 추가 정보
                        expiring.append(p)

                except (ValueError, TypeError):
                    continue # 날짜 형식이 이상하면 무시

            # 남은 일수 순으로 정렬 (급한 것부터)
            expiring.sort(key=lambda x: x['days_left'])
            
            return {"expired": expired, "expiring": expiring}
            
        except sqlite3.Error as e:
            sys.stderr.write(f"유통기한 조회 중 오류 발생: {e}\n")
            return {"expired": [], "expiring": []}

    def decrement_stock_by_udi(self, udi: str) -> Dict[str, Any]:
        """UDI에 해당하는 제품의 재고를 1 감소시킵니다. 재고가 0이 되어도 삭제하지 않습니다."""
        try:
            # 제품 조회
            cursor = self.conn.execute("SELECT * FROM products WHERE udi = ?", (udi,))
            row = cursor.fetchone()
            
            if not row:
                return {'success': False, 'message': '제품을 찾을 수 없습니다.', 'product': None}
            
            product = dict(row)
            
            # 이미 0 이하인 경우 더 이상 차감하지 않고 안내
            if product['qty'] <= 0:
                return {'success': False, 'message': f"이미 재고가 0인 제품입니다: {product['name']}", 'product': product}

            new_qty = product['qty'] - 1
            
            with self.conn:
                if new_qty <= 0:
                    new_qty = 0
                    self.conn.execute("UPDATE products SET qty = ? WHERE udi = ?", (new_qty, udi))
                    msg = f"재고 소진 (남은 수량: 0): {product['name']}"
                else:
                    self.conn.execute("UPDATE products SET qty = ? WHERE udi = ?", (new_qty, udi))
                    msg = f"재고 1 감소 (남은 수량: {new_qty}): {product['name']}"
            
            product['qty'] = new_qty # 결과 반환용 업데이트
            return {'success': True, 'message': msg, 'product': product}
            
        except sqlite3.Error as e:
            return {'success': False, 'message': f"DB 오류: {e}", 'product': None}

    def decrement_stock_by_gtin(self, gtin: str) -> Dict[str, Any]:
        """GTIN(상품번호)에 해당하는 제품 중 유통기한이 가장 임박한 재고를 1 감소시킵니다."""
        try:
            # 재고가 있는 제품 중 유통기한이 가장 짧은 것(가장 먼저 팔아야 할 것)을 조회
            cursor = self.conn.execute(
                "SELECT * FROM products WHERE gtin = ? AND qty > 0 ORDER BY expire_date ASC LIMIT 1", 
                (gtin,)
            )
            row = cursor.fetchone()
            
            if not row:
                return {'success': False, 'message': '해당 상품번호의 남은 재고를 찾을 수 없습니다.', 'product': None}
            
            product = dict(row)
            new_qty = product['qty'] - 1
            udi = product['udi'] # 실제 업데이트는 UDI(고유번호) 기준으로 수행
            
            with self.conn:
                if new_qty <= 0:
                    new_qty = 0
                    self.conn.execute("UPDATE products SET qty = ? WHERE udi = ?", (new_qty, udi))
                    msg = f"재고 소진 (남은 수량: 0): {product['name']}"
                else:
                    self.conn.execute("UPDATE products SET qty = ? WHERE udi = ?", (new_qty, udi))
                    msg = f"재고 1 감소 (남은 수량: {new_qty}): {product['name']}"
            
            product['qty'] = new_qty
            return {'success': True, 'message': msg, 'product': product}
            
        except sqlite3.Error as e:
            return {'success': False, 'message': f"DB 오류: {e}", 'product': None}

    def delete_product(self, product_id: int) -> bool:
        """제품 강제 삭제 (Home키를 통한 ID 삭제)"""
        try:
            with self.conn:
                self.conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
            return True
        except sqlite3.Error:
            return False

    def update_expiry_for_default_items(self, new_date: str = '2031-03-31') -> int:
        """기본값(9999-12-31)으로 설정된 유통기한을 일괄 수정합니다."""
        try:
            with self.conn:
                cursor = self.conn.execute(
                    "UPDATE products SET expire_date = ? WHERE expire_date = '9999-12-31'", 
                    (new_date,)
                )
                return cursor.rowcount
        except sqlite3.Error as e:
            sys.stderr.write(f"유통기한 일괄 수정 중 오류: {e}\n")
            return 0

    def close(self):
        """데이터베이스 연결을 닫습니다."""
        if self.conn:
            self.conn.close()

    def __del__(self):
        self.close()