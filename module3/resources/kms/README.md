# KMS Fine-grained IAM 실전 케이스

## 핵심 요약

> **⚠️ Key Policy + IAM Policy 이중 잠금** — Key Policy에 IAM 위임 문장 없으면 IAM Policy가 아무리 허용해도 키 사용 불가.

> **⚠️ `kms:ViaService`로 직접 호출 차단** — 특정 AWS 서비스를 통해서만 키 사용 허용. 형식: `SERVICE.REGION.amazonaws.com`.

> **⚠️ `kms:EncryptionContext:KEY`는 단일값 조건키** — `ForAllValues`/`ForAnyValue` 사용하면 오류. `kms:EncryptionContextKeys`는 다중값.

> **⚠️ IAM Policy Resource에 alias ARN 쓰면 키 권한이 아님** — 반드시 key ARN 사용.

> **⚠️ 크로스 계정은 암호화 작업만 가능** — `ScheduleKeyDeletion`, `ListKeys` 등 관리 작업은 크로스 계정 불가.

---

## 전용 Condition Key

| Condition Key | 설명 |
|---|---|
| `kms:ViaService` | 특정 AWS 서비스 경유 요청만 허용 |
| `kms:CallerAccount` | 특정 계정의 Principal만 허용 |
| `kms:EncryptionContext:KEY` | 암호화 컨텍스트 key-value 매칭 (단일값) |
| `kms:EncryptionContextKeys` | 암호화 컨텍스트 키 목록 (다중값) |
| `kms:GrantIsForAWSResource` | AWS 서비스가 요청한 Grant만 허용 |
| `kms:GrantOperations` | Grant에 포함 가능한 작업 제한 |
| `kms:GranteePrincipal` | Grant 수신자 제한 |
| `kms:RetiringPrincipal` | Grant 폐기자 제한 |
| `kms:ScheduleKeyDeletionPendingWindowInDays` | 삭제 대기 기간 최소값 강제 |
| `kms:KeySpec` | 키 사양 제한 |
| `kms:KeyUsage` | 키 용도 제한 |
| `kms:KeyOrigin` | 키 원본 제한 (AWS_KMS, EXTERNAL 등) |
| `kms:RotationPeriodInDays` | 로테이션 주기 범위 강제 |

---

## ARN 패턴

```
# Key ARN (IAM Policy Resource에 사용)
arn:aws:kms:REGION:ACCOUNT_ID:key/KEY_ID

# Alias ARN (alias 리소스 관리용 — 키 사용 권한 아님!)
arn:aws:kms:REGION:ACCOUNT_ID:alias/ALIAS_NAME
```

---

## 정책 파일

| 케이스 | 파일 | 의도 |
|---|---|---|
| Case 01 | `policies/case01-key-policy-3tier.json` | Key Policy 3-tier 분리 (관리/사용/Grant) |
| Case 02 | `policies/case02-via-service-s3-only.json` | S3 경유 요청만 허용 (직접 호출 차단) |
| Case 03 | `policies/case03-encryption-context.json` | 암호화 컨텍스트 기반 세밀한 제어 |
| Case 04 | `policies/case04-deny-key-deletion.json` | 키 삭제/비활성화 차단 + 대기 기간 강제 |
| Case 05 | `policies/case05-encrypt-decrypt-split.json` | Encrypt 전용 / Decrypt 전용 분리 |
| Case 06 | `policies/case06-cross-account-key.json` | 크로스 계정 키 사용 (Key Policy + IAM) |
| Case 07 | `policies/case07-grant-restrictions.json` | Grant 생성 제한 (작업/수신자 범위) |

---

## ViaService 주요 서비스 값

| 서비스 | 값 |
|---|---|
| S3 | `s3.REGION.amazonaws.com` |
| EBS (EC2) | `ec2.REGION.amazonaws.com` |
| RDS | `rds.REGION.amazonaws.com` |
| Secrets Manager | `secretsmanager.REGION.amazonaws.com` |
| SSM | `ssm.REGION.amazonaws.com` |
| DynamoDB | `dynamodb.REGION.amazonaws.com` |
| SQS | `sqs.REGION.amazonaws.com` |
| Lambda | `lambda.REGION.amazonaws.com` |

---

## 감점 방지 포인트

- Key Policy에 `arn:aws:iam::ACCOUNT_ID:root` 위임 문장 없으면 IAM Policy 무효
- `kms:EncryptionContext:KEY`에 `ForAllValues` 쓰면 `OverlyPermissiveCondition` 오류
- IAM Policy Resource에 alias ARN 넣으면 alias 관리 권한이지 키 사용 권한 아님
- 크로스 계정: Key Policy(소유 계정) + IAM Policy(사용 계정) 양쪽 모두 필요
- AWS Managed Key(`aws/ebs`, `aws/s3` 등)는 크로스 계정 사용 불가
