"""
시나리오 2+3: Lambda + Secrets Manager + RDS Proxy + IAM 인증

핸들러: lambda_function.lambda_handler
런타임: Python 3.11
Layer: pymysql-layer

필수 환경변수:
  SECRET_ARN      — Secrets Manager 시크릿 ARN
  PROXY_ENDPOINT  — RDS Proxy 엔드포인트 (hostname)
  DB_USER         — IAM 인증용 DB 사용자명 (AWSAuthenticationPlugin 사용자)
  DB_NAME         — DB 이름

VPC 설정:
  서브넷: Private Subnet
  보안그룹: Lambda SG

IAM 역할 필수 권한:
  AWSLambdaBasicExecutionRole
  AWSLambdaVPCAccessExecutionRole
  secretsmanager:GetSecretValue          (Secrets Manager 시크릿 조회)
  rds-db:connect (Resource: prx-xxxx)   (RDS Proxy IAM 인증)

VPC Interface Endpoint 필요:
  NAT Gateway 없는 환경에서 Secrets Manager 접근 시
  com.amazonaws.REGION.secretsmanager 엔드포인트 생성 + private DNS 활성화

DB 사용자 사전 생성 필요 (RDS MySQL):
  CREATE USER 'lambda_user'@'%' IDENTIFIED WITH AWSAuthenticationPlugin AS 'RDS';
  GRANT SELECT, INSERT, UPDATE, DELETE ON mydb.* TO 'lambda_user'@'%';
  FLUSH PRIVILEGES;
"""
import json
import os

import boto3
import pymysql

# ── Secrets Manager 시크릿 캐싱 ─────────────────────────────
# 매 호출마다 GetSecretValue 호출은 불필요한 API 비용 + 지연 발생.
# 모듈 레벨에서 한 번만 조회하고 재사용.
_secret = None


def get_secret():
    global _secret
    if _secret is None:
        client = boto3.client("secretsmanager")
        r = client.get_secret_value(SecretId=os.environ["SECRET_ARN"])
        _secret = json.loads(r["SecretString"])
    return _secret


# ── IAM 토큰 기반 연결 ────────────────────────────────────────
# IAM 토큰은 15분 유효 → 장기 캐싱 대신 매 호출 갱신이 안전.
# (커넥션 자체를 캐싱하면 토큰 만료 후 재연결 필요)
def get_connection():
    region = os.environ.get("AWS_REGION", "ap-northeast-2")
    proxy_endpoint = os.environ["PROXY_ENDPOINT"]
    db_user = os.environ["DB_USER"]

    token = boto3.client("rds").generate_db_auth_token(
        DBHostname=proxy_endpoint,
        Port=3306,
        DBUsername=db_user,
        Region=region,
    )

    return pymysql.connect(
        host=proxy_endpoint,
        user=db_user,
        password=token,
        database=os.environ["DB_NAME"],
        ssl={"use": True},          # IAM 인증은 SSL 필수
        connect_timeout=10,
        cursorclass=pymysql.cursors.DictCursor,
    )


def response(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, ensure_ascii=False, default=str),
    }


# ── 핸들러 ───────────────────────────────────────────────────
def lambda_handler(event, context):
    method = event.get("httpMethod", "GET")
    path = event.get("path", "/")

    # Secrets Manager에서 시크릿 조회 (캐싱됨)
    # 이 예제에서는 DB_USER/DB_NAME을 환경변수로 받지만,
    # 필요하면 시크릿에서 읽어도 됨: secret["username"]
    _ = get_secret()

    conn = get_connection()
    try:
        if method == "GET" and path == "/employees":
            with conn.cursor() as cur:
                cur.execute("SELECT id, name, email, dept FROM employees ORDER BY id")
                rows = cur.fetchall()
            return response(200, rows)

        if method == "POST" and path == "/employees":
            body = json.loads(event.get("body") or "{}")
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO employees (name, email, dept) VALUES (%s, %s, %s)",
                    (body["name"], body["email"], body.get("dept", "")),
                )
            conn.commit()
            return response(201, {"message": "created"})

        return response(404, {"message": "Not Found"})
    finally:
        conn.close()
