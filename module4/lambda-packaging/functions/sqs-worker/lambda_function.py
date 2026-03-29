"""
시나리오 5: SQS → Lambda Worker → MySQL

핸들러: lambda_function.lambda_handler
런타임: Python 3.11
Layer: pymysql-layer

필수 환경변수:
  DB_HOST  — RDS 엔드포인트
  DB_USER  — DB 사용자명
  DB_PASS  — DB 비밀번호
  DB_NAME  — DB 이름

SQS 트리거 설정 (콘솔: Lambda > 구성 > 트리거):
  배치 크기: 10 (한 번에 처리할 메시지 수)
  배치 창: 0초
  함수 응답 유형: ReportBatchItemFailures  ← 반드시 활성화

SQS 큐 설정:
  가시성 타임아웃: Lambda 타임아웃 × 6 이상
  (Lambda 타임아웃 30초 → SQS 가시성 타임아웃 180초 이상)
  DLQ: 연결 권장 (maxReceiveCount: 3)

IAM 역할 필수 권한:
  AWSLambdaBasicExecutionRole
  AWSLambdaVPCAccessExecutionRole
  AWSLambdaSQSQueueExecutionRole  (또는 sqs:ReceiveMessage, sqs:DeleteMessage 등)

예상 SQS 메시지 body (JSON):
  {"order_id": "ORD-001", "user_id": 42, "amount": 15000}

MySQL 테이블 DDL:
  CREATE TABLE orders (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    order_id   VARCHAR(50) NOT NULL,
    user_id    INT NOT NULL,
    amount     INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_order_id (order_id)
  );
"""
import json
import os

import pymysql

_conn = None


def get_connection():
    global _conn
    if _conn is None or not _conn.open:
        _conn = pymysql.connect(
            host=os.environ["DB_HOST"],
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASS"],
            database=os.environ["DB_NAME"],
            connect_timeout=5,
        )
    return _conn


def lambda_handler(event, context):
    failed_ids = []
    conn = get_connection()

    for record in event["Records"]:
        msg_id = record["messageId"]
        try:
            body = json.loads(record["body"])

            with conn.cursor() as cur:
                # INSERT IGNORE: order_id 중복 시 조용히 무시 (멱등성)
                # SQS at-least-once 보장 → 동일 메시지 두 번 처리될 수 있음
                cur.execute(
                    "INSERT IGNORE INTO orders (order_id, user_id, amount) "
                    "VALUES (%s, %s, %s)",
                    (body["order_id"], body["user_id"], body["amount"]),
                )
            conn.commit()
            print(f"OK: {body['order_id']}")

        except Exception as e:
            print(f"FAIL: {msg_id} — {e}")
            # 실패한 메시지 ID를 반환 → SQS가 해당 메시지만 재처리
            failed_ids.append({"itemIdentifier": msg_id})

    # ReportBatchItemFailures: 실패한 메시지만 큐에 돌려보냄
    # 빈 리스트 반환 = 전체 성공
    return {"batchItemFailures": failed_ids}
