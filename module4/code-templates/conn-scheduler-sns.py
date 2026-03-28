"""
시나리오 6: EventBridge → Lambda → MySQL + SNS 알림
- 스케줄 기반 DB 정리 작업
- 완료 후 SNS 토픽에 알림 발행
- EventBridge는 Lambda를 비동기 호출 → Lambda Destination 사용 가능

Lambda 역할 필요 권한:
  - sns:Publish

Lambda 리소스 정책 필요:
  aws lambda add-permission \
    --function-name FUNC_NAME \
    --statement-id EventBridgeInvoke \
    --action lambda:InvokeFunction \
    --principal events.amazonaws.com \
    --source-arn arn:aws:events:REGION:ACCOUNT_ID:rule/RULE_NAME

EventBridge cron (UTC 기준):
  cron(0 0 * * ? *) = 매일 KST 09:00
"""
import os
from datetime import datetime, timedelta

import boto3
import pymysql

sns = boto3.client("sns")
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
    conn = get_connection()
    cutoff = datetime.now() - timedelta(days=int(os.environ.get("RETENTION_DAYS", "30")))

    with conn.cursor() as cur:
        cur.execute("DELETE FROM temp_data WHERE created_at < %s", (cutoff,))
        deleted = cur.rowcount
    conn.commit()

    # 완료 알림 발행
    sns.publish(
        TopicArn=os.environ["SNS_TOPIC_ARN"],
        Subject="[DB Cleanup] 완료",
        Message=f"{deleted}건 삭제 완료 ({datetime.now().isoformat()})",
    )

    print(f"Deleted {deleted} rows older than {cutoff}")
    return {"deleted": deleted}
