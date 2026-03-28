"""
시나리오 1: 기본 VPC Lambda + RDS MySQL 연결
- 환경변수로 DB 정보 관리
- 모듈 레벨 커넥션 재사용 (컨테이너 재사용 시 새 연결 방지)
- API Gateway Lambda 프록시 통합 응답 형식
"""
import json
import os

import pymysql

# 모듈 레벨 커넥션 — 컨테이너 재사용 시 재연결하지 않음
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
            cursorclass=pymysql.cursors.DictCursor,
        )
    return _conn


def handler(event, context):
    method = event.get("httpMethod", "GET")
    path = event.get("path", "/")

    conn = get_connection()

    if method == "GET" and path == "/employees":
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, email, dept FROM employees")
            rows = cur.fetchall()
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(rows, ensure_ascii=False, default=str),
        }

    if method == "POST" and path == "/employees":
        body = json.loads(event.get("body", "{}"))
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO employees (name, email, dept) VALUES (%s, %s, %s)",
                (body["name"], body["email"], body.get("dept")),
            )
        conn.commit()
        return {
            "statusCode": 201,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"message": "created"}, ensure_ascii=False),
        }

    return {"statusCode": 404, "body": "Not Found"}
