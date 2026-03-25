# AWS 로그 DDL 모음

---

| # | 로그 타입 | 파일 |
|---|-----------|------|
| 1 | CloudTrail | [01-cloudtrail.md](./01-cloudtrail.md) |
| 2 | ALB Access Logs | [02-alb-access.md](./02-alb-access.md) |
| 3 | VPC Flow Logs | [03-vpc-flow-logs.md](./03-vpc-flow-logs.md) |
| 4 | S3 Access Logs | [04-s3-access-logs.md](./04-s3-access-logs.md) |
| 5 | CloudFront Logs | [05-cloudfront.md](./05-cloudfront.md) |
| 6 | WAF Logs | [06-waf.md](./06-waf.md) |

---

## 공통 함정

> **SerDe 불일치 = NULL 값**
>
> 로그 테이블 생성 후 `SELECT * FROM table LIMIT 5;` 무조건 확인.

> **Partition Projection 쓰면 `MSCK REPAIR TABLE` 하지 마라.**

> **LOCATION 끝에 슬래시(`/`) 맞춰라.** 경로 오타가 제일 흔함.
