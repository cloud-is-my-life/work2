# [정답] 예시 과제 2 — CloudTrail ConsoleLogin 탐지

## 목표

- CloudTrail 로그 경로를 Partition Projection 기반 Athena 테이블로 구성
- 최근 7일 `ConsoleLogin` 이벤트에서 사용자명/IP/이벤트 시간을 최신순 조회

---

## 1) CloudShell 준비

```bash
export AWS_REGION="us-east-1"
export ATHENA_DB="wsi_security_db"
export ATHENA_TABLE="cloudtrail_logs_pp"
export ACCOUNT_ID="123456789012"
export LOG_BUCKET="wsi-qfs-logs"
```

---

## 2) Athena DDL (Projection 정답)

```sql
CREATE DATABASE IF NOT EXISTS wsi_security_db;

CREATE EXTERNAL TABLE IF NOT EXISTS wsi_security_db.cloudtrail_logs_pp (
  useridentity STRUCT<username:STRING, arn:STRING>,
  eventtime STRING,
  eventname STRING,
  sourceipaddress STRING
)
PARTITIONED BY (`timestamp` STRING)
ROW FORMAT SERDE 'org.apache.hive.hcatalog.data.JsonSerDe'
STORED AS INPUTFORMAT 'com.amazon.emr.cloudtrail.CloudTrailInputFormat'
OUTPUTFORMAT 'org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat'
LOCATION 's3://wsi-qfs-logs/AWSLogs/123456789012/CloudTrail/us-east-1/'
TBLPROPERTIES (
  'projection.enabled'='true',
  'projection.timestamp.type'='date',
  'projection.timestamp.range'='2026/01/01,NOW',
  'projection.timestamp.format'='yyyy/MM/dd',
  'projection.timestamp.interval'='1',
  'projection.timestamp.interval.unit'='DAYS',
  'storage.location.template'='s3://wsi-qfs-logs/AWSLogs/123456789012/CloudTrail/us-east-1/${timestamp}'
);
```

---

## 3) 최근 7일 ConsoleLogin 쿼리 (정답)

```sql
SELECT
  COALESCE(useridentity.username, useridentity.arn, 'UNKNOWN') AS user_name,
  sourceipaddress AS source_ip,
  from_iso8601_timestamp(eventtime) AS event_ts
FROM wsi_security_db.cloudtrail_logs_pp
WHERE `timestamp` BETWEEN date_format(current_date - INTERVAL '7' DAY, '%Y/%m/%d')
                      AND date_format(current_date, '%Y/%m/%d')
  AND eventname = 'ConsoleLogin'
ORDER BY event_ts DESC;
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

Projection 확인 SQL:

```sql
SHOW CREATE TABLE wsi_security_db.cloudtrail_logs_pp;
SELECT *
FROM wsi_security_db.cloudtrail_logs_pp
WHERE `timestamp` = date_format(current_date, '%Y/%m/%d')
LIMIT 5;
```

---

## 5) Console 경로

- Athena Console → Query editor → `wsi_security_db`에서 DDL/쿼리 실행
- Athena Console → Data → `cloudtrail_logs_pp` 테이블 속성에서 Projection 확인

---

## 6) 감점 방지 포인트

- Projection 테이블에서 `MSCK REPAIR TABLE` 실행하지 않는다
- 시작 날짜는 요구사항대로 `2026-01-01` (`'2026/01/01,NOW'`)
- `event_ts` 정렬은 문자열이 아니라 timestamp로 변환해서 정렬
