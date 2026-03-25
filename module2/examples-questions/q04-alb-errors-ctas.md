
# [예시 과제 4] ALB 5xx 분석 + Parquet 최적화 (난이도: ★★★)

## 시나리오

운영팀은 ALB Access Logs에서 최근 24시간 5xx 오류를 분석하고,
반복 조회 비용을 줄이기 위해 CTAS로 Parquet 최적화를 수행하려 한다.

---

## 요구사항

### [A] 원본 로그
- 경로: `s3://wsi-qfs-logs/AWSLogs/123456789012/elasticloadbalancing/ap-northeast-2/`
- Table: `alb_access_logs_pp`
- Projection 사용

### [B] 분석
- 최근 24시간 5xx 오류 건수 집계
- target_group_arn 기준 그룹화

### [C] 최적화
- CTAS로 Parquet 변환
- SNAPPY 압축
- day 기준 파티셔닝

---

## 채점 기준

| 항목 | 배점 |
|------|------|
| ALB DDL | 4점 |
| Projection 구성 | 3점 |
| 5xx 분석 쿼리 | 4점 |
| CTAS 최적화 | 4점 |
| **합계** | **15점** |
