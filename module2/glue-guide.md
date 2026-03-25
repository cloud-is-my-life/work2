# Glue Data Catalog + Crawler 가이드

---

## 핵심 개념

- **Glue Data Catalog = Athena의 메타스토어.** Athena에서 CREATE TABLE 하면 Glue에 자동 등록.
- Glue Database = Athena Database (같은 것)
- Glue Table = Athena Table (같은 것)
- Crawler는 S3 데이터를 스캔해서 **자동으로 스키마 추론 + 테이블 생성/업데이트**

> ⚠️ Crawler Role 이름은 **`AWSGlueServiceRole`로 시작**해야 매니지드 정책 조건 매칭됨!

---

## 1. Database 관리

### CLI로 생성
```bash
aws glue create-database \
  --database-input '{
    "Name": "my_database",
    "Description": "My analytics database",
    "LocationUri": "s3://my-bucket/prefix/"
  }'
```

### CLI로 조회
```bash
aws glue get-database --name my_database
aws glue get-databases
```

### CLI로 삭제
```bash
aws glue delete-database --name my_database
```

### Athena SQL로 생성
```sql
CREATE DATABASE IF NOT EXISTS my_database
LOCATION 's3://my-bucket/prefix/';
```

---

## 2. Table 관리 (CLI)

### CLI로 테이블 생성 (CSV 예시)
```bash
aws glue create-table \
  --database-name my_database \
  --table-input '{
    "Name": "my_csv_table",
    "TableType": "EXTERNAL_TABLE",
    "Parameters": {
      "EXTERNAL": "TRUE",
      "classification": "csv",
      "skip.header.line.count": "1"
    },
    "StorageDescriptor": {
      "Columns": [
        {"Name": "id", "Type": "string"},
        {"Name": "name", "Type": "string"},
        {"Name": "amount", "Type": "double"}
      ],
      "Location": "s3://my-bucket/csv-data/",
      "InputFormat": "org.apache.hadoop.mapred.TextInputFormat",
      "OutputFormat": "org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat",
      "Compressed": false,
      "SerdeInfo": {
        "SerializationLibrary": "org.apache.hadoop.hive.serde2.lazy.LazySimpleSerDe",
        "Parameters": {"field.delim": ",", "serialization.format": ","}
      }
    },
    "PartitionKeys": [
      {"Name": "year", "Type": "string"},
      {"Name": "month", "Type": "string"}
    ]
  }'
```

### CLI로 테이블 조회
```bash
aws glue get-table --database-name my_database --name my_csv_table
aws glue get-tables --database-name my_database
```

### CLI로 테이블 삭제
```bash
aws glue delete-table --database-name my_database --name my_csv_table
```

### 자주 쓰는 InputFormat / OutputFormat / SerDe 조합

| 포맷 | InputFormat | OutputFormat | SerializationLibrary |
|------|-------------|--------------|----------------------|
| CSV | `o.a.h.mapred.TextInputFormat` | `o.a.h.hive.ql.io.HiveIgnoreKeyTextOutputFormat` | `o.a.h.hive.serde2.lazy.LazySimpleSerDe` |
| JSON | `o.a.h.mapred.TextInputFormat` | `o.a.h.hive.ql.io.HiveIgnoreKeyTextOutputFormat` | `org.openx.data.jsonserde.JsonSerDe` |
| Parquet | `o.a.h.hive.ql.io.parquet.MapredParquetInputFormat` | `o.a.h.hive.ql.io.parquet.MapredParquetOutputFormat` | `o.a.h.hive.ql.io.parquet.serde.ParquetHiveSerDe` |
| ORC | `o.a.h.hive.ql.io.orc.OrcInputFormat` | `o.a.h.hive.ql.io.orc.OrcOutputFormat` | `o.a.h.hive.ql.io.orc.OrcSerde` |

> `o.a.h` = `org.apache.hadoop` 축약

---

## 3. Crawler

### CLI로 Crawler 생성
```bash
aws glue create-crawler \
  --name my-crawler \
  --role arn:aws:iam::123456789012:role/AWSGlueServiceRole-Default \
  --database-name my_database \
  --targets '{
    "S3Targets": [
      {
        "Path": "s3://my-bucket/data/",
        "Exclusions": ["**.tmp", "**.log", "_temporary/**"]
      }
    ]
  }' \
  --table-prefix "raw_" \
  --schema-change-policy '{
    "UpdateBehavior": "UPDATE_IN_DATABASE",
    "DeleteBehavior": "LOG"
  }' \
  --recrawl-policy '{"RecrawlBehavior": "CRAWL_NEW_FOLDERS_ONLY"}'
```

