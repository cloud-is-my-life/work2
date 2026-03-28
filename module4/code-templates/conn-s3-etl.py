"""
시나리오 4: S3 Event → Lambda → MySQL ETL
- S3 이벤트에서 버킷/키 추출
- CSV 파싱 (utf-8-sig: BOM 포함 UTF-8 처리)
- executemany로 배치 INSERT (성능 최적화)
- ON DUPLICATE KEY UPDATE로 멱등성 보장
- 트랜잭션으로 부분 실패 방지

Lambda 역할 필요 권한:
  - AWSLambdaVPCAccessExecutionRole
  - s3:GetObject (S3 트리거만으로는 파일 읽기 권한 없음)

Lambda 설정:
  - Timeout: 300초 (기본 3초는 ETL에 부족)
  - Layer: pymysql
"""
import csv
import io
import json
import os

import boto3
import pymysql

s3 = boto3.client("s3")
_conn = None


def get_connection():
    global _conn
    if _conn is None or not _conn.open:
        _conn = pymysql.connect(
            host=os.environ["DB_HOST"],
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASS"],
            database=os.environ["DB_NAME"],
            autocommit=False,   # 트랜잭션 수동 제어
            connect_timeout=5,
        )
    return _conn


def handler(event, context):
    record = event["Records"][0]
    bucket = record["s3"]["bucket"]["name"]
    key = record["s3"]["object"]["key"]

    # S3 파일 읽기 (s3:GetObject 권한 필요)
    response = s3.get_object(Bucket=bucket, Key=key)
    content = response["Body"].read().decode("utf-8-sig")  # BOM 처리

    reader = csv.DictReader(io.StringIO(content))
    rows = [
        (r["name"], r["email"], r.get("dept", ""))
        for r in reader
        if r.get("name")    # 빈 행 건너뜀
    ]

    if not rows:
        return {"statusCode": 200, "body": "no rows"}

    conn = get_connection()
    try:
        conn.begin()
        with conn.cursor() as cur:
            sql = (
                "INSERT INTO employees (name, email, dept) VALUES (%s, %s, %s) "
                "ON DUPLICATE KEY UPDATE dept = VALUES(dept)"
            )
            cur.executemany(sql, rows)
        conn.commit()
        print(f"Inserted/updated {len(rows)} rows from s3://{bucket}/{key}")
        return {"statusCode": 200, "inserted": len(rows)}
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
        raise
