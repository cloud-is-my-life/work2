# [정답] 예시 과제 6 — Query from S3 종합 실전

## 목표

- (A) 단일 대용량 JSONL은 **S3 Select**로 ERROR 레코드만 추출
- (B) 반복 조회 CSV는 Athena External Table + CTAS(Parquet/SNAPPY) 최적화
- (C) 운영 로그 1종(여기서는 CloudTrail) Projection + 7일 이상 분석 쿼리 2개
- (D) 최소 권한 IAM + 결과 버킷 SSL 강제 정책 적용

---

## 1) CloudShell 변수

```bash
export AWS_REGION="ap-northeast-2"
export ATHENA_DB="wsi_final_db"

export RAW_BUCKET="wsi-qfs-data"
export RAW_KEY="raw/huge.jsonl"

export CSV_BUCKET="wsi-qfs-data"
export CSV_PREFIX="sales/csv/"

export CTAS_OUTPUT="s3://wsi-qfs-data/optimized/sales-parquet/"
export ATHENA_RESULTS_BUCKET="ATHENA_RESULTS_BUCKET"

export LOG_BUCKET="wsi-qfs-logs"
export ACCOUNT_ID="123456789012"
```

---

## 2) [A] S3 Select (정답)

```bash
aws s3api select-object-content \
  --bucket "$RAW_BUCKET" \
  --key "$RAW_KEY" \
  --expression "SELECT s.timestamp, s.level, s.message FROM S3Object s WHERE s.level = 'ERROR'" \
  --expression-type SQL \
  --input-serialization '{"JSON":{"Type":"LINES"},"CompressionType":"NONE"}' \
  --output-serialization '{"JSON":{"RecordDelimiter":"\n"}}' \
  error_rows.jsonl
```

검증:

```bash
ls -lh error_rows.jsonl
```

> 참고: 일부 계정은 S3 Select 사용 제한이 있을 수 있음. 과제에서 S3 Select를 요구하면 우선 시도하고, 계정 제한 메시지가 나오면 심사위원 지시에 따라 대체 경로(Athena)로 진행.

---

## 3) [B] Athena External Table + CTAS 최적화 (정답)

Athena SQL:

```sql
CREATE DATABASE IF NOT EXISTS wsi_final_db;

CREATE EXTERNAL TABLE IF NOT EXISTS wsi_final_db.sales_csv_raw (
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
TBLPROPERTIES ('skip.header.line.count'='1');

CREATE TABLE wsi_final_db.sales_parquet_snappy
WITH (
  format='PARQUET',
  parquet_compression='SNAPPY',
  external_location='s3://wsi-qfs-data/optimized/sales-parquet/',
  partitioned_by=ARRAY['order_day']
)
AS
SELECT
  order_id,
  customer_id,
  product_name,
  amount,
  order_day
FROM (
  SELECT
    order_id,
    customer_id,
    product_name,
    CAST(amount AS DOUBLE) AS amount,
    substr(order_date, 1, 10) AS order_day
  FROM wsi_final_db.sales_csv_raw
);
```

검증 SQL:

```sql
SELECT COUNT(*) FROM wsi_final_db.sales_csv_raw;
SELECT COUNT(*) FROM wsi_final_db.sales_parquet_snappy;
SELECT * FROM wsi_final_db.sales_parquet_snappy LIMIT 10;
```

---

## 4) [C] 운영 로그 분석 (CloudTrail 선택, Projection + 7일 쿼리 2개)

### 4-1. Projection 테이블

```sql
CREATE EXTERNAL TABLE IF NOT EXISTS wsi_final_db.cloudtrail_logs_pp (
  eventtime STRING,
  eventname STRING,
  sourceipaddress STRING,
  useridentity STRUCT<username:STRING, arn:STRING>,
  responseelements STRING
)
PARTITIONED BY (`timestamp` STRING)
ROW FORMAT SERDE 'org.apache.hive.hcatalog.data.JsonSerDe'
STORED AS INPUTFORMAT 'com.amazon.emr.cloudtrail.CloudTrailInputFormat'
OUTPUTFORMAT 'org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat'
LOCATION 's3://wsi-qfs-logs/AWSLogs/123456789012/CloudTrail/ap-northeast-2/'
TBLPROPERTIES (
  'projection.enabled'='true',
  'projection.timestamp.type'='date',
  'projection.timestamp.range'='2026/01/01,NOW',
  'projection.timestamp.format'='yyyy/MM/dd',
  'projection.timestamp.interval'='1',
  'projection.timestamp.interval.unit'='DAYS',
  'storage.location.template'='s3://wsi-qfs-logs/AWSLogs/123456789012/CloudTrail/ap-northeast-2/${timestamp}'
);
```

