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

## 케이스별 상세 설명

### Case 01 — Prefix 읽기 전용 + 삭제 Deny + TLS 강제

**시나리오**: 특정 prefix(`reports/`) 하위 오브젝트만 읽기 허용. 삭제는 Explicit Deny. HTTP 접근 차단.

**핵심 메커니즘**:
- Allow: `s3:GetObject` → Resource `arn:aws:s3:::BUCKET/reports/*`
- Allow: `s3:ListBucket` → Resource `arn:aws:s3:::BUCKET` + Condition `s3:prefix: "reports/"`
- Deny: `s3:DeleteObject` → Resource `*`
- Deny: `aws:SecureTransport: "false"` → 모든 Action

**허용**: `reports/` prefix 오브젝트 읽기 + 리스팅
**거부**: 삭제, 다른 prefix 접근, HTTP 요청

**주의사항**:
- `ListBucket`은 **버킷 ARN** (`arn:aws:s3:::BUCKET`), `GetObject`는 **오브젝트 ARN** (`arn:aws:s3:::BUCKET/*`) — 혼동 시 즉시 감점
- `s3:prefix` 조건 없이 `ListBucket`만 허용하면 버킷 전체 리스팅 가능
- CloudShell은 항상 HTTPS이므로 `SecureTransport` Deny는 CloudShell 검증에 영향 없음

---

### Case 02 — PrincipalTag 기반 Prefix 자동 분기 (ABAC)

**시나리오**: 하나의 정책으로 여러 팀 사용자를 관리. `PrincipalTag/Team` 값에 따라 `home/${aws:PrincipalTag/Team}/` prefix만 접근 가능.

**핵심 메커니즘**:
- Resource: `arn:aws:s3:::BUCKET/home/${aws:PrincipalTag/Team}/*`
- `s3:prefix` 조건에도 `home/${aws:PrincipalTag/Team}/` 사용
- Deny: `PrincipalTag/Team`이 `Null`이면 모든 S3 작업 거부

**허용**: `Team=analytics` 사용자 → `home/analytics/*` 접근
**거부**: `home/ops/*` 접근 시 `AccessDenied`, 태그 없는 사용자 전면 차단

**주의사항**:
- 정책 변수 `${aws:PrincipalTag/Team}`은 IAM 사용자/역할에 태그가 설정되어 있어야 동작
- 태그 미설정 시 변수가 빈 문자열로 치환 → `home//` prefix가 되어 의도치 않은 접근 가능 → `Null` Deny 필수
- 검증 시 최소 2명의 사용자(다른 팀 태그)로 교차 검증해야 점수 안정적

---

### Case 03 — SSE-KMS 암호화 강제 업로드

**시나리오**: `PutObject` 시 SSE-KMS 암호화를 사용하지 않으면 업로드 거부. 특정 KMS 키만 허용.

**핵심 메커니즘**:
- Deny: `s3:x-amz-server-side-encryption` ≠ `aws:kms` → `PutObject` 거부
- Deny: `s3:x-amz-server-side-encryption-aws-kms-key-id` ≠ `KMS_KEY_ARN` → 다른 키 사용 거부
- Deny: `s3:x-amz-server-side-encryption`가 `Null: "true"` → 암호화 헤더 누락 거부

**허용**: 지정 KMS 키로 암호화한 `PutObject`
**거부**: 암호화 없는 업로드, SSE-S3 사용, 다른 KMS 키 사용

**주의사항**:
- `StringNotEquals` + Deny 패턴 권장 (Allow에 조건 거는 것보다 확실)
- `Null` 조건으로 헤더 자체가 없는 경우도 차단해야 함 — 빠뜨리면 암호화 없이 업로드 가능
- 버킷 기본 암호화 설정과 별개 — IAM 정책은 클라이언트 요청 헤더 기준으로 평가

---

### Case 04 — Public ACL 차단

**시나리오**: `PutObject`/`PutBucketAcl` 시 `public-read`, `public-read-write` 등 공개 ACL 설정 차단.

**핵심 메커니즘**:
- Deny: `s3:x-amz-acl` ∈ [`public-read`, `public-read-write`, `authenticated-read`] → 거부

