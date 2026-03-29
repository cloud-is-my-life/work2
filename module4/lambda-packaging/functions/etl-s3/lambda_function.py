"""
시나리오 4: S3 Event → Lambda → MySQL ETL

핸들러: lambda_function.lambda_handler
런타임: Python 3.11
Layer: pymysql-layer

필수 환경변수:
  DB_HOST  — RDS 엔드포인트
  DB_USER  — DB 사용자명
  DB_PASS  — DB 비밀번호
  DB_NAME  — DB 이름

Lambda 설정:
  타임아웃: 300초 (기본 3초로는 ETL 불가)
  메모리: 256MB 이상 권장

IAM 역할 필수 권한:
  AWSLambdaBasicExecutionRole
  AWSLambdaVPCAccessExecutionRole
  s3:GetObject  (S3 트리거만으로는 파일 읽기 권한 없음, 별도 필요)

S3 트리거 설정:
  이벤트 유형: PUT
  prefix: data/   (선택)
  suffix: .csv    (무한 루프 방지를 위해 필수 설정)

예상 CSV 형식:
  name,email,dept
  홍길동,hong@example.com,개발팀
  김철수,kim@example.com,영업팀

MySQL 테이블 DDL:
  CREATE TABLE employees (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    name       VARCHAR(100) NOT NULL,
    email      VARCHAR(100) NOT NULL,
    dept       VARCHAR(50),
    UNIQUE KEY uq_email (email)
  );
"""
import csv
import io
import json
import os

import boto3
import pymysql

s3_client = boto3.client("s3")
_conn = None


def get_connection():
    global _conn
    if _conn is None or not _conn.open:
        _conn = pymysql.connect(
            host=os.environ["DB_HOST"],
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASS"],
            database=os.environ["DB_NAME"],
            autocommit=False,       # 트랜잭션 수동 제어
            connect_timeout=5,
        )
    return _conn


def lambda_handler(event, context):
    record = event["Records"][0]
    bucket = record["s3"]["bucket"]["name"]
    key = record["s3"]["object"]["key"]

    print(f"Processing s3://{bucket}/{key}")

    # S3 파일 읽기 (s3:GetObject 권한 필요)
    obj = s3_client.get_object(Bucket=bucket, Key=key)
    content = obj["Body"].read().decode("utf-8-sig")  # BOM 포함 UTF-8 처리

    # CSV 파싱
    reader = csv.DictReader(io.StringIO(content))
    rows = [
        (r["name"].strip(), r["email"].strip(), r.get("dept", "").strip())
        for r in reader
        if r.get("name", "").strip()    # 빈 행 건너뜀
    ]

    if not rows:
        print("No rows to insert")
        return {"statusCode": 200, "inserted": 0}

    conn = get_connection()
    try:
        conn.begin()
        with conn.cursor() as cur:
            # ON DUPLICATE KEY UPDATE: 같은 email이 이미 있으면 UPDATE
            # → 동일 파일을 두 번 처리해도 중복 데이터 없음 (멱등성)
            sql = (
                "INSERT INTO employees (name, email, dept) VALUES (%s, %s, %s) "
                "ON DUPLICATE KEY UPDATE name = VALUES(name), dept = VALUES(dept)"
            )
            cur.executemany(sql, rows)
            affected = cur.rowcount
        conn.commit()
        print(f"Done: {affected} rows affected (inserted/updated)")
        return {"statusCode": 200, "affected": affected}

    except Exception as e:
        conn.rollback()     # 실패 시 전체 롤백 — 부분 삽입 방지
        print(f"Error: {e}")
        raise               # 예외 다시 발생 → Lambda DLQ로 전송
