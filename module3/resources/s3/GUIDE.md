# S3 Fine-grained IAM 실전 가이드

> AWS Skills Competition 2026 대비. 이 문서 하나로 S3 IAM 문제는 전부 커버된다.

---

## 빈출 패턴 요약

시험에서 반복해서 나오는 패턴 7가지. 이것만 외워도 절반은 먹고 들어간다.

| 순위 | 패턴 | 핵심 키워드 |
|------|------|------------|
| 1 | Prefix 읽기 + 삭제 Deny | `s3:prefix`, `DeleteObject` Deny |
| 2 | ABAC (PrincipalTag 기반 분기) | `${aws:PrincipalTag/Team}`, Null Deny |
| 3 | 사용자별 홈 디렉토리 | `${aws:username}`, NotResource |
| 4 | MFA 없으면 삭제 차단 | `aws:MultiFactorAuthPresent`, `BoolIfExists` |
| 5 | SSE-KMS 암호화 강제 | `s3:x-amz-server-side-encryption`, StringNotEquals Deny |
| 6 | IP + TLS 복합 제한 | `aws:SourceIp`, `aws:SecureTransport` |
| 7 | 크로스 계정 Bucket Policy | Principal + 양쪽 Allow 필수 |

---

## ARN 실수 방지

S3 IAM에서 가장 많이 틀리는 부분이다. 버킷 ARN과 오브젝트 ARN을 헷갈리면 즉시 감점.

### 버킷 ARN vs 오브젝트 ARN

```
버킷 ARN:   arn:aws:s3:::BUCKET_NAME
오브젝트 ARN: arn:aws:s3:::BUCKET_NAME/*
```

### 어떤 Action에 어떤 ARN을 써야 하나

| Action | Resource ARN | 틀리면? |
|--------|-------------|---------|
| `s3:ListBucket` | `arn:aws:s3:::BUCKET` (버킷) | `InvalidBucketName` 오류 |
| `s3:GetObject` | `arn:aws:s3:::BUCKET/*` (오브젝트) | 항상 AccessDenied |
| `s3:PutObject` | `arn:aws:s3:::BUCKET/*` (오브젝트) | 항상 AccessDenied |
| `s3:DeleteObject` | `arn:aws:s3:::BUCKET/*` (오브젝트) | 항상 AccessDenied |
| `s3:GetBucketPolicy` | `arn:aws:s3:::BUCKET` (버킷) | 항상 AccessDenied |

### 자주 나오는 실수 패턴

```json
// 틀린 예 — ListBucket에 오브젝트 ARN 사용
{
  "Action": "s3:ListBucket",
  "Resource": "arn:aws:s3:::my-bucket/*"  // 오답!
}

// 맞는 예
{
  "Action": "s3:ListBucket",
  "Resource": "arn:aws:s3:::my-bucket"    // 정답
}
```

`s3:prefix` 조건은 `ListBucket`에만 동작한다. `GetObject`에 `s3:prefix` 조건을 걸어봤자 아무 효과 없다. `GetObject` 범위 제한은 Resource ARN 패턴(`BUCKET/reports/*`)으로 해야 한다.

---

## Condition 연산자 빠른 참조

### 문자열 비교

| 연산자 | 의미 | 사용 예 |
|--------|------|---------|
| `StringEquals` | 정확히 일치 | 특정 팀 태그 허용 |
| `StringNotEquals` | 일치하지 않으면 | 특정 암호화 방식 아니면 Deny |
| `StringLike` | 와일드카드(`*`, `?`) 포함 | prefix 패턴 매칭 |
| `StringNotLike` | 와일드카드 포함 불일치 | 특정 패턴 외 차단 |
| `StringEqualsIfExists` | 키가 있을 때만 비교 | 선택적 헤더 검사 |

### 숫자 비교

| 연산자 | 의미 |
|--------|------|
| `NumericLessThanEquals` | 이하 |
| `NumericGreaterThan` | 초과 |

### 불리언

| 연산자 | 의미 | 주의 |
|--------|------|------|
| `Bool` | true/false 정확히 비교 | 키 없으면 조건 미적용 |
| `BoolIfExists` | 키가 있을 때만 비교 | MFA 조건에 권장 |

### Null 체크

```json
// 키가 없으면(헤더 누락) Deny
{ "Null": { "s3:x-amz-server-side-encryption": "true" } }

// 키가 있으면(태그 설정됨) 통과
{ "Null": { "aws:PrincipalTag/Team": "false" } }
```

### ForAllValues vs ForAnyValue

- `ForAllValues:StringEquals` — 요청의 모든 값이 허용 목록 안에 있어야 함
- `ForAnyValue:StringEquals` — 요청 값 중 하나라도 허용 목록에 있으면 됨

---

## 기존 케이스 01~07 요약

### Case 01 — Prefix 읽기 전용 + 삭제 Deny + TLS 강제

`reports/` prefix만 읽기 허용. 삭제는 Explicit Deny. HTTP 차단.

핵심: `ListBucket`은 버킷 ARN + `s3:prefix` 조건, `GetObject`는 오브젝트 ARN.

### Case 02 — PrincipalTag 기반 Prefix 자동 분기 (ABAC)

`${aws:PrincipalTag/Team}` 변수로 팀별 prefix 자동 분기. 태그 없는 사용자는 Null Deny로 전면 차단.

핵심: 태그 미설정 시 변수가 빈 문자열이 되어 `home//` prefix 접근 가능해짐. Null Deny 필수.

### Case 03 — SSE-KMS 암호화 강제

`StringNotEquals` + Deny 패턴으로 지정 KMS 키 외 업로드 차단. 암호화 헤더 누락도 Null 조건으로 차단.

### Case 04 — Public ACL 차단

`s3:x-amz-acl` 조건으로 `public-read`, `public-read-write` 차단. S3 Block Public Access와 별개의 IAM 레벨 이중 방어.

### Case 05 — IP/VPC Endpoint 기반 접근 제한

`NotIpAddress` + `StringNotEquals(SourceVpce)` 조합으로 허용 IP 또는 VPC Endpoint 외 전면 차단.

### Case 06 — 오브젝트 태그 기반 접근 제어

`s3:ExistingObjectTag/Classification` 조건으로 태그 값에 따라 읽기 허용/차단. 업로드 시 태그 강제는 `s3:RequestObjectTag`.

### Case 07 — 크로스 계정 Bucket Policy

외부 계정에 prefix 읽기 권한 부여. 크로스 계정은 Bucket Policy + 상대 계정 IAM Policy 양쪽 모두 Allow 필요.

---
test
