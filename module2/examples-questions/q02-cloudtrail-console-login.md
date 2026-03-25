
# [예시 과제 2] CloudTrail ConsoleLogin 탐지 (난이도: ★★☆)

## 시나리오

보안팀은 최근 7일간 ConsoleLogin 이벤트를 추적하려고 한다.
CloudTrail 로그를 Athena로 조회 가능한 상태로 구성하시오.

---

## 요구사항

### [A] 로그 경로
- `s3://wsi-qfs-logs/AWSLogs/123456789012/CloudTrail/us-east-1/`

### [B] 테이블
- Table: `cloudtrail_logs_pp`
- Partition Projection 사용
- 시작 날짜: 2026-01-01

### [C] 쿼리
- 최근 7일간 `ConsoleLogin`
- 사용자명, IP, 이벤트 시간 출력
- 최신순 정렬

---

## 채점 기준

| 항목 | 배점 |
|------|------|
| DDL 생성 | 4점 |
| Projection 정확성 | 4점 |
| ConsoleLogin 쿼리 | 4점 |
| 결과 정렬 | 2점 |
| **합계** | **14점** |
