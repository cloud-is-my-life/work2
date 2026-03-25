# WAF Logs DDL

---

## 핵심

- WAF 로그는 JSON
- Partition Projection 공식 예제가 아주 좋음
- 경로: `s3://bucket/AWSLogs/{account}/WAFLogs/{source}/{webacl}/{yyyy}/{MM}/{dd}/{HH}/{mm}/`

---

## Partition Projection

```sql
CREATE EXTERNAL TABLE waf_logs_partition_projection (
  `timestamp` bigint,
  `formatversion` int,
  `webaclid` string,
  `terminatingruleid` string,
  `terminatingruletype` string,
  `action` string,
  `terminatingrulematchdetails` array<struct<conditiontype:string,sensitivitylevel:string,location:string,matcheddata:array<string>>>,
  `httpsourcename` string,
  `httpsourceid` string,
  `rulegrouplist` array<struct<rulegroupid:string,terminatingrule:struct<ruleid:string,action:string,rulematchdetails:array<struct<conditiontype:string,sensitivitylevel:string,location:string,matcheddata:array<string>>>>,nonterminatingmatchingrules:array<struct<ruleid:string,action:string,rulematchdetails:array<struct<conditiontype:string,sensitivitylevel:string,location:string,matcheddata:array<string>>>>>,excludedrules:string>>, 
  `ratebasedrulelist` array<struct<ratebasedruleid:string,limitkey:string,maxrateallowed:int>>, 
  `nonterminatingmatchingrules` array<struct<ruleid:string,action:string,rulematchdetails:array<struct<conditiontype:string,sensitivitylevel:string,location:string,matcheddata:array<string>>>>>,
  `requestheadersinserted` array<struct<name:string,value:string>>,
  `responsecodesent` string,
  `httprequest` struct<clientip:string,country:string,headers:array<struct<name:string,value:string>>,uri:string,args:string,httpversion:string,httpmethod:string,requestid:string>,
  `labels` array<struct<name:string>>,
  `captcharesponse` struct<responsecode:string,solvetimestamp:string,failurereason:string>,
  `challengeresponse` struct<responsecode:string,solvetimestamp:string,failurereason:string>,
  `ja3fingerprint` string,
  `ja4fingerprint` string,
  `oversizefields` string,
  `requestbodysize` int,
  `requestbodysizeinspectedbywaf` int
)
PARTITIONED BY (`log_time` string)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
STORED AS INPUTFORMAT 'org.apache.hadoop.mapred.TextInputFormat'
OUTPUTFORMAT 'org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat'
LOCATION 's3://my-waf-logs-bucket/AWSLogs/123456789012/WAFLogs/cloudfront/my-distribution/'
TBLPROPERTIES (
  'projection.enabled'='true',
  'projection.log_time.format'='yyyy/MM/dd/HH/mm',
  'projection.log_time.interval'='1',
  'projection.log_time.interval.unit'='minutes',
  'projection.log_time.range'='2024/01/01/00/00,NOW',
  'projection.log_time.type'='date',
  'storage.location.template'='s3://my-waf-logs-bucket/AWSLogs/123456789012/WAFLogs/cloudfront/my-distribution/${log_time}'
);
```

### 예시 쿼리
```sql
SELECT from_unixtime(`timestamp`/1000) AS event_time, action, httprequest.clientip, httprequest.uri
FROM waf_logs_partition_projection
WHERE log_time BETWEEN '2026/03/24/00/00' AND '2026/03/24/23/59'
  AND action IN ('BLOCK', 'CAPTCHA', 'CHALLENGE')
ORDER BY event_time DESC;
```
