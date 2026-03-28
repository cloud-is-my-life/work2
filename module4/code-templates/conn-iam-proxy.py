"""
시나리오 3: Lambda + RDS Proxy + IAM 인증
- generate_db_auth_token으로 IAM 토큰 생성 (15분 유효)
- SSL 필수 (ssl={"use": True})
- 토큰 생성 hostname == 연결 hostname (Proxy 엔드포인트 사용)

IAM 정책 필요:
  {
    "Effect": "Allow",
    "Action": "rds-db:connect",
    "Resource": "arn:aws:rds-db:REGION:ACCOUNT_ID:dbuser:prx-RESOURCE_ID/DB_USERNAME"
  }

DB 사용자 생성 (RDS MySQL에서 실행):
  CREATE USER 'lambda_user'@'%' IDENTIFIED WITH AWSAuthenticationPlugin AS 'RDS';
  GRANT SELECT, INSERT, UPDATE, DELETE ON mydb.* TO 'lambda_user'@'%';
  FLUSH PRIVILEGES;
"""
import json
import os

import boto3
import pymysql


def get_iam_connection():
    region = os.environ.get("AWS_REGION", "ap-northeast-2")
    proxy_endpoint = os.environ["PROXY_ENDPOINT"]
    db_user = os.environ["DB_USER"]

    # IAM 토큰 생성 (15분 유효 — 매 호출마다 갱신)
    client = boto3.client("rds", region_name=region)
    token = client.generate_db_auth_token(
        DBHostname=proxy_endpoint,
        Port=3306,
        DBUsername=db_user,
        Region=region,
    )

    conn = pymysql.connect(
        host=proxy_endpoint,
        user=db_user,
        password=token,
        database=os.environ["DB_NAME"],
        ssl={"use": True},          # IAM 인증은 SSL 필수
        connect_timeout=10,
        cursorclass=pymysql.cursors.DictCursor,
    )
    return conn


def handler(event, context):
    # IAM 토큰은 15분 유효 → 장기 캐싱보다 매 호출 갱신이 안전
    conn = get_iam_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, email FROM employees LIMIT 10")
            rows = cur.fetchall()
        return {
            "statusCode": 200,
            "body": json.dumps(rows, ensure_ascii=False, default=str),
        }
    finally:
        conn.close()
