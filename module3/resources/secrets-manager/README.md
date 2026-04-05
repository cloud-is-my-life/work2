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
