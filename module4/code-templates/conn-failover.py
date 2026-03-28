"""
시나리오 7: Multi-AZ RDS + Lambda 재연결 패턴
- ping(reconnect=True)으로 연결 상태 확인
- 지수 백오프(exponential backoff)로 재시도
- 항상 DNS hostname 사용 (IP 하드코딩 금지)

장애 조치 흐름:
  1. RDS Primary 장애 → Multi-AZ Standby가 Primary로 승격 (60-120초)
  2. RDS DNS 엔드포인트가 새 Primary IP를 가리킴
  3. Lambda 컨테이너의 DNS 캐시는 old IP를 가질 수 있음
  4. ping(reconnect=True) → 연결 실패 → 새 연결 생성 → DNS 재조회
"""
import os
import time

import pymysql

_conn = None


def get_connection(retries: int = 3):
    global _conn

    for attempt in range(retries):
        try:
            if _conn is not None:
                # ping(reconnect=True): 끊어진 경우 자동 재연결 시도
                _conn.ping(reconnect=True)
                return _conn
        except Exception:
            _conn = None  # 재연결 실패 시 커넥션 초기화

        try:
            # 항상 DNS hostname 사용 — IP 하드코딩 금지
            _conn = pymysql.connect(
                host=os.environ["DB_HOST"],   # RDS DNS 엔드포인트
                user=os.environ["DB_USER"],
                password=os.environ["DB_PASS"],
                database=os.environ["DB_NAME"],
                connect_timeout=5,
            )
            return _conn
        except Exception as e:
            if attempt < retries - 1:
                wait = 2 ** attempt     # 1초, 2초, 4초...
                print(f"Connection failed (attempt {attempt + 1}), retrying in {wait}s: {e}")
                time.sleep(wait)
            else:
                raise


def handler(event, context):
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT 1")
    return {"statusCode": 200, "message": "ok"}
