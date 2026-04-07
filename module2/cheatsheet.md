# Athena 도우미 — DDL / DML / CLI / CTAS / Partition Projection

---

## 1. DDL — CREATE TABLE

### 기본 구조
```sql
CREATE EXTERNAL TABLE [IF NOT EXISTS] db_name.table_name (
    col1  STRING,
    col2  INT,
    col3  BIGINT,
    col4  DOUBLE,
    col5  BOOLEAN,
    col6  ARRAY<STRING>,
    col7  MAP<STRING, STRING>,
    col8  STRUCT<field1:STRING, field2:INT>
)
[PARTITIONED BY (part_col1 STRING, part_col2 STRING)]
ROW FORMAT SERDE 'serde.class.name'
[WITH SERDEPROPERTIES ('key'='value')]
STORED AS INPUTFORMAT 'input.format.class'
OUTPUTFORMAT 'output.format.class'
LOCATION 's3://bucket/prefix/'
[TBLPROPERTIES ('key'='value')];
```

### CSV (LazySimpleSerDe — 단순 구분자)
```sql
CREATE EXTERNAL TABLE csv_simple (
    id      STRING,
    name    STRING,
    value   DOUBLE
)
ROW FORMAT DELIMITED
FIELDS TERMINATED BY ','
LINES TERMINATED BY '\n'
LOCATION 's3://bucket/csv-data/'
TBLPROPERTIES ('skip.header.line.count'='1');
```

### CSV (OpenCSVSerDe — 따옴표 처리)
```sql
CREATE EXTERNAL TABLE csv_quoted (
    id      STRING,
    name    STRING,
    value   STRING   -- OpenCSVSerDe는 모든 컬럼 STRING 취급!
)
ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.OpenCSVSerde'
WITH SERDEPROPERTIES (
    'separatorChar' = ',',
    'quoteChar'     = '"',
    'escapeChar'    = '\\'
)
STORED AS TEXTFILE
LOCATION 's3://bucket/csv-quoted/';
```
> ⚠️ OpenCSVSerDe는 **모든 컬럼을 STRING으로 취급**. INT/DOUBLE 쓰려면 쿼리에서 CAST 필요.

### JSON (OpenX JsonSerDe)
```sql
CREATE EXTERNAL TABLE json_table (
    id          STRING,
    timestamp   STRING,
    data        STRUCT<key1:STRING, key2:INT>,
    tags        ARRAY<STRING>
)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
WITH SERDEPROPERTIES (
    'ignore.malformed.json' = 'true',
    'case.insensitive'      = 'true'
)
STORED AS INPUTFORMAT 'org.apache.hadoop.mapred.TextInputFormat'
OUTPUTFORMAT 'org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat'
LOCATION 's3://bucket/json-data/';
```

### Parquet
```sql
CREATE EXTERNAL TABLE parquet_table (
    id      BIGINT,
    name    STRING,
    amount  DOUBLE
)
STORED AS PARQUET
LOCATION 's3://bucket/parquet-data/';
```
> Parquet은 ROW FORMAT SERDE 생략 가능. STORED AS PARQUET이면 자동 매핑.

### ORC
```sql
CREATE EXTERNAL TABLE orc_table (
    id      BIGINT,
    name    STRING,
    amount  DOUBLE
)
STORED AS ORC
LOCATION 's3://bucket/orc-data/';
```

### Regex (로그 파싱용)
```sql
CREATE EXTERNAL TABLE regex_table (
    col1  STRING,
    col2  STRING,
    col3  INT
)
ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.RegexSerDe'
WITH SERDEPROPERTIES (
    'serialization.format' = '1',
    'input.regex' = '([^ ]*) ([^ ]*) ([0-9]*)'
)
STORED AS INPUTFORMAT 'org.apache.hadoop.mapred.TextInputFormat'
OUTPUTFORMAT 'org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat'
LOCATION 's3://bucket/log-data/';
```
> ⚠️ 정규식 캡처 그룹 수 = 컬럼 수. 안 맞으면 전부 NULL.

---

## 2. DDL — 파티션 관리

### 수동 파티션 추가
```sql
ALTER TABLE my_table ADD
PARTITION (year='2026', month='03', day='24')
LOCATION 's3://bucket/prefix/year=2026/month=03/day=24/';
```