### 스케줄 추가
```bash
aws glue create-crawler \
  --name scheduled-crawler \
  --role arn:aws:iam::123456789012:role/AWSGlueServiceRole-Default \
  --database-name my_database \
  --targets '{"S3Targets": [{"Path": "s3://my-bucket/data/"}]}' \
  --schedule "cron(0 */6 * * ? *)"
```

> Glue cron 형식: `cron(분 시 일 월 요일 연)` — 6필드.
> - 매 6시간: `cron(0 */6 * * ? *)`
> - 매일 자정: `cron(0 0 * * ? *)`
> - 매주 월요일 9시: `cron(0 9 ? * MON *)`

### Crawler 실행/상태 확인
```bash
aws glue start-crawler --name my-crawler
aws glue get-crawler --name my-crawler
aws glue stop-crawler --name my-crawler
```

### Crawler 삭제
```bash
aws glue delete-crawler --name my-crawler
```

### SchemaChangePolicy 값

| 속성 | 값 | 설명 |
|------|-----|------|
| UpdateBehavior | `UPDATE_IN_DATABASE` | 스키마 변경 시 테이블 업데이트 |
| UpdateBehavior | `LOG` | 변경 로그만 남김 (테이블 안 바꿈) |
| DeleteBehavior | `LOG` | 삭제된 객체 로그만 |
| DeleteBehavior | `DELETE_FROM_DATABASE` | 테이블/파티션 삭제 |
| DeleteBehavior | `DEPRECATE_IN_DATABASE` | deprecated 마킹 |

### RecrawlPolicy 값

| 값 | 설명 |
|-----|------|
| `CRAWL_EVERYTHING` | 전체 재크롤 (기존 파티션도 업데이트) |
| `CRAWL_NEW_FOLDERS_ONLY` | 새 S3 폴더만 (빠름, 기본 추천) |
| `CRAWL_EVENT_MODE` | S3 이벤트 기반 (SQS 필요) |

### S3Target 전체 속성
```json
{
  "Path": "s3://bucket/prefix/",
  "Exclusions": ["**.tmp"],
  "ConnectionName": "string",
  "SampleSize": 10,
  "EventQueueArn": "arn:aws:sqs:region:account:queue",
  "DlqEventQueueArn": "arn:aws:sqs:region:account:dlq"
}
```

---

## 4. Classifier (분류기)

Crawler가 데이터 포맷을 자동 감지 못할 때 커스텀 분류기 사용.

### CSV Classifier
```bash
aws glue create-classifier \
  --csv-classifier '{
    "Name": "my-csv-classifier",
    "Delimiter": ",",
    "QuoteSymbol": "\"",
    "ContainsHeader": "PRESENT",
    "Header": ["col1", "col2", "col3"],
    "DisableValueTrimming": false,
    "AllowSingleColumn": false
  }'
```

### JSON Classifier
```bash
aws glue create-classifier \
  --json-classifier '{
    "Name": "my-json-classifier",
    "JsonPath": "$[*]"
  }'
```

### Grok Classifier
```bash
aws glue create-classifier \
  --grok-classifier '{
    "Name": "my-grok-classifier",
    "Classification": "custom-log",
    "GrokPattern": "%{TIMESTAMP_ISO8601:timestamp} %{LOGLEVEL:level} %{GREEDYDATA:message}",
    "CustomPatterns": "MYPATTERN [a-z]+"
  }'
```

### XML Classifier
```bash
aws glue create-classifier \
  --xml-classifier '{
    "Name": "my-xml-classifier",
    "Classification": "xml",
    "RowTag": "record"
  }'
```

### ContainsHeader 값
- `PRESENT` — 헤더 있음
- `ABSENT` — 헤더 없음
- `UNKNOWN` — 자동 감지

---

## 5. Data Catalog 설정

### 리소스 정책 (크로스계정 접근)
```bash
aws glue put-resource-policy \
  --policy-in-json '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"AWS": "arn:aws:iam::111122223333:root"},
      "Action": ["glue:GetTable", "glue:GetDatabase", "glue:GetPartition", "glue:GetPartitions", "glue:BatchGetPartition"],
      "Resource": [
        "arn:aws:glue:us-east-1:123456789012:catalog",
        "arn:aws:glue:us-east-1:123456789012:database/*",
        "arn:aws:glue:us-east-1:123456789012:table/*/*"
      ]
    }]
  }'
```