### 4-2. 분석 쿼리 1 (최근 7일 ConsoleLogin 성공/실패)

```sql
SELECT
  `timestamp` AS day,
  COALESCE(json_extract_scalar(responseelements, '$.ConsoleLogin'), 'UNKNOWN') AS login_result,
  COUNT(*) AS cnt
FROM wsi_final_db.cloudtrail_logs_pp
WHERE `timestamp` BETWEEN date_format(current_date - INTERVAL '7' DAY, '%Y/%m/%d')
                      AND date_format(current_date, '%Y/%m/%d')
  AND eventname = 'ConsoleLogin'
GROUP BY `timestamp`, COALESCE(json_extract_scalar(responseelements, '$.ConsoleLogin'), 'UNKNOWN')
ORDER BY day DESC, cnt DESC;
```

### 4-3. 분석 쿼리 2 (최근 7일 상위 Source IP)

```sql
SELECT
  sourceipaddress,
  COUNT(*) AS api_call_count
FROM wsi_final_db.cloudtrail_logs_pp
WHERE `timestamp` BETWEEN date_format(current_date - INTERVAL '7' DAY, '%Y/%m/%d')
                      AND date_format(current_date, '%Y/%m/%d')
GROUP BY sourceipaddress
ORDER BY api_call_count DESC
LIMIT 20;
```

---

## 5) [D] 보안 — 최소 권한 IAM + 결과 버킷 SSL 강제

### 5-1. Athena 최소 권한 정책(예시)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AthenaExecution",
      "Effect": "Allow",
      "Action": [
        "athena:StartQueryExecution",
        "athena:GetQueryExecution",
        "athena:GetQueryResults",
        "athena:GetWorkGroup",
        "athena:ListWorkGroups"
      ],
      "Resource": "*"
    },
    {
      "Sid": "GlueRead",
      "Effect": "Allow",
      "Action": [
        "glue:GetDatabase","glue:GetDatabases",
        "glue:GetTable","glue:GetTables",
        "glue:GetPartition","glue:GetPartitions","glue:BatchGetPartition"
      ],
      "Resource": "*"
    },
    {
      "Sid": "ReadDataBucket",
      "Effect": "Allow",
      "Action": ["s3:GetBucketLocation","s3:ListBucket","s3:GetObject"],
      "Resource": [
        "arn:aws:s3:::wsi-qfs-data",
        "arn:aws:s3:::wsi-qfs-data/*",
        "arn:aws:s3:::wsi-qfs-logs",
        "arn:aws:s3:::wsi-qfs-logs/*"
      ]
    },
    {
      "Sid": "WriteResultsBucket",
      "Effect": "Allow",
      "Action": [
        "s3:GetBucketLocation","s3:ListBucket","s3:GetObject","s3:PutObject",
        "s3:ListBucketMultipartUploads","s3:ListMultipartUploadParts","s3:AbortMultipartUpload"
      ],
      "Resource": [
        "arn:aws:s3:::ATHENA_RESULTS_BUCKET",
        "arn:aws:s3:::ATHENA_RESULTS_BUCKET/*"
      ]
    }
  ]
}
```

### 5-2. 결과 버킷 SSL 강제 정책(예시)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyNonSSL",
      "Effect": "Deny",
      "Principal": "*",
      "Action": "s3:*",
      "Resource": [
        "arn:aws:s3:::ATHENA_RESULTS_BUCKET",
        "arn:aws:s3:::ATHENA_RESULTS_BUCKET/*"
      ],
      "Condition": {
        "Bool": {
          "aws:SecureTransport": "false"
        }
      }
    }
  ]
}
```

---

## 6) 최종 검증 체크

- [ ] `error_rows.jsonl` 생성 확인 (S3 Select)
- [ ] `sales_csv_raw` + `sales_parquet_snappy` 생성 확인
- [ ] CloudTrail Projection 테이블 생성 확인
- [ ] 최근 7일 분석 쿼리 2개 성공
- [ ] IAM 최소 권한 정책/SSL 강제 버킷 정책 적용 확인

---

## 7) Console 경로

- Athena Console: DB/테이블 생성, 분석 쿼리 실행
- IAM Console: 최소 권한 정책 부여
- S3 Console: 결과 버킷 정책(SSL 강제) 적용 확인
