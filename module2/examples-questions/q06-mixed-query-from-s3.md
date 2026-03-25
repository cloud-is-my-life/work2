
# [예시 과제 6] Query from S3 종합 실전 (난이도: ★★★★)

## 시나리오

심사위원은 "Query from S3" 주제로 서비스 선택, 비용 최적화, IAM, 분석 결과까지 한 번에 본다.
Athena와 S3 Select를 적절히 구분해 사용하고, 반복 조회 대상은 최적화까지 수행하시오.

---

## 요구사항

### [A] 단일 대용량 JSON 파일
- `s3://wsi-qfs-data/raw/huge.jsonl`
- S3 Select로 `level='ERROR'` 인 레코드만 추출

### [B] 반복 조회 대상 CSV 데이터셋
- Athena External Table 생성
- CTAS로 Parquet 변환 + SNAPPY 압축

### [C] 운영 로그 분석
- CloudTrail / ALB / VPC Flow 중 1종 선택
- Projection 기반 테이블 구성
- 최근 7일 이상 조건 분석 쿼리 2개 작성

### [D] 보안
- 최소 권한 IAM 정책 작성
- 결과 버킷 SSL 강제 버킷 정책 적용

---

## 채점 기준

| 항목 | 배점 |
|------|------|
| S3 Select 적절성 | 3점 |
| Athena DDL | 4점 |
| CTAS 최적화 | 4점 |
| 로그 분석 쿼리 2개 | 4점 |
| IAM 최소 권한 | 3점 |
| 결과 버킷 정책 | 2점 |
| **합계** | **20점** |
