"""
시나리오 1: API Gateway + Lambda(VPC) + RDS MySQL

핸들러: lambda_function.lambda_handler
런타임: Python 3.11
Layer: pymysql-layer

필수 환경변수:
  DB_HOST  — RDS 엔드포인트
  DB_USER  — DB 사용자명
  DB_PASS  — DB 비밀번호
  DB_NAME  — DB 이름

VPC 설정:
  서브넷: Private Subnet (RDS와 같은 VPC)
  보안그룹: Lambda SG (아웃바운드 3306 → RDS SG)

IAM 역할:
  AWSLambdaBasicExecutionRole
  AWSLambdaVPCAccessExecutionRole

테스트 이벤트 (GET):
  {"httpMethod": "GET", "path": "/employees", "body": null}

테스트 이벤트 (POST):
  {"httpMethod": "POST", "path": "/employees",
   "body": "{\"name\": \"홍길동\", \"email\": \"hong@example.com\", \"dept\": \"개발팀\"}"}
"""
import json
import os

import pymysql

# ── 모듈 레벨 커넥션 ─────────────────────────────────────────
# Lambda 컨테이너가 재사용될 때 기존 커넥션을 재사용.
# 핸들러 내부에 선언하면 매 호출마다 새 연결 생성 → 비효율.
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
    conn = get_connection()

    # GET /employees — 전체 목록 조회
    if method == "GET" and path == "/employees":
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, email, dept, created_at FROM employees ORDER BY id"
            )
            rows = cur.fetchall()
        return response(200, rows)

    # GET /employees/{id} — 단건 조회
    if method == "GET" and path.startswith("/employees/"):
        emp_id = path.split("/")[-1]
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, email, dept FROM employees WHERE id = %s", (emp_id,)
            )
            row = cur.fetchone()
        if row is None:
            return response(404, {"message": "Not Found"})
        return response(200, row)

    # POST /employees — 신규 등록
    if method == "POST" and path == "/employees":
        body = json.loads(event.get("body") or "{}")
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO employees (name, email, dept) VALUES (%s, %s, %s)",
                (body["name"], body["email"], body.get("dept", "")),
            )
        conn.commit()
        return response(201, {"message": "created", "id": conn.insert_id()})

    # DELETE /employees/{id} — 삭제
    if method == "DELETE" and path.startswith("/employees/"):
        emp_id = path.split("/")[-1]
        with conn.cursor() as cur:
            cur.execute("DELETE FROM employees WHERE id = %s", (emp_id,))
        conn.commit()
        return response(200, {"message": "deleted"})

    return response(404, {"message": "Not Found"})
