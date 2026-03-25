# ALB Access Logs DDL

---

## 핵심

- SerDe: `org.apache.hadoop.hive.serde2.RegexSerDe`
- 기본 경로: `s3://bucket/AWSLogs/{account}/elasticloadbalancing/{region}/{yyyy}/{MM}/{dd}/`
- 정규식 끝의 `?( .*)?`는 **미래 필드 추가 대비용** → 지우지 마라

---

## 1. 수동 테이블

```sql
CREATE EXTERNAL TABLE IF NOT EXISTS alb_access_logs (
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
ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.RegexSerDe'
WITH SERDEPROPERTIES (
  'serialization.format' = '1',
  'input.regex' = '([^ ]*) ([^ ]*) ([^ ]*) ([^ ]*):([0-9]*) ([^ ]*)[:-]([0-9]*) ([-.0-9]*) ([-.0-9]*) ([-.0-9]*) (|[-0-9]*) (-|[-0-9]*) ([-0-9]*) ([-0-9]*) "([^ ]*) (.*) (- |[^ ]*)" "([^"]*)" ([A-Z0-9-_]+) ([A-Za-z0-9.-]*) ([^ ]*) "([^"]*)" "([^"]*)" "([^"]*)" ([-.0-9]*) ([^ ]*) "([^"]*)" "([^"]*)" "([^ ]*)" "([^\\s]+?)" "([^\\s]+)" "([^ ]*)" "([^ ]*)" ?([^ ]*)? ?( .*)?'
)
LOCATION 's3://my-alb-logs-bucket/AWSLogs/123456789012/elasticloadbalancing/us-east-1/';
```

---

## 2. Partition Projection

```sql
CREATE EXTERNAL TABLE IF NOT EXISTS alb_access_logs_pp (
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
  'serialization.format' = '1',
  'input.regex' = '([^ ]*) ([^ ]*) ([^ ]*) ([^ ]*):([0-9]*) ([^ ]*)[:-]([0-9]*) ([-.0-9]*) ([-.0-9]*) ([-.0-9]*) (|[-0-9]*) (-|[-0-9]*) ([-0-9]*) ([-0-9]*) "([^ ]*) (.*) (- |[^ ]*)" "([^"]*)" ([A-Z0-9-_]+) ([A-Za-z0-9.-]*) ([^ ]*) "([^"]*)" "([^"]*)" "([^"]*)" ([-.0-9]*) ([^ ]*) "([^"]*)" "([^"]*)" "([^ ]*)" "([^\\s]+?)" "([^\\s]+)" "([^ ]*)" "([^ ]*)" ?([^ ]*)? ?( .*)?'
)
LOCATION 's3://my-alb-logs-bucket/AWSLogs/123456789012/elasticloadbalancing/us-east-1/'
TBLPROPERTIES (
  'projection.enabled'='true',
  'projection.day.type'='date',
  'projection.day.range'='2024/01/01,NOW',
  'projection.day.format'='yyyy/MM/dd',
  'projection.day.interval'='1',
  'projection.day.interval.unit'='DAYS',
  'storage.location.template'='s3://my-alb-logs-bucket/AWSLogs/123456789012/elasticloadbalancing/us-east-1/${day}'
);
```

### 예시 쿼리
```sql
SELECT target_group_arn, elb_status_code, COUNT(*) AS cnt
FROM alb_access_logs_pp
WHERE day = '2026/03/24'
  AND elb_status_code BETWEEN 500 AND 599
GROUP BY target_group_arn, elb_status_code
ORDER BY cnt DESC;
```
