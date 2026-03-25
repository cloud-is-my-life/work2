# S3 Select 레퍼런스

---

> ⚠️ S3 Select는 2026년 기준 **신규 고객 사용 불가**. 기존 고객만 사용 가능. 경기에서 나올 가능성은 낮지만 알아두면 좋음.

---

## 핵심 요약

- **파일 1개만** 쿼리 가능 (JOIN 불가)
- SELECT, WHERE, LIMIT만 지원. **GROUP BY, ORDER BY, JOIN, 서브쿼리 전부 불가**
- 입력: CSV, JSON, Parquet / 출력: CSV, JSON만 (**Parquet 출력 불가**)
- 테이블명은 항상 `S3Object`
- CSV 헤더 사용하려면 `FileHeaderInfo: USE`
- JSON은 `DOCUMENT` (단일 문서) vs `LINES` (줄 단위)

---

## 1. CLI 기본 문법

```bash
aws s3api select-object-content \
  --bucket BUCKET \
  --key KEY \
  --expression "SQL_QUERY" \
  --expression-type SQL \
  --input-serialization 'INPUT_JSON' \
  --output-serialization 'OUTPUT_JSON' \
  output_file
```

---

## 2. CSV 쿼리

### 헤더 있는 CSV
```bash
aws s3api select-object-content \
  --bucket my-bucket \
  --key data/sales.csv \
  --expression "SELECT s.name, s.amount FROM S3Object s WHERE CAST(s.amount AS FLOAT) > 1000" \
  --expression-type SQL \
  --input-serialization '{"CSV": {"FileHeaderInfo": "USE"}, "CompressionType": "NONE"}' \
  --output-serialization '{"CSV": {}}' \
  output.csv
```

### 헤더 없는 CSV (위치 기반)
```bash
aws s3api select-object-content \
  --bucket my-bucket \
  --key data/raw.csv \
  --expression "SELECT _1, _3 FROM S3Object WHERE _2 > '100'" \
  --expression-type SQL \
  --input-serialization '{"CSV": {"FileHeaderInfo": "NONE"}, "CompressionType": "NONE"}' \
  --output-serialization '{"CSV": {}}' \
  output.csv
```

### GZIP 압축 CSV
```bash
aws s3api select-object-content \
  --bucket my-bucket \
  --key data/compressed.csv.gz \
  --expression "SELECT * FROM S3Object s WHERE s.status = 'ERROR'" \
  --expression-type SQL \
  --input-serialization '{"CSV": {"FileHeaderInfo": "USE"}, "CompressionType": "GZIP"}' \
  --output-serialization '{"CSV": {}}' \
  output.csv
```

---

## 3. JSON 쿼리

### JSON Lines (줄 단위)
```bash
aws s3api select-object-content \
  --bucket my-bucket \
  --key logs/app.jsonl \
  --expression "SELECT s.timestamp, s.level, s.message FROM S3Object s WHERE s.level = 'ERROR'" \
  --expression-type SQL \
  --input-serialization '{"JSON": {"Type": "LINES"}, "CompressionType": "NONE"}' \
  --output-serialization '{"JSON": {"RecordDelimiter": "\n"}}' \
  errors.json
```

### JSON Document (단일 문서)
```bash
aws s3api select-object-content \
  --bucket my-bucket \
  --key data/config.json \
  --expression "SELECT s.name, s.value FROM S3Object[*] s WHERE s.category = 'network'" \
  --expression-type SQL \
  --input-serialization '{"JSON": {"Type": "DOCUMENT"}}' \
  --output-serialization '{"JSON": {}}' \
  output.json
```

---

## 4. Parquet 쿼리

```bash
aws s3api select-object-content \
  --bucket my-bucket \
  --key data/events.parquet \
  --expression "SELECT event_id, event_type FROM S3Object WHERE event_type = 'LOGIN' LIMIT 1000" \
  --expression-type SQL \
  --input-serialization '{"Parquet": {}}' \
  --output-serialization '{"CSV": {}}' \
  output.csv
```
> Parquet 입력은 옵션 없음. 빈 객체 `{}` 전달.
> 출력은 CSV 또는 JSON만 가능.

---

## 5. InputSerialization 옵션

### CSV
| 필드 | 값 | 기본값 |
|------|-----|--------|
| `FileHeaderInfo` | `USE` / `IGNORE` / `NONE` | - |
| `Comments` | 단일 문자 | `#` |
| `QuoteEscapeCharacter` | 단일 문자 | `"` |
| `RecordDelimiter` | 문자열 | `\n` |
| `FieldDelimiter` | 단일 문자 | `,` |
| `QuoteCharacter` | 단일 문자 | `"` |
| `AllowQuotedRecordDelimiter` | boolean | `false` |

