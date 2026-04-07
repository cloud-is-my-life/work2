# Module 2: Query from S3 — Athena / Glue / S3 Select

---

## 핵심 요약 (경기장에서 이것만 기억)

> **⚠️ SerDe 불일치 = NULL 값 (에러 아님!)** 잘못된 SerDe 쓰면 쿼리는 성공하는데 전부 NULL 나옴. 에러 안 뜨니까 원인 찾기 존나 어려움. 테이블 만들고 `SELECT * LIMIT 5` 무조건 확인!

> **⚠️ s3:GetBucketLocation 빠뜨리면 Access Denied!** Athena 최소 권한에 이거 빠뜨리는 게 가장 흔한 실수. 데이터 버킷 + 결과 버킷 둘 다 필요.

> **⚠️ Partition Projection 쓰면 MSCK REPAIR TABLE 절대 불필요!** 오히려 쓰면 에러남. SHOW PARTITIONS 비어있는 게 정상.

> **⚠️ CTAS 후 MSCK REPAIR TABLE 불필요!** CTAS가 자동으로 파티션 등록함.

> **⚠️ EnforceWorkGroupConfiguration = true면 클라이언트 설정 무시!** 출력 위치, 암호화 전부 워크그룹 설정이 이김.

- Athena 테이블 = Glue Data Catalog 테이블. **같은 것.** Athena에서 CREATE TABLE 하면 Glue에 등록됨.
- Athena 결과 버킷은 **같은 리전**이어야 함. 다른 리전이면 에러.
- CloudTrail SerDe: `org.apache.hive.hcatalog.data.JsonSerDe` 권장 (최신 필드 지원). `CloudTrailSerde`는 구버전.
- ALB 로그 RegexSerDe: 끝에 `?( .*)?` 패턴 유지 — 미래 필드 추가 대비.
- `date`, `end` 같은 예약어는 **백틱(\`)으로 감싸야 함.**
- S3 Select: **파일 1개만** 쿼리 가능. JOIN/GROUP BY/ORDER BY 불가. 간단한 필터링용.
- Glue Crawler Role 이름은 **`AWSGlueServiceRole`로 시작**해야 매니지드 정책 조건 매칭됨.
- CTAS `partitioned_by` 컬럼은 **SELECT 맨 끝**에 와야 함.
- Parquet/ORC = 컬럼형 → 스캔 비용 절감. CSV 대비 최대 90% 절약.

---

## 목차

| # | 주제 | 바로가기 |
|---|------|----------|
| 1 | Athena DDL/DML/CLI 도우미 | [cheatsheet.md](./cheatsheet.md) |
| 2 | AWS 로그 분석 DDL 6종 | [log-ddl/](./log-ddl/) |
| 3 | Glue Data Catalog + Crawler | [glue-guide.md](./glue-guide.md) |
| 4 | S3 Select 레퍼런스 | [s3-select-guide.md](./s3-select-guide.md) |
| 5 | IAM 정책 + 크로스계정 + KMS | [iam-guide.md](./iam-guide.md) |
| 6 | 트러블슈팅 + 함정 체크리스트 | [troubleshooting.md](./troubleshooting.md) |
| 7 | IAM 정책 JSON 파일 | [policies/](./policies/) |
| 8 | CloudFormation 템플릿 | [cfn-templates/](./cfn-templates/) |
| 9 | 예시 과제 (난이도별) | [examples-questions/](./examples-questions/) |
| 10 | 채점 대응 플레이북 (CloudShell) | [grading-playbook.md](./grading-playbook.md) |

---

## 빠른 레퍼런스 (외우기 어려운 것만)

### SerDe 클래스명

| 포맷 | SerDe 클래스 |
|------|-------------|
| CSV (단순) | `org.apache.hadoop.hive.serde2.lazy.LazySimpleSerDe` |
| CSV (따옴표) | `org.apache.hadoop.hive.serde2.OpenCSVSerde` |
| JSON | `org.openx.data.jsonserde.JsonSerDe` |
| Regex | `org.apache.hadoop.hive.serde2.RegexSerDe` |
| Parquet | `org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe` |
| ORC | `org.apache.hadoop.hive.ql.io.orc.OrcSerde` |
| CloudTrail | `org.apache.hive.hcatalog.data.JsonSerDe` (권장) |
| CloudTrail (구) | `com.amazon.emr.hive.serde.CloudTrailSerde` |
| Grok | `com.amazonaws.glue.serde.GrokSerDe` |

### InputFormat / OutputFormat

| 포맷 | InputFormat | OutputFormat |
|------|-------------|--------------|
| Text/CSV/JSON | `org.apache.hadoop.mapred.TextInputFormat` | `org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat` |
| Parquet | `org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat` | `org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat` |
| ORC | `org.apache.hadoop.hive.ql.io.orc.OrcInputFormat` | `org.apache.hadoop.hive.ql.io.orc.OrcOutputFormat` |
| CloudTrail | `com.amazon.emr.cloudtrail.CloudTrailInputFormat` | `org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat` |

### Partition Projection 타입

| 타입 | 용도 | 필수 속성 |
|------|------|-----------|
| `enum` | 고정 목록 (리전, 계정ID) | `.values` = 쉼표 구분 목록 |
| `integer` | 숫자 범위 (연/월/일) | `.range` = `min,max` |
| `date` | 날짜 범위 | `.range`, `.format`, `.interval`, `.interval.unit` |
| `injected` | WHERE절에서 값 제공 필수 | 없음 (WHERE 필수) |

### CTAS WITH 속성

| 속성 | 값 |
|------|-----|
| `format` | `'PARQUET'`, `'ORC'`, `'AVRO'`, `'JSON'`, `'TEXTFILE'` |
| `write_compression` | `'SNAPPY'`, `'GZIP'`, `'ZSTD'`, `'LZ4'`, `'ZLIB'`, `'NONE'` |
| `parquet_compression` | `'SNAPPY'` (기본 GZIP) |
| `external_location` | `'s3://bucket/prefix/'` |
| `partitioned_by` | `ARRAY['col1', 'col2']` — SELECT 맨 끝에 배치 |
| `bucketed_by` | `ARRAY['col']` |
| `bucket_count` | 정수 (파티션×버킷 ≤ 100) |

### Athena 암호화 옵션

| 옵션 | 설명 | 추가 권한 |
|------|------|-----------|
| `SSE_S3` | S3 관리 키 | 없음 |
| `SSE_KMS` | KMS 키 | `kms:GenerateDataKey`, `kms:Decrypt` |
| `CSE_KMS` | 클라이언트 측 KMS | `kms:GenerateDataKey`, `kms:Decrypt` |

### AWS 로그 S3 경로 패턴

| 로그 | S3 경로 |
|------|---------|
| CloudTrail | `s3://bucket/AWSLogs/{account}/CloudTrail/{region}/{yyyy}/{MM}/{dd}/` |
| ALB | `s3://bucket/AWSLogs/{account}/elasticloadbalancing/{region}/{yyyy}/{MM}/{dd}/` |
| VPC Flow | `s3://bucket/AWSLogs/{account}/vpcflowlogs/{region}/{yyyy}/{MM}/{dd}/` |
| S3 Access | `s3://bucket/prefix/` (날짜 구조 없음, 또는 커스텀) |
| CloudFront | `s3://bucket/prefix/{dist-id}.{yyyy}-{MM}-{dd}-{HH}.{unique}.gz` |
| WAF | `s3://bucket/AWSLogs/{account}/WAFLogs/{source}/{webacl}/{yyyy}/{MM}/{dd}/{HH}/{mm}/` |

### BytesScannedCutoffPerQuery 변환

| 제한 | 바이트 값 |
|------|-----------|
| 10 MB | `10485760` |
| 100 MB | `104857600` |
| 1 GB | `1073741824` |
| 10 GB | `10737418240` |
| 100 GB | `107374182400` |
