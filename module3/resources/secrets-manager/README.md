# Secrets Manager Fine-grained IAM 실전 케이스

## 핵심 요약

> **⚠️ Secret ARN 끝 6자리 랜덤 suffix** — 정확한 ARN 모르면 `??????` 와일드카드 사용. `*`보다 안전.

> **⚠️ 크로스 계정 시크릿 공유는 반드시 CMK** — `aws/secretsmanager` AWS managed key는 크로스 계정 불가.

> **⚠️ 로테이션 Lambda는 `AWSPENDING` 스테이지 접근 필요** — `VersionStage` 조건으로 과도하게 제한하면 로테이션 실패.

> **⚠️ Resource Policy + IAM Policy 이중 구조** — 같은 계정이면 합집합, 크로스 계정이면 교집합.

> **⚠️ `ForceDeleteWithoutRecovery` 차단 필수** — 즉시 삭제 방지는 별도 Deny 필요.

---

## 전용 Condition Key

| Condition Key | 적용 Action | 설명 |
|---|---|---|
| `secretsmanager:Name` | `CreateSecret` | 시크릿 이름 패턴 제한 |
| `secretsmanager:VersionStage` | `GetSecretValue` | 버전 스테이지 제한 (AWSCURRENT/AWSPENDING/AWSPREVIOUS) |
| `secretsmanager:ResourceTag/${TagKey}` | 대부분 | 리소스 태그 기반 접근 제어 |
| `secretsmanager:ForceDeleteWithoutRecovery` | `DeleteSecret` | 즉시 삭제 차단 |
| `secretsmanager:RecoveryWindowInDays` | `DeleteSecret` | 복구 기간 최소값 강제 |
| `secretsmanager:KmsKeyArn` | `CreateSecret`, `UpdateSecret` | 특정 KMS 키 강제 |
| `secretsmanager:RotationLambdaARN` | `RotateSecret` | 특정 Lambda만 로테이션 허용 |
| `secretsmanager:BlockPublicPolicy` | `PutResourcePolicy` | 공개 정책 차단 |
| `secretsmanager:resource/AllowRotationLambdaArn` | 읽기 액션 | 로테이션 설정된 시크릿만 접근 |

---

## ARN 패턴

```
# 특정 시크릿 (6자리 suffix 포함)
arn:aws:secretsmanager:REGION:ACCOUNT_ID:secret:SECRET_NAME-AbCdEf

# 6자리 와일드카드 (권장)
arn:aws:secretsmanager:REGION:ACCOUNT_ID:secret:SECRET_NAME-??????

# 경로 prefix
arn:aws:secretsmanager:REGION:ACCOUNT_ID:secret:prod/*
```

---

## 정책 파일

| 케이스 | 파일 | 의도 |
|---|---|---|
| Case 01 | `policies/case01-path-prefix-readonly.json` | 경로 prefix 기반 읽기 전용 |
| Case 02 | `policies/case02-deny-delete-force.json` | 삭제 차단 + 즉시 삭제 방지 + 복구 기간 강제 |
| Case 03 | `policies/case03-abac-principaltag.json` | PrincipalTag ↔ ResourceTag 동적 ABAC |
| Case 04 | `policies/case04-enforce-cmk.json` | CMK 강제 + AWS managed key 차단 |
| Case 05 | `policies/case05-version-stage-current-only.json` | AWSCURRENT 버전만 조회 허용 |
| Case 06 | `policies/case06-resource-policy-vpce.json` | Resource Policy — VPC Endpoint 강제 |
| Case 07 | `policies/case07-rotation-lambda-permissions.json` | 로테이션 Lambda 실행 역할 정책 |

---

## 케이스별 상세 설명

### Case 01 — 경로 Prefix 기반 읽기 전용

**시나리오**: `prod/` prefix 시크릿만 읽기 허용. `dev/`, `staging/` 등 다른 경로는 접근 불가.

**핵심 메커니즘**:
- Allow: `secretsmanager:GetSecretValue`, `secretsmanager:DescribeSecret` → Resource `arn:aws:secretsmanager:REGION:ACCOUNT:secret:prod/*`
- Allow: `secretsmanager:ListSecrets` → Resource `*` (리소스 수준 제어 불가)

**허용**: `prod/db/mysql`, `prod/api/key` 등 `prod/` prefix 시크릿 읽기
**거부**: `dev/db/mysql` 등 다른 prefix 접근 시 `AccessDenied`