### 전체 파티션 자동 로드 (Hive 호환 경로만)
```sql
MSCK REPAIR TABLE my_table;
```
> ⚠️ Hive 호환 = `key=value/` 형식만. `2026/03/24/` 같은 비-Hive 경로는 안 됨.
> ⚠️ Partition Projection 쓰면 MSCK REPAIR TABLE **절대 불필요**.

### 파티션 삭제
```sql
ALTER TABLE my_table DROP PARTITION (year='2026', month='03', day='24');
```

### 파티션 확인
```sql
SHOW PARTITIONS my_table;
```

---

## 3. Partition Projection (자동 파티션 — 핵심!)

### 날짜 기반 (가장 흔함)
```sql
CREATE EXTERNAL TABLE logs_pp (
    -- 컬럼 정의 ...
)
PARTITIONED BY (`timestamp` STRING)
ROW FORMAT ...
LOCATION 's3://bucket/AWSLogs/123456789012/service/us-east-1/'
TBLPROPERTIES (
    'projection.enabled'                  = 'true',
    'projection.timestamp.type'           = 'date',
    'projection.timestamp.range'          = '2024/01/01,NOW',
    'projection.timestamp.format'         = 'yyyy/MM/dd',
    'projection.timestamp.interval'       = '1',
    'projection.timestamp.interval.unit'  = 'DAYS',
    'storage.location.template'           = 's3://bucket/AWSLogs/123456789012/service/us-east-1/${timestamp}'
);
```

### 정수 기반 (연/월/일 분리)
```sql
PARTITIONED BY (year STRING, month STRING, day STRING)
...
TBLPROPERTIES (
    'projection.enabled'       = 'true',
    'projection.year.type'     = 'integer',
    'projection.year.range'    = '2024,2026',
    'projection.month.type'    = 'integer',
    'projection.month.range'   = '1,12',
    'projection.month.digits'  = '2',
    'projection.day.type'      = 'integer',
    'projection.day.range'     = '1,31',
    'projection.day.digits'    = '2',
    'storage.location.template'= 's3://bucket/prefix/${year}/${month}/${day}'
);
```

### Enum 기반 (리전, 계정 등)
```sql
PARTITIONED BY (region STRING)
...
TBLPROPERTIES (
    'projection.enabled'        = 'true',
    'projection.region.type'    = 'enum',
    'projection.region.values'  = 'us-east-1,us-west-2,ap-northeast-2,eu-west-1',
    'storage.location.template' = 's3://bucket/prefix/${region}/'
);
```

### Injected (WHERE절 필수)
```sql
PARTITIONED BY (account_id STRING)
...
TBLPROPERTIES (
    'projection.enabled'           = 'true',
    'projection.account_id.type'   = 'injected',
    'storage.location.template'    = 's3://bucket/AWSLogs/${account_id}/prefix/'
);
-- 쿼리 시 반드시: WHERE account_id = '123456789012'
```

### 복합 (enum + date)
```sql
PARTITIONED BY (region STRING, day STRING)
...
TBLPROPERTIES (
    'projection.enabled'              = 'true',
    'projection.region.type'          = 'enum',
    'projection.region.values'        = 'us-east-1,ap-northeast-2',
    'projection.day.type'             = 'date',
    'projection.day.range'            = '2024/01/01,NOW',
    'projection.day.format'           = 'yyyy/MM/dd',
    'projection.day.interval'         = '1',
    'projection.day.interval.unit'    = 'DAYS',
    'storage.location.template'       = 's3://bucket/AWSLogs/123456789012/elasticloadbalancing/${region}/${day}'
);
```

---

## 4. CTAS (CREATE TABLE AS SELECT)

### CSV to Parquet 변환 + SNAPPY 압축 + 파티셔닝
```sql
CREATE TABLE new_parquet
WITH (
    format              = 'PARQUET',
    parquet_compression = 'SNAPPY',
    external_location   = 's3://output-bucket/parquet-data/',
    partitioned_by      = ARRAY['year', 'month']
)
AS
SELECT
    id, name, amount,
    substr("date", 1, 4) AS year,
    substr("date", 6, 2) AS month
FROM source_csv_table
WHERE cast(substr("date", 1, 4) AS INT) >= 2024;
```
> ⚠️ 파티션 컬럼은 SELECT 맨 끝에 배치!

### ORC + ZLIB 압축
```sql
CREATE TABLE new_orc
WITH (
    format            = 'ORC',
    write_compression = 'ZLIB',
    external_location = 's3://output-bucket/orc-data/'
)
AS SELECT * FROM source_table;
```

