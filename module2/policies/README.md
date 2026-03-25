# IAM 정책 모음

| 파일 | 설명 |
|------|------|
| `01-athena-minimum-query.json` | Athena 쿼리 최소 권한 |
| `02-athena-readonly.json` | Athena 읽기 전용 |
| `03-athena-workgroup-restricted.json` | 특정 워크그룹만 허용 |
| `04-glue-crawler-minimum.json` | Glue Crawler 최소 권한 |
| `05-athena-results-bucket-policy.json` | Athena 결과 버킷 정책 |
| `06-kms-key-policy-for-athena.json` | Athena 결과 암호화용 KMS 키 정책 |

> `DATA-BUCKET`, `RESULTS-BUCKET`, `REGION`, `ACCOUNT`, `WORKGROUP-NAME` 같은 placeholder는 실환경 값으로 바꿔서 사용.