**주의사항**:
- Secret ARN에는 6자리 랜덤 suffix가 붙음 → `prod/*` 와일드카드로 커버
- `ListSecrets`는 `Resource: "*"` 필수 — 특정 ARN 지정 불가
- `DescribeSecret`은 값은 반환하지 않지만 메타데이터(태그, 로테이션 설정) 노출 → 필요 시 별도 제한

---

### Case 02 — 삭제 차단 + 즉시 삭제 방지 + 복구 기간 강제

**시나리오**: 시크릿 삭제 자체를 차단하거나, 삭제 시 최소 복구 기간(7일 이상) 강제. `ForceDeleteWithoutRecovery` 완전 차단.

**핵심 메커니즘**:
- Deny: `secretsmanager:DeleteSecret` + `secretsmanager:ForceDeleteWithoutRecovery: "true"` → 즉시 삭제 차단
- Deny: `secretsmanager:DeleteSecret` + `secretsmanager:RecoveryWindowInDays` < 7 → 짧은 복구 기간 차단
- 또는 전면 Deny: `secretsmanager:DeleteSecret` → Resource `*`

**허용**: 7일 이상 복구 기간 설정한 삭제 (전면 차단이 아닌 경우)
**거부**: 즉시 삭제, 짧은 복구 기간 삭제

**주의사항**:
- `ForceDeleteWithoutRecovery`와 `RecoveryWindowInDays`는 `DeleteSecret` Action에만 적용
- `NumericLessThan` 연산자로 복구 기간 최소값 강제
- 삭제 차단만으로는 시크릿 값 변경(`UpdateSecret`)은 막지 못함 → 필요 시 별도 제어

---

### Case 03 — PrincipalTag ↔ ResourceTag 동적 ABAC

**시나리오**: IAM 사용자의 `Team` 태그와 시크릿의 `Team` 태그가 일치할 때만 접근 허용.

**핵심 메커니즘**:
- `secretsmanager:ResourceTag/Team` + `StringEquals` + `${aws:PrincipalTag/Team}`
- Deny: `aws:PrincipalTag/Team` `Null: "true"` → 태그 없는 사용자 전면 차단

**허용**: `PrincipalTag/Team = backend` → `ResourceTag/Team = backend` 시크릿만
**거부**: 태그 불일치 또는 태그 미설정 시 `AccessDenied`

**주의사항**:
- `secretsmanager:ResourceTag/KEY` vs `aws:ResourceTag/KEY` — 둘 다 동작하지만 혼용 시 혼란 가능
- 시크릿 생성 시 태그 강제는 `aws:RequestTag/Team` + `Null` 조건으로 별도 구현
- `ListSecrets`는 태그 필터링 불가 → 모든 시크릿 이름이 노출됨 (값은 아님)

---

### Case 04 — CMK 강제 + AWS Managed Key 차단

**시나리오**: 시크릿 생성/업데이트 시 고객 관리형 KMS 키(CMK) 사용 강제. `aws/secretsmanager` 기본 키 사용 차단.

**핵심 메커니즘**:
- Deny: `secretsmanager:CreateSecret`, `secretsmanager:UpdateSecret` + `secretsmanager:KmsKeyArn` ≠ `ALLOWED_CMK_ARN`
- Deny: `secretsmanager:KmsKeyArn` `Null: "true"` → KMS 키 미지정 시 거부 (기본 키 사용 방지)

**허용**: 지정 CMK로 암호화한 시크릿 생성/업데이트
**거부**: 기본 키 사용, 다른 CMK 사용, KMS 키 미지정

**주의사항**:
- `aws/secretsmanager` 키는 크로스 계정 공유 불가 → 크로스 계정 시크릿 공유 시 CMK 필수
- `Null` 조건으로 키 미지정 케이스도 차단해야 함 — 빠뜨리면 기본 키로 생성 가능
- CMK의 Key Policy에도 해당 사용자/역할의 `kms:GenerateDataKey*`, `kms:Decrypt` 허용 필요

---

### Case 05 — AWSCURRENT 버전만 조회 허용

**시나리오**: `GetSecretValue` 시 `AWSCURRENT` 스테이지만 조회 가능. `AWSPREVIOUS`, `AWSPENDING` 등 이전/대기 버전 접근 차단.

**핵심 메커니즘**:
- Allow: `secretsmanager:GetSecretValue` + `secretsmanager:VersionStage: "AWSCURRENT"`
- Deny: `secretsmanager:GetSecretValue` + `secretsmanager:VersionStage` ∈ [`AWSPREVIOUS`, `AWSPENDING`]