### 버킷팅 + 파티셔닝
```sql
CREATE TABLE bucketed_table
WITH (
    format           = 'PARQUET',
    external_location= 's3://output-bucket/bucketed/',
    partitioned_by   = ARRAY['region'],
    bucketed_by      = ARRAY['customer_id'],
    bucket_count     = 8
)
AS SELECT customer_id, order_id, amount, region
FROM orders;
```
> ⚠️ 파티션 x 버킷 <= 100. 예: 버킷 8개면 파티션 최대 12개.

### 빈 테이블 복제 (스키마만)
```sql
CREATE TABLE empty_copy
AS SELECT * FROM source_table
WITH NO DATA;
```

---

## 5. DML — 자주 쓰는 쿼리 패턴

### 기본 SELECT
```sql
SELECT col1, col2, COUNT(*) AS cnt
FROM my_table
WHERE year = '2026' AND month = '03'
GROUP BY col1, col2
HAVING COUNT(*) > 10
ORDER BY cnt DESC
LIMIT 100;
```

### CTE (WITH 절)
```sql
WITH daily_stats AS (
    SELECT
        date_parse(time, '%Y-%m-%dT%H:%i:%s') AS ts,
        elb_status_code,
        COUNT(*) AS cnt
    FROM alb_logs
    WHERE day = '2026/03/24'
    GROUP BY 1, 2
)
SELECT * FROM daily_stats WHERE cnt > 100;
```

### Window 함수
```sql
SELECT
    eventname,
    sourceipaddress,
    eventtime,
    ROW_NUMBER() OVER (PARTITION BY sourceipaddress ORDER BY eventtime DESC) AS rn,
    LAG(eventtime) OVER (PARTITION BY sourceipaddress ORDER BY eventtime) AS prev_time
FROM cloudtrail_logs
WHERE eventname = 'ConsoleLogin';
```

### INSERT INTO (기존 테이블에 추가)
```sql
INSERT INTO target_table
SELECT col1, col2, col3
FROM source_table
WHERE condition;
```

### UNLOAD (결과를 특정 포맷으로 S3에 저장)
```sql
UNLOAD (SELECT * FROM my_table WHERE year = '2026')
TO 's3://output-bucket/unload-results/'
WITH (format = 'PARQUET', compression = 'SNAPPY');
```

---

## 6. 자주 쓰는 함수

### 문자열
```sql
regexp_extract(request_url, 'host=([^&]+)', 1)   -- 정규식 추출
regexp_like(user_agent, '(?i)bot|crawler')        -- 정규식 매칭
split(request_url, '/')[2]                        -- 문자열 분할
substr(time, 1, 10)                               -- 부분 문자열
trim(name)                                        -- 공백 제거
lower(eventname)                                  -- 소문자
upper(region)                                     -- 대문자
concat(col1, '-', col2)                           -- 문자열 결합
length(user_agent)                                -- 문자열 길이
replace(url, '%20', ' ')                          -- 문자열 치환
```

### 날짜/시간
```sql
date_parse(time, '%Y-%m-%dT%H:%i:%s.%fZ')        -- 문자열 to 타임스탬프
date_format(ts, '%Y-%m-%d')                       -- 타임스탬프 to 문자열
from_unixtime(start)                              -- Unix epoch to 타임스탬프
from_iso8601_timestamp(time)                      -- ISO8601 to 타임스탬프
date_add('day', -7, current_date)                 -- 7일 전
date_diff('hour', ts1, ts2)                       -- 시간 차이
current_date                                      -- 오늘 (DATE)
current_timestamp                                 -- 지금 (TIMESTAMP)
year(ts)  / month(ts)  / day(ts)                  -- 연/월/일 추출
```

### JSON 추출
```sql
json_extract(requestparameters, '$.bucketName')           -- JSON 값 (JSON 타입)
json_extract_scalar(requestparameters, '$.bucketName')    -- JSON 값 (STRING)
json_array_get(json_col, 0)                               -- 배열 인덱스
json_array_length(json_col)                               -- 배열 길이
```

### 집계
```sql
COUNT(*)                          -- 전체 행 수
COUNT(DISTINCT col)               -- 고유값 수
APPROX_DISTINCT(col)              -- 근사 고유값 (빠름)
SUM(bytes)                        -- 합계
AVG(response_time)                -- 평균
MIN(ts) / MAX(ts)                 -- 최소/최대
APPROX_PERCENTILE(latency, 0.99)  -- P99
```

