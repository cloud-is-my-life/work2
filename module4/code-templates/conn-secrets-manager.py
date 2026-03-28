"""
시나리오 2: Lambda + Secrets Manager + RDS 연결
- Secrets Manager에서 자격증명 조회 (모듈 레벨 캐싱)
- NAT 없는 VPC → VPC Interface Endpoint 필수
- KMS CMK 사용 시 kms:Decrypt 권한 필요
"""
import json
import os

import boto3
import pymysql

# 모듈 레벨 캐싱 — 컨테이너 재사용 시 재조회 안 함
_secret = None
_conn = None


def get_secret():
    global _secret
    if _secret is None:
        client = boto3.client(
            "secretsmanager", region_name=os.environ.get("AWS_REGION", "ap-northeast-2")
        )
        response = client.get_secret_value(SecretId=os.environ["SECRET_ARN"])
        _secret = json.loads(response["SecretString"])
    return _secret


def get_connection():
    global _conn
    if _conn is None or not _conn.open:
        secret = get_secret()
        _conn = pymysql.connect(
            host=os.environ["DB_HOST"],
            user=secret["username"],
            password=secret["password"],
            database=os.environ["DB_NAME"],
            connect_timeout=5,
            cursorclass=pymysql.cursors.DictCursor,
        )
    return _conn


def handler(event, context):
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS cnt FROM employees")
        result = cur.fetchone()
    return {
        "statusCode": 200,
        "body": json.dumps(result, ensure_ascii=False),
    }
