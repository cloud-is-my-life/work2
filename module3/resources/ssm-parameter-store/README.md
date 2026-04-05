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