**허용**: `private` ACL 또는 ACL 미지정 업로드
**거부**: 공개 ACL 설정 시 `AccessDenied`

**주의사항**:
- S3 Block Public Access 설정과 별개로 IAM 레벨에서도 차단하는 이중 방어
- `PutBucketAcl`도 함께 Deny해야 버킷 수준 공개 ACL 변경도 차단
- `x-amz-grant-*` 헤더 기반 ACL 설정은 `s3:x-amz-acl` 조건으로 잡히지 않음 → 별도 Deny 필요할 수 있음

---

### Case 05 — IP/VPC Endpoint 기반 접근 제한

**시나리오**: 특정 IP 대역 또는 VPC Endpoint에서만 S3 접근 허용. 그 외 네트워크에서는 전면 차단.

**핵심 메커니즘**:
- Deny: `aws:SourceIp` ∉ `ALLOWED_CIDR` AND `aws:SourceVpce` ≠ `VPCE_ID` → 모든 S3 Action 거부
- `NotIpAddress` + `StringNotEquals` 조합으로 "둘 다 아니면 Deny"

**허용**: 허용 IP 대역 또는 지정 VPC Endpoint에서의 접근
**거부**: 그 외 모든 네트워크에서 `AccessDenied`

**주의사항**:
- VPC Endpoint 경유 시 `aws:SourceIp`가 설정되지 않음 → IP 조건만 쓰면 VPC 내부 접근도 차단됨
- 두 조건을 OR로 결합하려면 **별도 Deny Statement 2개** 또는 `Condition` 블록 내 AND 로직 활용
- Bucket Policy(Resource-based)에서 구현하는 것이 더 일반적 — IAM Policy에서는 사용자별 적용

---

### Case 06 — 오브젝트 태그 기반 접근 제어

**시나리오**: 오브젝트에 `Classification=Public` 태그가 있는 것만 읽기 허용. `Confidential` 태그 오브젝트는 차단.

**핵심 메커니즘**:
- Allow: `s3:GetObject` + `s3:ExistingObjectTag/Classification: "Public"`
- Deny: `s3:GetObject` + `s3:ExistingObjectTag/Classification: "Confidential"`
- 업로드 시 태그 강제: `s3:RequestObjectTag/Classification` + `Null: "true"` → Deny

**허용**: `Classification=Public` 태그 오브젝트 읽기
**거부**: `Classification=Confidential` 오브젝트 읽기, 태그 없는 오브젝트 업로드

**주의사항**:
- `s3:ExistingObjectTag`는 기존 오브젝트에만 적용 — 업로드 시점은 `s3:RequestObjectTag` 사용
- 태그 키는 대소문자 구분 — `classification` ≠ `Classification`
- `s3:GetObjectTagging` 권한이 있으면 태그 값을 먼저 확인 후 접근 가능 → 태그 조회 권한도 함께 고려

---

### Case 07 — 크로스 계정 Bucket Policy

**시나리오**: 외부 계정(`EXTERNAL_ACCOUNT_ID`)에 특정 prefix 읽기 권한 부여. Bucket Policy(Resource-based) 형태.

**핵심 메커니즘**:
- `Principal: {"AWS": "arn:aws:iam::EXTERNAL_ACCOUNT_ID:root"}`
- Allow: `s3:GetObject`, `s3:ListBucket` — prefix 제한
- Condition: `aws:PrincipalOrgID` 또는 `aws:PrincipalAccount`로 추가 제한

**허용**: 외부 계정의 IAM 엔티티가 지정 prefix 읽기
**거부**: 다른 prefix 접근, 쓰기/삭제

**주의사항**:
- 크로스 계정은 **Bucket Policy + 상대 계정 IAM Policy 양쪽 모두 Allow** 필요 (교집합)
- `Principal: "*"` 사용 시 반드시 `Condition`으로 제한 — 없으면 공개 버킷
- Organization 내부만 허용하려면 `aws:PrincipalOrgID` 조건 추가 권장
- 외부 계정이 KMS 암호화 오브젝트를 읽으려면 KMS Key Policy에도 해당 계정 허용 필요

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
