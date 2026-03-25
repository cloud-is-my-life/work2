# [정답] 예시 과제 4 — ALB 5xx 분석 + Parquet 최적화

## 목표

- ALB Access Logs를 Projection 테이블(`alb_access_logs_pp`)로 구성
- 최근 24시간 5xx를 `target_group_arn` 기준 집계
- CTAS로 Parquet + SNAPPY + `day` 파티셔닝 수행

---

## 1) CloudShell 변수

```bash
export AWS_REGION="ap-northeast-2"
export ATHENA_DB="wsi_ops_db"
```

---

## 2) Athena DDL (정답)

```sql
CREATE DATABASE IF NOT EXISTS wsi_ops_db;

CREATE EXTERNAL TABLE IF NOT EXISTS wsi_ops_db.alb_access_logs_pp (
  type string,
  time string,
  elb string,
  client_ip string,
  client_port int,
  target_ip string,
  target_port int,
  request_processing_time double,
  target_processing_time double,
  response_processing_time double,
  elb_status_code int,
  target_status_code string,
  received_bytes bigint,
  sent_bytes bigint,
  request_verb string,
  request_url string,
  request_proto string,
  user_agent string,
  ssl_cipher string,
  ssl_protocol string,
  target_group_arn string,
  trace_id string,
  domain_name string,
  chosen_cert_arn string,
  matched_rule_priority string,
  request_creation_time string,
  actions_executed string,
  redirect_url string,
  lambda_error_reason string,
  target_port_list string,
  target_status_code_list string,
  classification string,
  classification_reason string,
  conn_trace_id string
)
PARTITIONED BY (day STRING)
ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.RegexSerDe'
WITH SERDEPROPERTIES (
  'serialization.format'='1',
  'input.regex'='([^ ]*) ([^ ]*) ([^ ]*) ([^ ]*):([0-9]*) ([^ ]*)[:-]([0-9]*) ([-.0-9]*) ([-.0-9]*) ([-.0-9]*) (|[-0-9]*) (-|[-0-9]*) ([-0-9]*) ([-0-9]*) "([^ ]*) (.*) (- |[^ ]*)" "([^"]*)" ([A-Z0-9-_]+) ([A-Za-z0-9.-]*) ([^ ]*) "([^"]*)" "([^"]*)" "([^"]*)" ([-.0-9]*) ([^ ]*) "([^"]*)" "([^"]*)" "([^ ]*)" "([^\\s]+?)" "([^\\s]+)" "([^ ]*)" "([^ ]*)" ?([^ ]*)? ?( .*)?'
)
LOCATION 's3://wsi-qfs-logs/AWSLogs/123456789012/elasticloadbalancing/ap-northeast-2/'
TBLPROPERTIES (
  'projection.enabled'='true',
  'projection.day.type'='date',
  'projection.day.range'='2026/01/01,NOW',
  'projection.day.format'='yyyy/MM/dd',
  'projection.day.interval'='1',
  'projection.day.interval.unit'='DAYS',
  'storage.location.template'='s3://wsi-qfs-logs/AWSLogs/123456789012/elasticloadbalancing/ap-northeast-2/${day}'
);
```

---

## 3) 최근 24시간 5xx 집계 (정답)

```sql
SELECT
  target_group_arn,
  COUNT(*) AS error_5xx_count
FROM wsi_ops_db.alb_access_logs_pp
WHERE day BETWEEN date_format(current_date - INTERVAL '1' DAY, '%Y/%m/%d')
              AND date_format(current_date, '%Y/%m/%d')
  AND from_iso8601_timestamp(time) >= current_timestamp - INTERVAL '24' HOUR
  AND elb_status_code BETWEEN 500 AND 599
GROUP BY target_group_arn
ORDER BY error_5xx_count DESC;
```

---

## 4) CTAS 최적화 (Parquet + SNAPPY + day 파티션)

> `external_location` 경로는 **비어 있어야 함**.

```sql
CREATE TABLE wsi_ops_db.alb_5xx_parquet
WITH (
  format='PARQUET',
  parquet_compression='SNAPPY',
  external_location='s3://wsi-qfs-data/optimized/alb-5xx/',
  partitioned_by=ARRAY['day']
)
AS
SELECT
  target_group_arn,
  elb_status_code,
  from_iso8601_timestamp(time) AS event_ts,
  request_url,
  user_agent,
  day
FROM wsi_ops_db.alb_access_logs_pp
WHERE day >= date_format(current_date - INTERVAL '7' DAY, '%Y/%m/%d')
  AND elb_status_code BETWEEN 500 AND 599;
```

---

## 5) 검증

```sql
SHOW CREATE TABLE wsi_ops_db.alb_access_logs_pp;
SHOW CREATE TABLE wsi_ops_db.alb_5xx_parquet;

SELECT day, COUNT(*) AS cnt
FROM wsi_ops_db.alb_5xx_parquet
GROUP BY day
ORDER BY day DESC;
```

---

## 6) Console 경로

- Athena Console → Query editor에서 DDL/분석/CTAS 순서 실행
- Athena Console → Data에서 `wsi_ops_db.alb_5xx_parquet` 생성 확인
- S3 Console → `s3://wsi-qfs-data/optimized/alb-5xx/` 결과 파일 확인

---

## 7) 감점 방지 포인트

- Regex 끝 `?( .*)?` 패턴 삭제 금지(신규 필드 대비)
- Projection 테이블에 `MSCK REPAIR TABLE` 불필요
- CTAS `partitioned_by` 컬럼(`day`)은 SELECT 맨 끝에 위치
