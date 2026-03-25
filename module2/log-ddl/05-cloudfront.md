# CloudFront Logs DDL

---

## 1. Standard Logs (Legacy)

```sql
CREATE EXTERNAL TABLE IF NOT EXISTS cloudfront_standard_logs (
  `date` DATE,
  time STRING,
  x_edge_location STRING,
  sc_bytes BIGINT,
  c_ip STRING,
  cs_method STRING,
  cs_host STRING,
  cs_uri_stem STRING,
  sc_status INT,
  cs_referrer STRING,
  cs_user_agent STRING,
  cs_uri_query STRING,
  cs_cookie STRING,
  x_edge_result_type STRING,
  x_edge_request_id STRING,
  x_host_header STRING,
  cs_protocol STRING,
  cs_bytes BIGINT,
  time_taken FLOAT,
  x_forwarded_for STRING,
  ssl_protocol STRING,
  ssl_cipher STRING,
  x_edge_response_result_type STRING,
  cs_protocol_version STRING,
  fle_status STRING,
  fle_encrypted_fields INT,
  c_port INT,
  time_to_first_byte FLOAT,
  x_edge_detailed_result_type STRING,
  sc_content_type STRING,
  sc_content_len BIGINT,
  sc_range_start BIGINT,
  sc_range_end BIGINT
)
ROW FORMAT DELIMITED
FIELDS TERMINATED BY '\t'
LOCATION 's3://my-cloudfront-logs-bucket/'
TBLPROPERTIES ('skip.header.line.count'='2');
```

---

## 2. Partition Projection (JSON path 기반 예시)

```sql
CREATE EXTERNAL TABLE cloudfront_logs_pp (
  `date` string,
  `time` string,
  `x-edge-location` string,
  `sc-bytes` string,
  `c-ip` string,
  `cs-method` string,
  `cs(host)` string,
  `cs-uri-stem` string,
  `sc-status` string,
  `cs(referer)` string,
  `cs(user-agent)` string,
  `cs-uri-query` string,
  `cs(cookie)` string,
  `x-edge-result-type` string,
  `x-edge-request-id` string,
  `x-host-header` string,
  `cs-protocol` string,
  `cs-bytes` string,
  `time-taken` string,
  `x-forwarded-for` string,
  `ssl-protocol` string,
  `ssl-cipher` string,
  `x-edge-response-result-type` string,
  `cs-protocol-version` string,
  `fle-status` string,
  `fle-encrypted-fields` string,
  `c-port` string,
  `time-to-first-byte` string,
  `x-edge-detailed-result-type` string,
  `sc-content-type` string,
  `sc-content-len` string,
  `sc-range-start` string,
  `sc-range-end` string
)
PARTITIONED BY (
  distributionid string,
  year int,
  month int,
  day int,
  hour int
)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
WITH SERDEPROPERTIES (
  'paths'='c-ip,c-port,cs(Cookie),cs(Host),cs(Referer),cs(User-Agent),cs-bytes,cs-method,cs-protocol,cs-protocol-version,cs-uri-query,cs-uri-stem,date,fle-encrypted-fields,fle-status,sc-bytes,sc-content-len,sc-content-type,sc-range-end,sc-range-start,sc-status,ssl-cipher,ssl-protocol,time,time-taken,time-to-first-byte,x-edge-detailed-result-type,x-edge-location,x-edge-request-id,x-edge-response-result-type,x-edge-result-type,x-forwarded-for,x-host-header'
)
STORED AS INPUTFORMAT 'org.apache.hadoop.mapred.TextInputFormat'
OUTPUTFORMAT 'org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat'
LOCATION 's3://my-cloudfront-logs-bucket/AWSLogs/AWS_ACCOUNT_ID/CloudFront/'
TBLPROPERTIES (
  'projection.enabled'='true',
  'projection.distributionid.type'='enum',
  'projection.distributionid.values'='E2OXXXXXXXXXXX',
  'projection.year.type'='integer',
  'projection.year.range'='2024,2026',
  'projection.month.type'='integer',
  'projection.month.range'='01,12',
  'projection.month.digits'='2',
  'projection.day.type'='integer',
  'projection.day.range'='01,31',
  'projection.day.digits'='2',
  'projection.hour.type'='integer',
  'projection.hour.range'='00,23',
  'projection.hour.digits'='2',
  'storage.location.template'='s3://my-cloudfront-logs-bucket/AWSLogs/AWS_ACCOUNT_ID/CloudFront/${distributionid}/${year}/${month}/${day}/${hour}/'
);
```

### 예시 쿼리
```sql
SELECT `cs(host)` AS host, SUM(CAST(`sc-bytes` AS BIGINT)) AS total_bytes
FROM cloudfront_logs_pp
WHERE distributionid = 'E2OXXXXXXXXXXX'
  AND year = 2026
  AND month = 3
  AND day BETWEEN 18 AND 24
GROUP BY `cs(host)`
ORDER BY total_bytes DESC;
```
