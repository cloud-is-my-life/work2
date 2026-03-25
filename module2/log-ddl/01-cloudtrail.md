# CloudTrail DDL

---

## 핵심

- AWS 공식 문서는 **`org.apache.hive.hcatalog.data.JsonSerDe` 권장**
- 이유: 구형 `CloudTrailSerde`가 최신 필드를 덜 받는 경우 있음
- InputFormat은 `com.amazon.emr.cloudtrail.CloudTrailInputFormat`
- 기본 경로: `s3://bucket/AWSLogs/{account-id}/CloudTrail/{region}/{yyyy}/{MM}/{dd}/`

---

## 1. 수동 파티션

```sql
CREATE EXTERNAL TABLE cloudtrail_logs (
  eventversion STRING,
  useridentity STRUCT<
    type:STRING,
    principalid:STRING,
    arn:STRING,
    accountid:STRING,
    invokedby:STRING,
    accesskeyid:STRING,
    username:STRING,
    onbehalfof:STRUCT<
      userid:STRING,
      identitystorearn:STRING
    >,
    sessioncontext:STRUCT<
      attributes:STRUCT<
        mfaauthenticated:STRING,
        creationdate:STRING
      >,
      sessionissuer:STRUCT<
        type:STRING,
        principalid:STRING,
        arn:STRING,
        accountid:STRING,
        username:STRING
      >,
      ec2roledelivery:STRING,
      webidfederationdata:STRUCT<
        federatedprovider:STRING,
        attributes:MAP<STRING,STRING>
      >
    >
  >,
  eventtime STRING,
  eventsource STRING,
  eventname STRING,
  awsregion STRING,
  sourceipaddress STRING,
  useragent STRING,
  errorcode STRING,
  errormessage STRING,
  requestparameters STRING,
  responseelements STRING,
  additionaleventdata STRING,
  requestid STRING,
  eventid STRING,
  resources ARRAY<STRUCT<
    arn:STRING,
    accountid:STRING,
    type:STRING
  >>,
  eventtype STRING,
  apiversion STRING,
  readonly STRING,
  recipientaccountid STRING,
  serviceeventdetails STRING,
  sharedeventid STRING,
  vpcendpointid STRING,
  vpcendpointaccountid STRING,
  eventcategory STRING,
  addendum STRUCT<
    reason:STRING,
    updatedfields:STRING,
    originalrequestid:STRING,
    originaleventid:STRING
  >,
  sessioncredentialfromconsole STRING,
  edgedevicedetails STRING,
  tlsdetails STRUCT<
    tlsversion:STRING,
    ciphersuite:STRING,
    clientprovidedhostheader:STRING
  >
)
PARTITIONED BY (region STRING, year STRING, month STRING, day STRING)
ROW FORMAT SERDE 'org.apache.hive.hcatalog.data.JsonSerDe'
STORED AS INPUTFORMAT 'com.amazon.emr.cloudtrail.CloudTrailInputFormat'
OUTPUTFORMAT 'org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat'
LOCATION 's3://my-cloudtrail-bucket/AWSLogs/123456789012/';
```

### 파티션 추가
```sql
ALTER TABLE cloudtrail_logs ADD
PARTITION (
  region='us-east-1',
  year='2026',
  month='03',
  day='24'
)
LOCATION 's3://my-cloudtrail-bucket/AWSLogs/123456789012/CloudTrail/us-east-1/2026/03/24/';
```

---

## 2. Partition Projection

```sql
CREATE EXTERNAL TABLE cloudtrail_logs_pp (
  eventversion STRING,
  useridentity STRUCT<
    type:STRING,
    principalid:STRING,
    arn:STRING,
    accountid:STRING,
    invokedby:STRING,
    accesskeyid:STRING,
    username:STRING,
    onbehalfof:STRUCT<userid:STRING, identitystorearn:STRING>,
    sessioncontext:STRUCT<
      attributes:STRUCT<mfaauthenticated:STRING, creationdate:STRING>,
      sessionissuer:STRUCT<type:STRING, principalid:STRING, arn:STRING, accountid:STRING, username:STRING>,
      ec2roledelivery:STRING,
      webidfederationdata:STRUCT<federatedprovider:STRING, attributes:MAP<STRING,STRING>>
    >
  >,
  eventtime STRING,
  eventsource STRING,
  eventname STRING,
  awsregion STRING,
  sourceipaddress STRING,
  useragent STRING,
  errorcode STRING,
  errormessage STRING,
  requestparameters STRING,
  responseelements STRING,
  additionaleventdata STRING,
  requestid STRING,
  eventid STRING,
  readonly STRING,
  resources ARRAY<STRUCT<arn:STRING, accountid:STRING, type:STRING>>,
  eventtype STRING,
  apiversion STRING,
  recipientaccountid STRING,
  serviceeventdetails STRING,
  sharedeventid STRING,
  vpcendpointid STRING,
  vpcendpointaccountid STRING,
  eventcategory STRING,
  addendum STRUCT<reason:STRING, updatedfields:STRING, originalrequestid:STRING, originaleventid:STRING>,
  sessioncredentialfromconsole STRING,
  edgedevicedetails STRING,
  tlsdetails STRUCT<tlsversion:STRING, ciphersuite:STRING, clientprovidedhostheader:STRING>
)
PARTITIONED BY (`timestamp` STRING)
ROW FORMAT SERDE 'org.apache.hive.hcatalog.data.JsonSerDe'
STORED AS INPUTFORMAT 'com.amazon.emr.cloudtrail.CloudTrailInputFormat'
OUTPUTFORMAT 'org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat'
LOCATION 's3://my-cloudtrail-bucket/AWSLogs/123456789012/CloudTrail/us-east-1/'
TBLPROPERTIES (
  'projection.enabled'='true',
  'projection.timestamp.format'='yyyy/MM/dd',
  'projection.timestamp.interval'='1',
  'projection.timestamp.interval.unit'='DAYS',
  'projection.timestamp.range'='2024/01/01,NOW',
  'projection.timestamp.type'='date',
  'storage.location.template'='s3://my-cloudtrail-bucket/AWSLogs/123456789012/CloudTrail/us-east-1/${timestamp}'
);
```

### 예시 쿼리
```sql
SELECT eventtime, eventname, sourceipaddress, useridentity.username
FROM cloudtrail_logs_pp
WHERE `timestamp` BETWEEN '2026/03/18' AND '2026/03/24'
  AND eventname = 'ConsoleLogin'
ORDER BY eventtime DESC;
```
