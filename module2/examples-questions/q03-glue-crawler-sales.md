
# [예시 과제 3] Glue Crawler 기반 카탈로그 자동화 (난이도: ★★☆)

## 시나리오

데이터팀은 매일 S3에 적재되는 CSV 매출 파일을 자동으로 카탈로그에 반영하려 한다.
Glue Crawler를 구성하고 Athena로 Top 10 상품을 조회하시오.

---

## 요구사항

### [A] Glue
- Database: `wsi_auto_db`
- Crawler: `wsi-sales-crawler`
- 대상 경로: `s3://wsi-qfs-data/sales/daily/`
- 6시간마다 실행

### [B] IAM
- Glue 서비스 역할 생성
- 데이터 버킷 읽기 권한 포함

### [C] Athena
- 생성된 테이블로 상품별 총매출 집계
- 상위 10개 출력

---

## 채점 기준

| 항목 | 배점 |
|------|------|
| Glue DB 생성 | 2점 |
| IAM Role | 3점 |
| Crawler 생성 | 4점 |
| 스케줄 적용 | 2점 |
| Athena 집계 쿼리 | 4점 |
| **합계** | **15점** |
