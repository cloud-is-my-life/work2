# VPC Flow Logs DDL

---

## 핵심

- 예약어 `end` 는 백틱 필요: `` `end` ``
- 기본 경로: `s3://bucket/prefix/AWSLogs/{account}/vpcflowlogs/{region}/{yyyy}/{MM}/{dd}/`
- 파티션 projection 예제가 공식 문서에서 제일 잘 나와 있음

---

## 1. 수동 파티션

```sql
CREATE EXTERNAL TABLE IF NOT EXISTS vpc_flow_logs (
  version int,
  account_id string,
  interface_id string,
  srcaddr string,
  dstaddr string,
  srcport int,
  dstport int,
  protocol bigint,
  packets bigint,
  bytes bigint,
  start bigint,
  `end` bigint,
  action string,
  log_status string,
  vpc_id string,
  subnet_id string,
  instance_id string,
  tcp_flags int,
  type string,
  pkt_srcaddr string,
  pkt_dstaddr string,
  region string,
  az_id string,
  sublocation_type string,
  sublocation_id string,
  pkt_src_aws_service string,
  pkt_dst_aws_service string,
  flow_direction string,
  traffic_path int
)
PARTITIONED BY (`date` date)
ROW FORMAT DELIMITED
FIELDS TERMINATED BY ' '
LOCATION 's3://my-flowlogs-bucket/prefix/AWSLogs/123456789012/vpcflowlogs/us-east-1/'
TBLPROPERTIES ('skip.header.line.count'='1');
```

### 파티션 추가
```sql
ALTER TABLE vpc_flow_logs
ADD PARTITION (`date`='2026-03-24')
LOCATION 's3://my-flowlogs-bucket/prefix/AWSLogs/123456789012/vpcflowlogs/us-east-1/2026/03/24';
```

---

## 2. Partition Projection (비-Hive 경로)

```sql
CREATE EXTERNAL TABLE IF NOT EXISTS vpc_flow_logs_pp (
  version int,
  account_id string,
  interface_id string,
  srcaddr string,
  dstaddr string,
  srcport int,
  dstport int,
  protocol bigint,
  packets bigint,
  bytes bigint,
  start bigint,
  `end` bigint,
  action string,
  log_status string,
  vpc_id string,
  subnet_id string,
  instance_id string,
  tcp_flags int,
  type string,
  pkt_srcaddr string,
  pkt_dstaddr string,
  az_id string,
  sublocation_type string,
  sublocation_id string,
  pkt_src_aws_service string,
  pkt_dst_aws_service string,
  flow_direction string,
  traffic_path int
)
PARTITIONED BY (accid string, region string, day string)
ROW FORMAT DELIMITED
FIELDS TERMINATED BY ' '
LOCATION 's3://my-flowlogs-bucket/AWSLogs/'
TBLPROPERTIES (
  'skip.header.line.count'='1',
  'projection.enabled'='true',
  'projection.accid.type'='enum',
  'projection.accid.values'='123456789012,111122223333',
  'projection.region.type'='enum',
  'projection.region.values'='us-east-1,us-west-2,ap-northeast-2',
  'projection.day.type'='date',
  'projection.day.range'='2024/01/01,NOW',
  'projection.day.format'='yyyy/MM/dd',
  'projection.day.interval'='1',
  'projection.day.interval.unit'='DAYS',
  'storage.location.template'='s3://my-flowlogs-bucket/AWSLogs/${accid}/vpcflowlogs/${region}/${day}'
);
```

### 예시 쿼리
```sql
SELECT srcaddr, dstaddr, SUM(bytes) AS total_bytes
FROM vpc_flow_logs_pp
WHERE accid = '123456789012'
  AND region = 'us-east-1'
  AND day BETWEEN '2026/03/18' AND '2026/03/24'
  AND action = 'ACCEPT'
GROUP BY srcaddr, dstaddr
ORDER BY total_bytes DESC
LIMIT 20;
```