### JSON
| 필드 | 값 |
|------|-----|
| `Type` | `DOCUMENT` (단일 JSON) / `LINES` (줄 단위 JSON) |

### Parquet
옵션 없음. `{"Parquet": {}}`

### CompressionType (InputSerialization 레벨)
| 값 | CSV/JSON | Parquet |
|-----|----------|---------|
| `NONE` | O | - |
| `GZIP` | O | 컬럼 압축만 |
| `BZIP2` | O | - |

---

## 6. OutputSerialization 옵션

### CSV
| 필드 | 값 | 기본값 |
|------|-----|--------|
| `QuoteFields` | `ALWAYS` / `ASNEEDED` | `ASNEEDED` |
| `QuoteEscapeCharacter` | 단일 문자 | `"` |
| `RecordDelimiter` | 문자열 | `\n` |
| `FieldDelimiter` | 단일 문자 | `,` |
| `QuoteCharacter` | 단일 문자 | `"` |

### JSON
| 필드 | 값 | 기본값 |
|------|-----|--------|
| `RecordDelimiter` | 문자열 | `\n` |

---

## 7. SQL 문법

### 지원되는 것
```sql
SELECT col1, col2 FROM S3Object
SELECT * FROM S3Object s WHERE s.col > 100
SELECT COUNT(*), SUM(CAST(s.amount AS FLOAT)) FROM S3Object s
SELECT * FROM S3Object LIMIT 100
```

### 지원 안 되는 것
- `ORDER BY` / `GROUP BY` / `HAVING`
- `JOIN` / 서브쿼리
- `DISTINCT`
- `UNION`
- Window 함수

### 집계 함수
`COUNT(*)`, `SUM()`, `AVG()`, `MIN()`, `MAX()`

### 조건
```sql
WHERE col = 'value'
WHERE col > 100
WHERE col BETWEEN 10 AND 20
WHERE col IN ('a', 'b', 'c')
WHERE col LIKE 'prefix%'
WHERE col IS NULL / IS NOT NULL
```

### 문자열 함수
`CHAR_LENGTH()`, `LOWER()`, `UPPER()`, `TRIM()`, `SUBSTRING(str FROM pos FOR len)`

### 날짜 함수
`DATE_ADD(part, qty, ts)`, `DATE_DIFF(part, ts1, ts2)`, `EXTRACT(part FROM ts)`, `TO_STRING(ts, fmt)`, `TO_TIMESTAMP(str)`, `UTCNOW()`

### 타입 변환
```sql
CAST(col AS INT)
CAST(col AS FLOAT)
CAST(col AS TIMESTAMP)
CAST('2026-03-24T00:00:00Z' AS TIMESTAMP)
```

### CASE / COALESCE / NULLIF
```sql
CASE WHEN col > 100 THEN 'high' ELSE 'low' END
COALESCE(col, 'default')
NULLIF(col, '')
```

---

## 8. 제한사항

| 항목 | 제한 |
|------|------|
| 쿼리 대상 | 파일 1개 |
| 최대 SQL 길이 | 256 KB |
| 최대 레코드 크기 | 1 MB |
| 최대 컬럼 수 | ~256 (1MB 레코드 제한) |
| Parquet 행 그룹 | 비압축 512 MB |
| 출력 포맷 | CSV, JSON만 (Parquet 불가) |
| 지원 스토리지 클래스 | STANDARD, STANDARD_IA, ONEZONE_IA, INTELLIGENT_TIERING (활성 티어만) |
| 미지원 | GLACIER, DEEP_ARCHIVE, Directory 버킷, Outposts |

---

## 9. S3 Select vs Athena

| | S3 Select | Athena |
|---|-----------|--------|
| 대상 | 파일 1개 | 여러 파일, 전체 prefix |
| SQL | 부분 (SELECT/WHERE/LIMIT) | 전체 ANSI SQL |
| JOIN | X | O |
| GROUP BY | X | O |
| ORDER BY | X | O |
| 스키마 | 인라인 (schema-on-read) | Glue Data Catalog |
| 비용 | $0.002/GB 스캔 + $0.0007/GB 반환 | $5/TB 스캔 |
| 지연 | 매우 낮음 (단일 파일 스트리밍) | 높음 (쿼리 엔진 시작) |
| 용도 | 단일 파일 필터링, Lambda 연동 | 대규모 분석, 로그 분석 |