**허용**: 현재 활성 버전(`AWSCURRENT`) 조회
**거부**: 이전 버전, 대기 버전 조회 시 `AccessDenied`

**주의사항**:
- 로테이션 Lambda는 `AWSPENDING` 스테이지 접근 필요 → 이 정책을 로테이션 역할에 적용하면 로테이션 실패
- `VersionId`로 직접 버전 지정 시 `VersionStage` 조건이 적용되지 않을 수 있음 → 별도 테스트 필요
- 기본 호출(`--version-stage` 미지정)은 `AWSCURRENT`로 간주됨

---

### Case 06 — Resource Policy: VPC Endpoint 강제

**시나리오**: 시크릿에 Resource Policy를 붙여 VPC Endpoint 경유 요청만 허용. 인터넷 경유 접근 차단.

**핵심 메커니즘**:
- Resource Policy(시크릿에 직접 연결): Deny + `aws:sourceVpce` ≠ `VPCE_ID`
- `Principal: "*"` + Condition으로 모든 호출자에 적용

**허용**: 지정 VPC Endpoint 경유 접근
**거부**: 인터넷, 다른 VPC Endpoint 경유 시 `AccessDenied`

**주의사항**:
- Resource Policy는 `aws secretsmanager put-resource-policy` CLI로 설정
- 같은 계정 내에서는 Resource Policy + IAM Policy 합집합 → Deny가 있으면 IAM Allow로도 우회 불가
- VPC Endpoint 없는 환경에서 이 정책 적용 시 모든 접근 차단됨 → 적용 전 VPC Endpoint 존재 확인 필수

---

### Case 07 — 로테이션 Lambda 실행 역할 정책

**시나리오**: 시크릿 로테이션 Lambda의 실행 역할에 필요한 최소 권한 정책. 대상 시크릿만 접근 가능.

**핵심 메커니즘**:
- Allow: `secretsmanager:GetSecretValue`, `secretsmanager:PutSecretValue`, `secretsmanager:UpdateSecretVersionStage`, `secretsmanager:DescribeSecret`
- Resource: 대상 시크릿 ARN만 (와일드카드 최소화)
- KMS 권한: `kms:GenerateDataKey`, `kms:Decrypt` (CMK 사용 시)

**허용**: 대상 시크릿의 값 읽기/쓰기/버전 스테이지 변경
**거부**: 다른 시크릿 접근, 시크릿 삭제/생성

**주의사항**:
- `AWSPENDING` 스테이지 접근 필수 — `VersionStage` 조건으로 과도하게 제한하면 로테이션 실패
- VPC 내 Lambda는 `ec2:CreateNetworkInterface`, `ec2:DescribeNetworkInterfaces`, `ec2:DeleteNetworkInterface` 권한도 필요
- 로테이션 Lambda가 DB에 직접 연결하는 경우 DB 보안 그룹에서 Lambda 서브넷 허용 필요
- `secretsmanager:RotationLambdaARN` 조건으로 특정 Lambda만 로테이션 허용 가능

---

## CloudShell 준비

```bash
export AWS_REGION="ap-northeast-2"
export ACCOUNT_ID="123456789012"
export SECRET_NAME="prod/db/mysql"
export USER_NAME="mod3-sm-user"
export PROFILE_NAME="mod3-sm-user"
```

---

## 검증 예시

```bash
# 시크릿 조회 — 성공 기대
aws secretsmanager get-secret-value \
  --secret-id "$SECRET_NAME" \
  --profile "$PROFILE_NAME"

# 다른 경로 시크릿 — AccessDenied 기대
aws secretsmanager get-secret-value \
  --secret-id "dev/db/mysql" \
  --profile "$PROFILE_NAME"

# 삭제 시도 — AccessDenied 기대
aws secretsmanager delete-secret \
  --secret-id "$SECRET_NAME" \
  --force-delete-without-recovery \
  --profile "$PROFILE_NAME"
```

---

## 감점 방지 포인트

- Secret ARN suffix `??????` vs `*` 차이 — `*`는 `prod/db/mysql-anything-extra`도 매칭
- `secretsmanager:ResourceTag/KEY` vs `aws:ResourceTag/KEY` — 둘 다 동작하지만 혼용 주의
- 크로스 계정 공유 시 Resource Policy + KMS Key Policy + 상대 IAM Policy 3단계 필요
- `GetSecretValue` 차단해도 `DescribeSecret`으로 메타데이터(태그, 로테이션 설정) 노출 가능
- 로테이션 Lambda에 VPC 접근 권한(`ec2:CreateNetworkInterface` 등) 빠뜨리면 로테이션 실패
