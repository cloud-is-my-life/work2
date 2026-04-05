# S3 Fine-grained IAM 실전 케이스

## 핵심 요약

> **⚠️ `ListBucket`은 버킷 ARN** (`arn:aws:s3:::BUCKET`), **`GetObject`는 오브젝트 ARN** (`arn:aws:s3:::BUCKET/*`) — 혼동하면 즉시 감점.

> **⚠️ `s3:prefix` 조건은 `ListBucket`에만 적용** — `GetObject`에는 Resource ARN 패턴으로 제한.

> **⚠️ Explicit Deny는 Allow보다 항상 우선** — Delete Deny + Get Allow 조합이 가장 빈출.

> **⚠️ `aws:SecureTransport` Deny 넣고 HTTP 엔드포인트 쓰면 무조건 실패** — CloudShell은 HTTPS이므로 안전.

> **⚠️ Bucket Policy(Resource-based)와 IAM Policy 동시 존재 시** — 같은 계정이면 합집합, 크로스 계정이면 교집합.

---

## 전용 Condition Key

| Condition Key | 적용 Action | 설명 |
|---|---|---|
| `s3:prefix` | `ListBucket` | 조회 가능한 prefix 제한 |
| `s3:delimiter` | `ListBucket` | delimiter 강제 |
| `s3:max-keys` | `ListBucket` | 최대 반환 키 수 제한 |
| `s3:x-amz-acl` | `PutObject`, `PutBucketAcl` | ACL 값 제한 |
| `s3:x-amz-server-side-encryption` | `PutObject` | 암호화 방식 강제 |
| `s3:x-amz-server-side-encryption-aws-kms-key-id` | `PutObject` | 특정 KMS 키 강제 |
| `s3:x-amz-storage-class` | `PutObject` | 스토리지 클래스 제한 |
| `s3:VersionId` | `GetObject`, `DeleteObject` | 특정 버전 접근 제어 |
| `s3:ExistingObjectTag/<key>` | `GetObject`, `DeleteObject` | 기존 오브젝트 태그 기반 |
| `s3:RequestObjectTag/<key>` | `PutObject` | 업로드 시 태그 강제 |
| `s3:RequestObjectTagKeys` | `PutObject` | 허용 태그 키 제한 |
| `aws:SecureTransport` | 전체 | TLS 강제 |
| `aws:SourceIp` | 전체 | IP 범위 제한 |
| `aws:SourceVpce` | 전체 | VPC Endpoint 강제 |

---

## 정책 파일

| 케이스 | 파일 | 의도 |
|---|---|---|
| Case 01 | `policies/case01-prefix-readonly-deny-delete.json` | Prefix 읽기 + 삭제 Deny + TLS 강제 |
| Case 02 | `policies/case02-abac-principaltag-prefix.json` | PrincipalTag 기반 prefix 자동 분기 |
| Case 03 | `policies/case03-enforce-sse-kms.json` | SSE-KMS 암호화 강제 업로드 |
| Case 04 | `policies/case04-deny-public-acl.json` | Public ACL 차단 |
| Case 05 | `policies/case05-ip-vpce-restriction.json` | IP/VPC Endpoint 기반 접근 제한 |
| Case 06 | `policies/case06-object-tag-based.json` | 오브젝트 태그 기반 접근 제어 |
| Case 07 | `policies/case07-bucket-policy-cross-account.json` | 크로스 계정 Bucket Policy |

---

## CloudShell 준비

```bash
export AWS_REGION="ap-northeast-2"
export ACCOUNT_ID="123456789012"
export DATA_BUCKET="YOUR_DATA_BUCKET"
export USER_NAME="mod3-s3-user"
export PROFILE_NAME="mod3-s3-user"
```

---

## 검증 예시

```bash
# Prefix listing — 성공 기대
aws s3 ls "s3://$DATA_BUCKET/reports/" --profile "$PROFILE_NAME"

# Object read — 성공 기대
aws s3 cp "s3://$DATA_BUCKET/reports/sample.txt" - --profile "$PROFILE_NAME"

# Delete — AccessDenied 기대
aws s3 rm "s3://$DATA_BUCKET/reports/sample.txt" --profile "$PROFILE_NAME"

# 다른 prefix — AccessDenied 기대
aws s3 ls "s3://$DATA_BUCKET/secret/" --profile "$PROFILE_NAME"
```

---

## 감점 방지 포인트

- `ListBucket` Resource를 오브젝트 ARN(`BUCKET/*`)으로 쓰면 오답
- `s3:prefix` 조건 누락 시 버킷 전체 리스트 가능해져 감점
- Bucket Policy에 `"Principal": "*"` 쓸 때 Condition 없으면 공개 버킷
- `s3:x-amz-server-side-encryption` 강제 시 `"StringNotEquals"` + Deny 패턴 권장
- 크로스 계정은 Bucket Policy + 상대 계정 IAM Policy 양쪽 모두 필요
