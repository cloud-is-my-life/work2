# SSM Parameter Store Fine-grained IAM 실전 케이스

## 핵심 요약

> **⚠️ `DescribeParameters`는 리소스 수준 제어 불가** — 항상 `"Resource": "*"` 필요.

> **⚠️ 경로 접근은 하위 전체 포함** — `/a` 권한이면 `/a/b/c`도 자동 접근 가능.

> **⚠️ `GetParameterHistory`로 SecureString 값 우회 가능** — GetParameter Deny해도 History로 노출.

> **⚠️ 기본 `aws/ssm` 키는 계정 내 모든 IAM에 Decrypt 허용** — SecureString 제한하려면 반드시 CMK 사용.

> **⚠️ Label은 IAM 조건키 없음** — 레이블 기반 접근 제어는 IAM으로 불가능.

> **⚠️ 크로스 계정 공유는 Advanced tier만 가능** — Standard 파라미터는 공유 불가.

---

## 전용 Condition Key

| Condition Key | 적용 Action | 설명 |
|---|---|---|
| `ssm:Overwrite` | `PutParameter` | 기존 파라미터 덮어쓰기 제어 |
| `ssm:Recursive` | `GetParametersByPath` | 재귀 경로 조회 제어 |
| `ssm:Policies` | `PutParameter` | 파라미터 정책 첨부 제어 |
| `aws:ResourceTag/${TagKey}` | Get/Delete/Label 등 | 기존 리소스 태그 기반 |
| `aws:RequestTag/${TagKey}` | Put/AddTags 등 | 생성 시 태그 강제 |

---

## ARN 패턴

```
# 특정 파라미터
arn:aws:ssm:REGION:ACCOUNT_ID:parameter/app/prod/db/host

# 경로 와일드카드
arn:aws:ssm:REGION:ACCOUNT_ID:parameter/app/prod/*

# 전체
arn:aws:ssm:REGION:ACCOUNT_ID:parameter/*
```

> **주의**: ARN에 `/parameter` 접두사가 포함됨. 파라미터 이름이 `/app/prod/key`이면 ARN은 `parameter/app/prod/key`.

---

## 정책 파일

| 케이스 | 파일 | 의도 |
|---|---|---|
| Case 01 | `policies/case01-path-readonly.json` | 경로 기반 읽기 전용 |
| Case 02 | `policies/case02-deny-overwrite-delete.json` | 덮어쓰기 + 삭제 차단 |
| Case 03 | `policies/case03-deny-recursive-sensitive.json` | 민감 경로 재귀 조회 차단 |
| Case 04 | `policies/case04-enforce-cmk-securestring.json` | CMK 강제 + 기본 키 차단 |
| Case 05 | `policies/case05-abac-tag-based.json` | 태그 기반 ABAC |

---

## 케이스별 상세 설명

### Case 01 — 경로 기반 읽기 전용

**시나리오**: `/app/prod/` 경로 하위 파라미터만 읽기 허용. 쓰기/삭제 불가.

**핵심 메커니즘**:
- Allow: `ssm:GetParameter`, `ssm:GetParameters`, `ssm:GetParametersByPath` → Resource `arn:aws:ssm:REGION:ACCOUNT:parameter/app/prod/*`
- Allow: `ssm:DescribeParameters` → Resource `*` (리소스 수준 제어 불가)

**허용**: `/app/prod/db/host`, `/app/prod/api/key` 등 읽기
**거부**: `/app/dev/*` 접근, `PutParameter`, `DeleteParameter`

**주의사항**:
- ARN에 `/parameter` 접두사 포함 — 파라미터 이름 `/app/prod/key`의 ARN은 `parameter/app/prod/key`
- `DescribeParameters`는 `Resource: "*"` 필수 — 특정 ARN 지정하면 오류
- `GetParameterHistory`도 값을 반환하므로 읽기 제한 시 함께 허용/차단 결정 필요

---

### Case 02 — 덮어쓰기 + 삭제 차단

**시나리오**: 파라미터 읽기와 신규 생성은 허용하되, 기존 파라미터 덮어쓰기(`Overwrite`)와 삭제는 차단.

**핵심 메커니즘**:
- Deny: `ssm:PutParameter` + `ssm:Overwrite: "true"` → 기존 파라미터 덮어쓰기 차단
- Deny: `ssm:DeleteParameter`, `ssm:DeleteParameters` → 삭제 차단

**허용**: 신규 파라미터 생성 (`Overwrite=false`), 읽기
**거부**: 기존 파라미터 값 변경, 삭제

**주의사항**:
- `ssm:Overwrite` 조건은 `PutParameter` Action에만 적용
- `DeleteParameter`(단건)와 `DeleteParameters`(복수) **둘 다** Deny해야 우회 불가
- 파라미터 이름이 같으면 `PutParameter`는 기본적으로 덮어쓰기 — `--no-overwrite` 플래그 없으면 `Overwrite=true`로 간주

---

