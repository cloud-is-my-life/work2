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

## 케이스별 상세 설명

### Case 01 — Key Policy 3-tier 분리

**시나리오**: 하나의 KMS 키에 대해 관리자(Key Admin), 사용자(Key User), Grant 관리자 3개 역할을 분리.

**핵심 메커니즘**:
- Statement 1: Root 계정에 IAM 위임 (`arn:aws:iam::ACCOUNT:root`) — IAM Policy가 키 권한을 제어할 수 있도록 허용
- Statement 2: Key Admin → `kms:Create*`, `kms:Describe*`, `kms:Enable*`, `kms:Disable*`, `kms:Put*`, `kms:Update*`, `kms:Revoke*`, `kms:Delete*`, `kms:TagResource`, `kms:UntagResource`, `kms:ScheduleKeyDeletion`, `kms:CancelKeyDeletion`
- Statement 3: Key User → `kms:Encrypt`, `kms:Decrypt`, `kms:ReEncrypt*`, `kms:GenerateDataKey*`, `kms:DescribeKey`
- Statement 4: Grant Admin → `kms:CreateGrant`, `kms:ListGrants`, `kms:RevokeGrant`

**허용**: 각 역할에 해당하는 작업만
**거부**: Key User가 키 삭제 시도 → 거부, Key Admin이 Encrypt 시도 → 거부 (IAM Policy에서 별도 허용하지 않는 한)

**주의사항**:
- Root 위임 문장 없으면 IAM Policy가 아무리 Allow해도 키 사용 불가 — **가장 빈출 함정**
- Key Policy는 리소스 기반 정책이므로 `Principal` 필수
- Key Admin에게 `kms:Encrypt`/`kms:Decrypt` 주지 않는 것이 최소 권한 원칙
- Grant Admin의 `kms:CreateGrant`에 `kms:GrantIsForAWSResource: "true"` 조건 추가 권장

---

### Case 02 — ViaService: S3 경유만 허용

**시나리오**: KMS 키를 S3 서비스를 통해서만 사용 가능. 직접 `kms:Encrypt`/`kms:Decrypt` API 호출은 차단.

**핵심 메커니즘**:
- Allow: `kms:Encrypt`, `kms:Decrypt`, `kms:GenerateDataKey*` + `kms:ViaService: "s3.REGION.amazonaws.com"`
- 직접 호출 시 `kms:ViaService` 조건 불일치 → 거부

**허용**: S3 `PutObject`/`GetObject` 시 자동으로 KMS 호출 → 성공
**거부**: `aws kms encrypt --key-id KEY_ID` 직접 호출 → `AccessDenied`

**주의사항**:
- `kms:ViaService` 값 형식: `SERVICE.REGION.amazonaws.com` — 리전 포함 필수
- 여러 서비스 허용 시 `StringEquals` 배열로 나열: `["s3.ap-northeast-2.amazonaws.com", "secretsmanager.ap-northeast-2.amazonaws.com"]`
- `kms:ViaService`는 IAM Policy에서도 사용 가능하지만, Key Policy에서 설정하는 것이 더 강력
- AWS Managed Key(`aws/s3` 등)는 이미 ViaService가 내장되어 있음

---

### Case 03 — 암호화 컨텍스트 기반 제어

**시나리오**: 특정 암호화 컨텍스트(`Department=Finance`)가 포함된 요청만 Decrypt 허용. 다른 컨텍스트는 차단.

**핵심 메커니즘**:
- Allow: `kms:Decrypt` + `kms:EncryptionContext:Department: "Finance"`
- `kms:EncryptionContext:KEY`는 단일값 조건키 → `StringEquals` 사용

**허용**: `--encryption-context Department=Finance` 포함 Decrypt
**거부**: 컨텍스트 없거나 다른 값 → `AccessDenied`

**주의사항**:
- `kms:EncryptionContext:KEY`에 `ForAllValues`/`ForAnyValue` 사용하면 오류 — **단일값 조건키**
- 컨텍스트 키 목록 제어는 `kms:EncryptionContextKeys` (다중값 조건키) 사용
- 암호화 시 사용한 컨텍스트와 복호화 시 컨텍스트가 정확히 일치해야 KMS가 복호화 수행
- S3 SSE-KMS는 자동으로 버킷 ARN을 컨텍스트에 포함 → 이를 활용한 버킷별 키 제어 가능

---

### Case 04 — 키 삭제/비활성화 차단 + 대기 기간 강제

**시나리오**: KMS 키 삭제와 비활성화를 차단. 삭제가 불가피한 경우 최소 30일 대기 기간 강제.

