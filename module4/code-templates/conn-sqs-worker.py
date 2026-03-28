"""
시나리오 5: SQS → Lambda Worker → RDS MySQL
- SQS 이벤트 소스 매핑으로 배치 처리
- ReportBatchItemFailures로 부분 실패 처리 (실패한 메시지만 재처리)
- INSERT IGNORE로 멱등성 보장
- 각 메시지 개별 처리 — 하나 실패해도 나머지는 정상 처리

SQS 설정 필수:
  - VisibilityTimeout >= Lambda Timeout × 6
  - DLQ 연결 (maxReceiveCount: 3)

Event Source Mapping 설정:
  - FunctionResponseTypes: [ReportBatchItemFailures]
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
        )
    return _conn


def handler(event, context):
    failed_ids = []
    conn = get_connection()

    for record in event["Records"]:
        msg_id = record["messageId"]
        try:
            body = json.loads(record["body"])
            with conn.cursor() as cur:
                # INSERT IGNORE: 중복 order_id는 조용히 무시 (멱등성)
                cur.execute(
                    "INSERT IGNORE INTO orders (order_id, user_id, amount) "
                    "VALUES (%s, %s, %s)",
                    (body["order_id"], body["user_id"], body["amount"]),
                )
            conn.commit()
        except Exception as e:
            print(f"Failed to process message {msg_id}: {e}")
            failed_ids.append({"itemIdentifier": msg_id})

    # 실패한 메시지만 재처리되도록 반환
    return {"batchItemFailures": failed_ids}
