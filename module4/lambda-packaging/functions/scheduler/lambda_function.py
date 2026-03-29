"""
시나리오 6: EventBridge → Lambda → MySQL + SNS 알림

핸들러: lambda_function.lambda_handler
런타임: Python 3.11
Layer: pymysql-layer

필수 환경변수:
  DB_HOST         — RDS 엔드포인트
  DB_USER         — DB 사용자명
  DB_PASS         — DB 비밀번호
  DB_NAME         — DB 이름
  SNS_TOPIC_ARN   — 완료 알림을 보낼 SNS 토픽 ARN
  RETENTION_DAYS  — 보관 기간 (기본: 30)

IAM 역할 필수 권한:
  AWSLambdaBasicExecutionRole
  AWSLambdaVPCAccessExecutionRole
  sns:Publish

EventBridge 트리거 설정:
  규칙 유형: 일정
  일정 패턴:
    매일 KST 오전 9시  → cron(0 0 * * ? *)   [UTC 기준]
    매시간             → rate(1 hour)
    5분마다            → rate(5 minutes)
  ※ cron은 UTC 기준. KST = UTC+9

Lambda 리소스 정책 (EventBridge가 Lambda 호출 가능하도록):
  콘솔에서 EventBridge를 트리거로 추가하면 자동 생성됨.
  직접 추가 시: lambda:InvokeFunction, principal: events.amazonaws.com

MySQL 테이블 DDL:
  CREATE TABLE temp_data (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    data       TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  );
"""
import os
from datetime import datetime, timedelta

import boto3
import pymysql

sns_client = boto3.client("sns")
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
    retention_days = int(os.environ.get("RETENTION_DAYS", "30"))
    cutoff = datetime.now() - timedelta(days=retention_days)

    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM temp_data WHERE created_at < %s", (cutoff,)
        )
        deleted = cur.rowcount
    conn.commit()

    print(f"Deleted {deleted} rows older than {cutoff.date()}")

    # SNS 완료 알림 발행
    sns_client.publish(
        TopicArn=os.environ["SNS_TOPIC_ARN"],
        Subject="[DB Cleanup] 완료",
        Message=(
            f"정리 완료\n"
            f"삭제 건수: {deleted}건\n"
            f"기준 날짜: {cutoff.date()} 이전\n"
            f"실행 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        ),
    )

    return {"deleted": deleted}
