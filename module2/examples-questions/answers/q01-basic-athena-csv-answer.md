# [정답] 예시 과제 1 — 기본 CSV 데이터 분석

## 목표

- S3 `s3://wsi-qfs-data/sales/csv/`의 헤더 포함 CSV를 Athena 외부 테이블로 조회
- `amount > 100000` 조건 + 매출 상위 10건 출력

---

## 1) CloudShell 준비

```bash
export AWS_REGION="ap-northeast-2"
export ATHENA_DB="wsi_sales_db"
export ATHENA_TABLE="sales_csv"
```

---

## 2) Athena DDL (정답)

Athena Query Editor 또는 `aws athena start-query-execution`으로 아래 SQL 실행:

```sql
CREATE DATABASE IF NOT EXISTS wsi_sales_db;

CREATE EXTERNAL TABLE IF NOT EXISTS wsi_sales_db.sales_csv (
  order_id STRING,
  customer_id STRING,
  product_name STRING,
  amount DOUBLE,
  order_date STRING
)
ROW FORMAT DELIMITED
FIELDS TERMINATED BY ','
STORED AS TEXTFILE
LOCATION 's3://wsi-qfs-data/sales/csv/'
TBLPROPERTIES (
  'skip.header.line.count'='1'
);
```

---

## 3) 분석 쿼리 (정답)

```sql
SELECT
  order_id,
  customer_id,
  product_name,
  amount,
  order_date
FROM wsi_sales_db.sales_csv
WHERE amount > 100000
ORDER BY amount DESC
LIMIT 10;
```

---

## 4) 검증 명령 (CloudShell)

```bash
aws athena list-table-metadata \
  --region "$AWS_REGION" \
  --catalog-name AwsDataCatalog \
  --database-name "$ATHENA_DB" \
  --query "TableMetadataList[?Name=='$ATHENA_TABLE'].Name" \
  --output table
```

추가 확인 SQL:

```sql
SELECT COUNT(*) AS total_rows FROM wsi_sales_db.sales_csv;
SELECT * FROM wsi_sales_db.sales_csv LIMIT 5;
```

---

## 5) Console 경로

- Athena Console → Query editor → `wsi_sales_db` 선택 → SQL 실행
- Athena Console → Data → `wsi_sales_db.sales_csv` 스키마/LOCATION 확인

---

## 6) 감점 방지 포인트

- `skip.header.line.count='1'` 누락 시 헤더가 데이터로 읽혀 감점
- LOCATION은 정확히 `s3://wsi-qfs-data/sales/csv/` (마지막 `/` 포함)
- 숫자 정렬은 `amount`를 숫자 타입으로 만들어야 정확함