### Case 03 — 민감 경로 재귀 조회 차단

**시나리오**: `/app/prod/secrets/` 경로는 개별 파라미터 조회만 허용하고, `GetParametersByPath`로 재귀 조회하는 것은 차단.

**핵심 메커니즘**:
- Deny: `ssm:GetParametersByPath` + `ssm:Recursive: "true"` → Resource `/app/prod/secrets/*`
- Allow: `ssm:GetParameter` → 개별 파라미터 조회는 허용

**허용**: `/app/prod/secrets/db-password` 개별 조회
**거부**: `GetParametersByPath --recursive --path /app/prod/secrets/` → `AccessDenied`

**주의사항**:
- `ssm:Recursive` 조건은 `GetParametersByPath` Action에만 적용
- 재귀 없이(`--no-recursive`) `GetParametersByPath`를 호출하면 직계 하위만 반환 — 이것도 차단하려면 Action 자체를 Deny
- `GetParameterHistory`로 개별 파라미터의 이전 값도 조회 가능 → 민감 데이터면 함께 차단 고려

---

### Case 04 — CMK 강제 + 기본 키 차단

**시나리오**: SecureString 파라미터 생성 시 고객 관리형 KMS 키(CMK) 사용 강제. 기본 `aws/ssm` 키 사용 차단.

**핵심 메커니즘**:
- Allow: `ssm:PutParameter` — 일반 허용
- Deny: `ssm:PutParameter` + `kms:KeyId` 조건 없음 또는 `aws/ssm` 키 사용 시 거부
- KMS 키 ARN을 명시적으로 지정하도록 강제

**허용**: 지정 CMK로 암호화한 SecureString 생성
**거부**: `aws/ssm` 기본 키 사용, KMS 키 미지정

**주의사항**:
- 기본 `aws/ssm` 키는 계정 내 모든 IAM 엔티티에 Decrypt 허용 → SecureString 의미 없어짐
- CMK 사용 시 해당 키의 Key Policy에도 사용자의 `kms:Encrypt`, `kms:Decrypt` 허용 필요
- `ssm:Policies` 조건으로 파라미터 정책(만료, 알림) 첨부도 제어 가능
- String/StringList 타입은 KMS 무관 — SecureString만 해당

---

### Case 05 — 태그 기반 ABAC

**시나리오**: 파라미터의 `Team` 태그와 IAM 사용자의 `PrincipalTag/Team`이 일치할 때만 접근 허용.

**핵심 메커니즘**:
- `aws:ResourceTag/Team` + `StringEquals` + `${aws:PrincipalTag/Team}` 동적 매칭
- Deny: `aws:PrincipalTag/Team` `Null: "true"` → 태그 없는 사용자 전면 차단

**허용**: `PrincipalTag/Team = ops` → `ResourceTag/Team = ops` 파라미터만
**거부**: 태그 불일치 또는 태그 미설정 시 `AccessDenied`

**주의사항**:
- `DescribeParameters`는 태그 필터링 불가 → 모든 파라미터 이름 노출 (값은 아님)
- 파라미터 생성 시 태그 강제는 `aws:RequestTag/Team` + `Null` 조건으로 별도 구현
- `AddTagsToResource`/`RemoveTagsFromResource` 권한도 제어해야 태그 변경으로 우회 방지
- Label 기반 접근 제어는 IAM 조건키가 없어 불가능 — 태그만 사용 가능

---

## CloudShell 준비

```bash
export AWS_REGION="ap-northeast-2"
export ACCOUNT_ID="123456789012"
export USER_NAME="mod3-ssm-user"
export PROFILE_NAME="mod3-ssm-user"
```

---

## 검증 예시

```bash
# 허용 경로 읽기 — 성공 기대
aws ssm get-parameter \
  --name "/app/prod/db/host" \
  --profile "$PROFILE_NAME"

# 다른 경로 — AccessDenied 기대
aws ssm get-parameter \
  --name "/app/dev/db/host" \
  --profile "$PROFILE_NAME"

# 덮어쓰기 시도 — AccessDenied 기대
aws ssm put-parameter \
  --name "/app/prod/db/host" \
  --value "new-value" \
  --overwrite \
  --profile "$PROFILE_NAME"

# 삭제 시도 — AccessDenied 기대
aws ssm delete-parameter \
  --name "/app/prod/db/host" \
  --profile "$PROFILE_NAME"
```

---

## 감점 방지 포인트

- `DescribeParameters`를 특정 ARN에 넣으면 오류 — 반드시 `"*"`
- `DeleteParameter`(단건)와 `DeleteParameters`(복수) 둘 다 Deny해야 우회 불가
- SecureString 값 숨기려면 KMS Decrypt Deny가 필요 (SSM 정책만으로 부족)
- `GetParameterHistory`도 값을 반환하므로 읽기 차단 시 함께 제한
- 크로스 계정 공유 시 소비 계정에서 반드시 전체 ARN 사용 (이름만으로 접근 불가)
