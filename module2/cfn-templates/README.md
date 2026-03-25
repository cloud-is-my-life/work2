# CloudFormation 템플릿

| 파일 | 설명 |
|------|------|
| `athena-workgroup.yaml` | 결과 버킷 + SSE-KMS + 스캔 제한이 있는 WorkGroup |
| `glue-crawler-basic.yaml` | S3 버킷 + Glue DB + IAM Role + Glue Crawler |

> YAML의 `!Ref`, `!Sub`, `!GetAtt`에 대한 에디터 경고는 CloudFormation 태그 false positive일 수 있음.