### 타입 변환
```sql
CAST(col AS INT)
CAST(col AS DOUBLE)
CAST(col AS VARCHAR)
CAST(col AS TIMESTAMP)
TRY(CAST(col AS INT))            -- 실패 시 NULL (에러 안 남)
COALESCE(col, 'default')         -- NULL이면 기본값
NULLIF(col, '')                  -- 빈 문자열이면 NULL
```

### 배열/맵
```sql
-- ARRAY
element_at(arr, 1)                -- 1-based 인덱스
cardinality(arr)                  -- 배열 길이
CROSS JOIN UNNEST(arr) AS t(item) -- 배열 펼치기

-- MAP
element_at(map_col, 'key')       -- 맵에서 값 추출
map_keys(map_col)                -- 키 목록
map_values(map_col)              -- 값 목록
```

---

## 7. Athena CLI

### 쿼리 실행
```bash
aws athena start-query-execution \
    --query-string "SELECT * FROM my_db.my_table LIMIT 10" \
    --query-execution-context Database=my_db \
    --result-configuration OutputLocation=s3://results-bucket/athena-output/ \
    --work-group primary
```

### 쿼리 상태 확인
```bash
aws athena get-query-execution \
    --query-execution-id "query-id-here"
```

### 쿼리 결과 가져오기
```bash
aws athena get-query-results \
    --query-execution-id "query-id-here" \
    --max-items 100
```

### 워크그룹 생성
```bash
aws athena create-work-group \
    --name my-workgroup \
    --configuration '{
        "ResultConfiguration": {
            "OutputLocation": "s3://results-bucket/my-workgroup/",
            "EncryptionConfiguration": {
                "EncryptionOption": "SSE_KMS",
                "KmsKey": "arn:aws:kms:us-east-1:123456789012:key/key-id"
            }
        },
        "EnforceWorkGroupConfiguration": true,
        "PublishCloudWatchMetricsEnabled": true,
        "BytesScannedCutoffPerQuery": 1073741824,
        "EngineVersion": {"SelectedEngineVersion": "Athena engine version 3"}
    }'
```

### Named Query 생성
```bash
aws athena create-named-query \
    --name "Top errors" \
    --database my_db \
    --query-string "SELECT elb_status_code, COUNT(*) FROM alb_logs WHERE elb_status_code >= 500 GROUP BY 1 ORDER BY 2 DESC LIMIT 20" \
    --work-group primary
```

### 데이터베이스 생성 (Athena SQL)
```sql
CREATE DATABASE IF NOT EXISTS my_database
LOCATION 's3://bucket/prefix/';
```

### 테이블 삭제
```sql
DROP TABLE IF EXISTS my_table;
```

### 데이터베이스 삭제
```sql
DROP DATABASE IF EXISTS my_database CASCADE;
-- CASCADE = 테이블 포함 전부 삭제
```

### VIEW 생성
```sql
CREATE OR REPLACE VIEW my_view AS
SELECT col1, col2, COUNT(*) AS cnt
FROM my_table
GROUP BY col1, col2;
```

---

## 8. 경기용 플로우

### S3 로그 분석 기본 플로우
```
1. CREATE DATABASE
2. CREATE EXTERNAL TABLE (SerDe + LOCATION + PARTITIONED BY)
3. 파티션 로드:
   - Partition Projection -> TBLPROPERTIES에 설정 (MSCK 불필요)
   - 수동 -> MSCK REPAIR TABLE 또는 ALTER TABLE ADD PARTITION
4. SELECT * FROM table LIMIT 5  <-- 반드시 확인! NULL이면 SerDe 문제
5. 분석 쿼리 실행
```

### CTAS 포맷 변환 플로우
```
1. 원본 테이블 확인 (CSV 등)
2. CTAS로 Parquet/ORC 변환 + 압축 + 파티셔닝
3. 새 테이블로 쿼리 (스캔 비용 대폭 절감)
```

### Glue Crawler 플로우
```
1. IAM Role 생성 (AWSGlueServiceRole + S3 읽기)
2. Glue Database 생성
3. Crawler 생성 (S3 타겟 + 스케줄)
4. Crawler 실행
5. Athena에서 테이블 확인 및 쿼리
```