### 암호화 설정
```bash
aws glue put-data-catalog-encryption-settings \
  --data-catalog-encryption-settings '{
    "EncryptionAtRest": {
      "CatalogEncryptionMode": "SSE-KMS",
      "SseAwsKmsKeyId": "arn:aws:kms:us-east-1:123456789012:key/key-id"
    },
    "ConnectionPasswordEncryption": {
      "ReturnConnectionPasswordEncrypted": true,
      "AwsKmsKeyId": "arn:aws:kms:us-east-1:123456789012:key/key-id"
    }
  }'
```

---

## 6. CloudFormation

### AWS::Glue::Database
```yaml
MyGlueDatabase:
  Type: AWS::Glue::Database
  Properties:
    CatalogId: !Ref AWS::AccountId
    DatabaseInput:
      Name: my_database
      Description: "Analytics database"
      LocationUri: !Sub "s3://${DataBucket}/prefix/"
```

### AWS::Glue::Table (JSON 예시)
```yaml
MyGlueTable:
  Type: AWS::Glue::Table
  Properties:
    CatalogId: !Ref AWS::AccountId
    DatabaseName: !Ref MyGlueDatabase
    TableInput:
      Name: json_events
      TableType: EXTERNAL_TABLE
      Parameters:
        EXTERNAL: "TRUE"
        classification: json
      StorageDescriptor:
        Columns:
          - Name: event_id
            Type: string
          - Name: timestamp
            Type: string
          - Name: payload
            Type: string
        Location: !Sub "s3://${DataBucket}/events/"
        InputFormat: org.apache.hadoop.mapred.TextInputFormat
        OutputFormat: org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat
        SerdeInfo:
          SerializationLibrary: org.openx.data.jsonserde.JsonSerDe
      PartitionKeys:
        - Name: year
          Type: string
        - Name: month
          Type: string
```

### AWS::Glue::Crawler
```yaml
GlueCrawler:
  Type: AWS::Glue::Crawler
  Properties:
    Name: my-crawler
    Role: !GetAtt GlueCrawlerRole.Arn
    DatabaseName: !Ref MyGlueDatabase
    TablePrefix: "raw_"
    Targets:
      S3Targets:
        - Path: !Sub "s3://${DataBucket}/data/"
          Exclusions:
            - "**.tmp"
    Schedule:
      ScheduleExpression: "cron(0 */6 * * ? *)"
    SchemaChangePolicy:
      UpdateBehavior: UPDATE_IN_DATABASE
      DeleteBehavior: LOG
    RecrawlPolicy:
      RecrawlBehavior: CRAWL_NEW_FOLDERS_ONLY
```

### AWS::Glue::Classifier (4종)
```yaml
MyCsvClassifier:
  Type: AWS::Glue::Classifier
  Properties:
    CsvClassifier:
      Name: my-csv-classifier
      Delimiter: ","
      QuoteSymbol: "\""
      ContainsHeader: PRESENT
      Header:
        - col1
        - col2

MyJsonClassifier:
  Type: AWS::Glue::Classifier
  Properties:
    JsonClassifier:
      Name: my-json-classifier
      JsonPath: "$[*]"

MyGrokClassifier:
  Type: AWS::Glue::Classifier
  Properties:
    GrokClassifier:
      Name: my-grok-classifier
      Classification: custom-log
      GrokPattern: "%{TIMESTAMP_ISO8601:timestamp} %{LOGLEVEL:level} %{GREEDYDATA:message}"

MyXmlClassifier:
  Type: AWS::Glue::Classifier
  Properties:
    XMLClassifier:
      Name: my-xml-classifier
      Classification: xml
      RowTag: record
```

---

## 7. Crawler IAM Role

### Trust Policy
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "glue.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}
```

### 최소 권한 정책
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "GlueCatalogAccess",
      "Effect": "Allow",
      "Action": [
        "glue:GetDatabase", "glue:GetDatabases",
        "glue:CreateTable", "glue:UpdateTable",
        "glue:GetTable", "glue:GetTables",
        "glue:CreatePartition", "glue:BatchCreatePartition",
        "glue:UpdatePartition", "glue:GetPartition",
        "glue:GetPartitions", "glue:BatchGetPartition",
        "glue:ImportCatalogToGlue"
      ],
      "Resource": "*"
    },
    {
      "Sid": "S3DataAccess",
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:ListBucket", "s3:GetBucketLocation"],
      "Resource": [
        "arn:aws:s3:::my-data-bucket",
        "arn:aws:s3:::my-data-bucket/*"
      ]
    },
    {
      "Sid": "CloudWatchLogs",
      "Effect": "Allow",
      "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
      "Resource": "arn:aws:logs:*:*:*"
    }
  ]
}
```

> 또는 매니지드 정책 `AWSGlueServiceRole` 연결 (Role 이름이 `AWSGlueServiceRole`로 시작해야 함)