**핵심 메커니즘**:
- Deny: `kms:ScheduleKeyDeletion` → 전면 차단 또는 조건부 허용
- Deny: `kms:DisableKey` → 키 비활성화 차단
- 조건부 허용 시: `kms:ScheduleKeyDeletionPendingWindowInDays` + `NumericLessThan: 30` → Deny

**허용**: 30일 이상 대기 기간 설정한 삭제 예약 (조건부 허용 시)
**거부**: 키 삭제, 비활성화, 30일 미만 대기 기간

**주의사항**:
- `CancelKeyDeletion`은 허용해야 실수로 예약된 삭제를 취소 가능
- `kms:DisableKey`와 `kms:ScheduleKeyDeletion`은 별도 Action — 둘 다 Deny 필요
- Key Policy에서 Deny하면 IAM Policy로 우회 불가 (Resource-based Deny 우선)
- `kms:EnableKeyRotation`/`kms:DisableKeyRotation`도 함께 고려 — 로테이션 비활성화 차단

---

### Case 05 — Encrypt/Decrypt 분리

**시나리오**: 데이터 생산자는 Encrypt만, 소비자는 Decrypt만 허용. 양방향 접근 차단.

**핵심 메커니즘**:
- Producer Role: `kms:Encrypt`, `kms:GenerateDataKey*`, `kms:DescribeKey`
- Consumer Role: `kms:Decrypt`, `kms:DescribeKey`
- `kms:ReEncrypt*`는 양쪽 모두에서 제외 (재암호화 방지)

**허용**: Producer → 암호화만, Consumer → 복호화만
**거부**: Producer가 Decrypt 시도 → `AccessDenied`, Consumer가 Encrypt 시도 → `AccessDenied`

**주의사항**:
- `kms:ReEncryptFrom`/`kms:ReEncryptTo`를 허용하면 키 간 데이터 이동 가능 → 보통 제외
- `kms:GenerateDataKeyWithoutPlaintext`는 봉투 암호화에서 사용 — Producer에 포함 여부 결정
- `kms:DescribeKey`는 양쪽 모두 필요 — 키 메타데이터 조회용 (민감 정보 아님)

---

### Case 06 — 크로스 계정 키 사용

**시나리오**: 외부 계정이 이 계정의 KMS 키를 사용하여 S3 오브젝트를 암호화/복호화.

**핵심 메커니즘**:
- Key Policy (소유 계정): 외부 계정 root 또는 특정 역할에 `kms:Encrypt`, `kms:Decrypt`, `kms:GenerateDataKey*`, `kms:DescribeKey` 허용
- IAM Policy (사용 계정): 해당 키 ARN에 대해 동일 Action 허용
- 양쪽 모두 Allow 필요 (교집합)

**허용**: 외부 계정의 지정 역할이 키를 사용한 암호화/복호화
**거부**: Key Policy 또는 IAM Policy 중 하나라도 없으면 `AccessDenied`

**주의사항**:
- AWS Managed Key(`aws/s3`, `aws/ebs` 등)는 크로스 계정 사용 **불가** — CMK만 가능
- `kms:CallerAccount` 조건으로 허용 계정 제한 가능
- `kms:ViaService` 조건 병행 시 특정 서비스 경유만 허용 가능
- 크로스 계정에서 관리 작업(`ScheduleKeyDeletion`, `EnableKey` 등)은 불가

---

### Case 07 — Grant 생성 제한

**시나리오**: Grant 생성 시 허용 작업과 수신자를 제한. 무분별한 Grant 발급 방지.

**핵심 메커니즘**:
- Allow: `kms:CreateGrant` + `kms:GrantOperations` 조건으로 허용 작업 제한 (예: `Encrypt`, `Decrypt`만)
- `kms:GranteePrincipal` 조건으로 Grant 수신자를 특정 역할/서비스로 제한
- `kms:GrantIsForAWSResource: "true"` → AWS 서비스가 요청한 Grant만 허용

**허용**: 지정 작업 + 지정 수신자에 대한 Grant 생성
**거부**: `ScheduleKeyDeletion` 등 위험 작업 포함 Grant, 비허용 수신자 Grant

**주의사항**:
- `kms:GrantOperations`는 `ForAnyValue:StringEquals`로 사용 — 하나라도 비허용 작업이 포함되면 거부
- `kms:GrantIsForAWSResource`는 EBS, RDS 등 AWS 서비스가 자동 생성하는 Grant에 사용
- Grant는 Key Policy/IAM Policy와 별개로 권한을 부여 → 제한 없으면 권한 상승 경로
- `kms:RetiringPrincipal` 조건으로 Grant 폐기 권한자도 제한 가능

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
