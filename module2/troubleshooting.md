# 트러블슈팅 + 함정 체크리스트

---

## 제일 흔한 사고 TOP 10

1. **`Access Denied (Service: Amazon S3; Status Code: 403)`**
   - `s3:GetBucketLocation` 빠짐
   - 데이터 버킷만 주고 결과 버킷 권한 안 줌
   - KMS 버킷인데 `kms:Decrypt` 없음

2. **쿼리는 성공했는데 전부 NULL**
   - SerDe 틀림
   - Regex 캡처 그룹 수 != 컬럼 수
   - OpenCSVSerDe 타입 기대가 틀림

3. **`HIVE_PARTITION_SCHEMA_MISMATCH`**
   - 파티션별 스키마가 다름
   - CSV 컬럼 순서/타입이 날짜별로 달라짐

4. **`MSCK REPAIR TABLE` 안 먹힘**
   - 경로가 `key=value/` 형식 아님
   - Partition Projection 쓰는 중인데 MSCK를 시도함

5. **Athena 결과 버킷 설정 오류**
   - 결과 버킷이 다른 리전
   - workgroup enforce가 켜져 있는데 클라이언트 설정만 바꿈

6. **Glue Crawler는 성공했는데 Athena에서 이상함**
   - Crawler가 잘못된 classifier/serde로 추론
   - 컬럼 타입이 string으로 다 들어감

7. **SSE-KMS 버킷 쿼리 실패**
   - IAM에는 S3 권한 있는데 KMS 권한 없음

8. **CloudTrail / VPC Flow / CloudFront에서 예약어 오류**
   - `date`, `end` 같은 예약어 백틱 안 씀

9. **CTAS 실패**
   - `partitioned_by` 컬럼이 SELECT 맨 끝이 아님
   - output 경로에 기존 파일이 남아 있음

10. **S3 Select가 안 됨**
   - 파일 여러 개 대상으로 착각
   - GROUP BY / ORDER BY / JOIN 같은 Athena 문법을 넣음

---

## 증상별 체크

### 1. Access Denied

체크 순서:

```text
1. athena:* 권한 있는가
2. glue:Get* 권한 있는가
3. 데이터 버킷: GetObject/ListBucket/GetBucketLocation 있는가
4. 결과 버킷: PutObject/GetBucketLocation/ListBucket 있는가
5. SSE-KMS면 kms:Decrypt / kms:GenerateDataKey 있는가
6. 버킷 정책에서 Principal 막는지 확인
7. Lake Formation 추가 제어 있는지 확인
```

### 2. NULL만 나옴

```sql
SELECT * FROM my_table LIMIT 5;
```

확인 포인트:
- CSV인데 OpenCSVSerDe/LazySimpleSerDe 잘못 골랐나?
- 로그 regex의 캡처 그룹 수가 컬럼 수와 맞나?
- `skip.header.line.count` 빠졌나?
- JSON인데 실제로는 JSON Lines인지 단일 Document인지?

### 3. 파티션 안 읽힘

수동 파티션이면:
```sql
SHOW PARTITIONS my_table;
MSCK REPAIR TABLE my_table;
```

Projection이면:
```text
- SHOW PARTITIONS 비어있어도 정상
- WHERE 절에서 projected column을 제대로 줬는지 확인
- storage.location.template 경로 확인
```

### 4. CTAS 실패

```text
- external_location 경로 비어 있는지
- partitioned_by 컬럼이 SELECT 맨 끝인지
- bucket_count * partition_count <= 100 인지
- workgroup이 output location 강제하는지
```

---

## 로그 타입별 함정

### CloudTrail
- `requestparameters`, `responseelements`, `additionaleventdata`는 보통 STRING으로 두고 `json_extract_scalar()`로 뽑는 게 안전
- org-wide / multi-account면 LOCATION 범위를 너무 좁게 잡지 말 것

### ALB
- 정규식 끝 `?( .*)?` 지우면 미래 필드 추가 때 깨질 수 있음
- `target_status_code`는 string으로 두는 게 안전

### VPC Flow Logs
- `` `end` `` 백틱 필요
- default format vs custom format 다르면 컬럼 정의를 바꿔야 함

### S3 Access Logs
- 경로 구조가 환경마다 제각각이라 LOCATION부터 먼저 확인해야 함
- CloudTrail data events가 더 낫지만 문제에서 “S3 access logs”면 그대로 풀면 됨

### CloudFront
- `skip.header.line.count='2'` 빼먹지 마라
- `date` 컬럼은 예약어라 백틱 또는 큰따옴표 처리

### WAF
- 시간 파티션 형식이 `yyyy/MM/dd/HH/mm`
- log_time projection interval unit이 `minutes`

---

## 경기장 디버깅 순서

```text
1. S3 실제 경로 확인
2. CREATE TABLE 실행
3. SELECT * LIMIT 5
4. NULL/에러면 SerDe/Regex/HEADER 먼저 의심
5. 파티션 방식 확인
   - Hive 스타일이면 MSCK/ALTER
   - Projection이면 TBLPROPERTIES와 WHERE 확인
6. 결과 버킷/리전 확인
7. IAM + KMS + Bucket Policy 확인
8. 성능 문제면 CTAS로 Parquet 변환
```

---

## 경기 직전 체크리스트

- [ ] 결과 버킷 리전 동일
- [ ] `s3:GetBucketLocation` 포함
- [ ] `SELECT * LIMIT 5`로 데이터 확인
- [ ] Projection이면 `MSCK REPAIR TABLE` 안 함
- [ ] CTAS면 output 경로 비어 있음
- [ ] 예약어 백틱 처리 (`date`, `end`)
- [ ] KMS 권한 확인
- [ ] WorkGroup enforce 여부 확인
