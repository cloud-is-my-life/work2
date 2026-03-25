# S3 Access Logs DDL

---

## 핵심

- AWS 자체 문서에서 CloudTrail Data Events를 더 권장하지만, S3 Access Logs도 출제 가능
- RegexSerDe 사용
- 경로는 버킷/프리픽스 구성 따라 달라짐 → **실제 로그 위치 먼저 확인**

---

## 1. 기본 테이블

```sql
CREATE EXTERNAL TABLE s3_access_logs (
  bucketowner STRING,
  bucket_name STRING,
  requestdatetime STRING,
  remoteip STRING,
  requester STRING,
  requestid STRING,
  operation STRING,
  key STRING,
  request_uri STRING,
  httpstatus STRING,
  errorcode STRING,
  bytessent BIGINT,
  objectsize BIGINT,
  totaltime STRING,
  turnaroundtime STRING,
  referrer STRING,
  useragent STRING,
  versionid STRING,
  hostid STRING,
  sigv STRING,
  ciphersuite STRING,
  authtype STRING,
  endpoint STRING,
  tlsversion STRING,
  accesspointarn STRING,
  aclrequired STRING,
  sourceregion STRING
)
ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.RegexSerDe'
WITH SERDEPROPERTIES (
  'input.regex'='([^ ]*) ([^ ]*) \[(.*?)\] ([^ ]*) ([^ ]*) ([^ ]*) ([^ ]*) ([^ ]*) ("[^"]*"|-) (-|[0-9]*) ([^ ]*) ([^ ]*) ([^ ]*) ([^ ]*) ([^ ]*) ([^ ]*) ("[^"]*"|-) ([^ ]*)(?: ([^ ]*) ([^ ]*) ([^ ]*) ([^ ]*) ([^ ]*) ([^ ]*) ([^ ]*) ([^ ]*) ([^ ]*))?.*$'
)
STORED AS INPUTFORMAT 'org.apache.hadoop.mapred.TextInputFormat'
OUTPUTFORMAT 'org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat'
LOCATION 's3://my-s3-access-logs-bucket/prefix/';
```

---

## 2. 날짜 projection 버전

```sql
CREATE EXTERNAL TABLE s3_access_logs_pp (
  bucketowner STRING,
  bucket_name STRING,
  requestdatetime STRING,
  remoteip STRING,
  requester STRING,
  requestid STRING,
  operation STRING,
  key STRING,
  request_uri STRING,
  httpstatus STRING,
  errorcode STRING,
  bytessent BIGINT,
  objectsize BIGINT,
  totaltime STRING,
  turnaroundtime STRING,
  referrer STRING,
  useragent STRING,
  versionid STRING,
  hostid STRING,
  sigv STRING,
  ciphersuite STRING,
  authtype STRING,
  endpoint STRING,
  tlsversion STRING,
  accesspointarn STRING,
  aclrequired STRING,
  sourceregion STRING
)
PARTITIONED BY (`timestamp` string)
ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.RegexSerDe'
WITH SERDEPROPERTIES (
  'input.regex'='([^ ]*) ([^ ]*) \[(.*?)\] ([^ ]*) ([^ ]*) ([^ ]*) ([^ ]*) ([^ ]*) ("[^"]*"|-) (-|[0-9]*) ([^ ]*) ([^ ]*) ([^ ]*) ([^ ]*) ([^ ]*) ([^ ]*) ("[^"]*"|-) ([^ ]*)(?: ([^ ]*) ([^ ]*) ([^ ]*) ([^ ]*) ([^ ]*) ([^ ]*) ([^ ]*) ([^ ]*) ([^ ]*))?.*$'
)
STORED AS INPUTFORMAT 'org.apache.hadoop.mapred.TextInputFormat'
OUTPUTFORMAT 'org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat'
LOCATION 's3://bucket-name/prefix-name/account-id/region/source-bucket-name/'
TBLPROPERTIES (
  'projection.enabled'='true',
  'projection.timestamp.format'='yyyy/MM/dd',
  'projection.timestamp.interval'='1',
  'projection.timestamp.interval.unit'='DAYS',
  'projection.timestamp.range'='2024/01/01,NOW',
  'projection.timestamp.type'='date',
  'storage.location.template'='s3://bucket-name/prefix-name/account-id/region/source-bucket-name/${timestamp}'
);
```

### 예시 쿼리
```sql
SELECT key, COUNT(*) AS access_count, SUM(bytessent) AS total_bytes_sent
FROM s3_access_logs_pp
WHERE operation = 'REST.GET.OBJECT'
  AND httpstatus = '200'
  AND `timestamp` BETWEEN '2026/03/18' AND '2026/03/24'
GROUP BY key
ORDER BY access_count DESC
LIMIT 20;
```
