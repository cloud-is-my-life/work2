# Module 3 정책 JSON 모음

CloudShell에서 바로 쓰기 위한 fine-grained IAM 정책 템플릿.

| 파일 | 용도 |
|---|---|
| `q01-s3-prefix-readonly-with-explicit-deny.json` | reports Prefix 읽기 + 삭제 Deny + TLS 강제 |
| `q02-abac-principal-tag-team.json` | PrincipalTag `Team` 기반 ABAC |
| `q03-boundary-readonly-s3.json` | Delegated IAM 과제용 Permissions Boundary |
| `q03-delegate-policy-template.json` | Boundary 강제 + Admin 정책 부착 차단 |

---

## 사용 방법 (예시)

```bash
export ACCOUNT_ID="123456789012"
export DATA_BUCKET="YOUR_DATA_BUCKET"
export BOUNDARY_ARN="arn:aws:iam::$ACCOUNT_ID:policy/MOD3_Q03_BOUNDARY_POLICY"

cp module3/policies/q01-s3-prefix-readonly-with-explicit-deny.json /tmp/policy.json
sed -i "s/YOUR_DATA_BUCKET/$DATA_BUCKET/g" /tmp/policy.json
```
