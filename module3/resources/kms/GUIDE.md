# KMS Fine-grained IAM 실전 가이드

> AWS Skills Competition 2026 대비. KMS 키 정책의 핵심 함정과 실전 패턴을 정리한 문서.

---

## 목차

1. [Key Policy vs IAM Policy 평가 로직](#1-key-policy-vs-iam-policy-평가-로직)
2. [EncryptionContext 실전 활용](#2-encryptioncontext-실전-활용)
3. [ViaService 서비스별 값 완전 목록](#3-viaservice-서비스별-값-완전-목록)
4. [기존 케이스 요약 (Case 01~07)](#4-기존-케이스-요약-case-0107)
5. [신규 케이스 상세 (Case 08~12)](#5-신규-케이스-상세-case-0812)
6. [감점 방지 포인트](#6-감점-방지-포인트)

---

## 1. Key Policy vs IAM Policy 평가 로직

### 이중 잠금 구조

KMS는 다른 AWS 서비스와 다르게 **두 개의 자물쇠**가 모두 열려야 접근이 가능하다.

```
요청 → [Key Policy 확인] AND [IAM Policy 확인] → 허용
```

일반 AWS 리소스(S3 버킷 정책 등)는 리소스 정책 OR IAM 정책 중 하나만 Allow해도 접근이 된다. KMS는 다르다. Key Policy에 명시적으로 허용되지 않은 Principal은 IAM Policy가 아무리 Allow해도 `AccessDenied`가 떨어진다.

### Root 위임 문장의 역할

Key Policy에 아래 문장이 있으면 IAM Policy에 위임된다.

```json
{
  "Sid": "AllowRootDelegation",
  "Effect": "Allow",
  "Principal": { "AWS": "arn:aws:iam::ACCOUNT_ID:root" },
  "Action": "kms:*",
  "Resource": "*"
}
```

이 문장이 있으면 IAM Policy에서 허용한 Principal은 Key Policy에 별도 명시 없이도 키를 사용할 수 있다. 없으면 Key Policy에 Principal을 직접 나열해야 한다.

### 평가 흐름 요약

| 상황 | Key Policy | IAM Policy | 결과 |
|---|---|---|---|
| Root 위임 있음 | Allow (root) | Allow (role) | 허용 |
| Root 위임 없음 | Allow (role 직접) | Allow (role) | 허용 |
| Root 위임 없음 | Allow (role 직접) | 없음 | 허용 |
| Root 위임 있음 | Allow (root) | 없음 | 거부 |
| Root 위임 없음 | 없음 | Allow (role) | 거부 |
| 어디서든 Deny | - | - | 거부 (Deny 우선) |

**핵심**: Key Policy에 Deny가 있으면 IAM Policy로 우회 불가. Deny는 항상 우선한다.

### 크로스 계정에서의 이중 잠금

크로스 계정은 자물쇠가 세 개다.

```
요청 → [소유 계정 Key Policy] AND [사용 계정 IAM Policy] → 허용
```

소유 계정 Key Policy에서 외부 계정 root 또는 특정 역할을 허용하고, 사용 계정 IAM Policy에서도 해당 키 ARN에 대해 Allow해야 한다. 둘 중 하나라도 빠지면 거부.

---

## 2. EncryptionContext 실전 활용

### 개념

암호화 컨텍스트는 KMS 암호화/복호화 요청에 함께 전달하는 key-value 쌍이다. 암호화 시 사용한 컨텍스트와 복호화 시 컨텍스트가 정확히 일치해야 KMS가 복호화를 수행한다. 컨텍스트 자체는 암호화되지 않고 CloudTrail 로그에 평문으로 기록된다.

### 조건 키 두 가지

| 조건 키 | 타입 | 사용법 |
|---|---|---|
| `kms:EncryptionContext:KEY` | 단일값 | `StringEquals`로 특정 key-value 매칭 |
| `kms:EncryptionContextKeys` | 다중값 | `ForAllValues`/`ForAnyValue:StringEquals`로 키 목록 제어 |

`kms:EncryptionContext:KEY`에 `ForAllValues`나 `ForAnyValue`를 붙이면 오류가 난다. 단일값 조건키이기 때문이다.

### 실전 패턴

**패턴 1: 특정 부서만 복호화 허용**

```json
{
  "Condition": {
    "StringEquals": {
      "kms:EncryptionContext:Department": "Finance"
    }
  }
}
```

Finance 부서 컨텍스트가 없는 요청은 모두 거부된다.

**패턴 2: 여러 컨텍스트 키 중 하나라도 포함 요구**

```json
{
  "Condition": {
    "ForAnyValue:StringEquals": {
      "kms:EncryptionContextKeys": ["Department", "ProjectId"]
    }
  }
}
```

**패턴 3: S3 SSE-KMS 버킷별 키 제어**

S3는 SSE-KMS 암호화 시 자동으로 버킷 ARN을 컨텍스트에 포함한다.

```
aws:s3:arn = arn:aws:s3:::MY_BUCKET
```

이를 활용하면 특정 버킷에서 온 요청만 복호화를 허용할 수 있다.

```json
{
  "Condition": {
    "StringEquals": {
      "kms:EncryptionContext:aws:s3:arn": "arn:aws:s3:::MY_BUCKET"
    }
  }
}
```

**패턴 4: 컨텍스트 없는 요청 차단**

```json
{
  "Sid": "DenyWithoutEncryptionContext",
  "Effect": "Deny",
  "Action": ["kms:Decrypt", "kms:Encrypt"],
  "Resource": "*",
  "Condition": {
    "Null": {
      "kms:EncryptionContextKeys": "true"
    }
  }
}
```

### CloudTrail 활용

암호화 컨텍스트는 CloudTrail `requestParameters`에 평문으로 기록된다. 누가 어떤 컨텍스트로 키를 사용했는지 추적할 수 있어서 감사(audit) 목적으로도 유용하다.

---

## 3. ViaService 서비스별 값 완전 목록

형식: `SERVICE_NAME.REGION.amazonaws.com`

리전은 반드시 포함해야 한다. 리전 없이 `s3.amazonaws.com`처럼 쓰면 조건이 일치하지 않는다.

### 스토리지 / 데이터베이스

| 서비스 | ViaService 값 |
|---|---|
| S3 | `s3.REGION.amazonaws.com` |
| EBS (EC2) | `ec2.REGION.amazonaws.com` |
| EFS | `elasticfilesystem.REGION.amazonaws.com` |
| RDS | `rds.REGION.amazonaws.com` |
| Aurora | `rds.REGION.amazonaws.com` |
| DynamoDB | `dynamodb.REGION.amazonaws.com` |
| Redshift | `redshift.REGION.amazonaws.com` |
| ElastiCache | `elasticache.REGION.amazonaws.com` |
| OpenSearch | `es.REGION.amazonaws.com` |
| Backup | `backup.REGION.amazonaws.com` |

### 컴퓨팅 / 컨테이너

| 서비스 | ViaService 값 |
|---|---|
| Lambda | `lambda.REGION.amazonaws.com` |
| EC2 Image Builder | `imagebuilder.REGION.amazonaws.com` |
| ECR | `ecr.REGION.amazonaws.com` |

### 메시징 / 통합

| 서비스 | ViaService 값 |
|---|---|
| SQS | `sqs.REGION.amazonaws.com` |
| SNS | `sns.REGION.amazonaws.com` |
| Kinesis | `kinesis.REGION.amazonaws.com` |
| EventBridge | `events.REGION.amazonaws.com` |

### 보안 / 관리

| 서비스 | ViaService 값 |
|---|---|
| Secrets Manager | `secretsmanager.REGION.amazonaws.com` |
| SSM Parameter Store | `ssm.REGION.amazonaws.com` |
| CloudTrail | `cloudtrail.REGION.amazonaws.com` |
| CodeBuild | `codebuild.REGION.amazonaws.com` |
| CodePipeline | `codepipeline.REGION.amazonaws.com` |

### 주의사항

- AWS Managed Key(`aws/s3`, `aws/ebs` 등)는 이미 ViaService가 내장되어 있어서 별도 설정 불필요
- `kms:ViaService`는 Key Policy와 IAM Policy 양쪽에서 모두 사용 가능하지만, Key Policy에서 설정하는 것이 더 강력하다
- 여러 서비스를 동시에 허용할 때는 `StringEquals` 배열로 나열한다

```json
"StringEquals": {
  "kms:ViaService": [
    "s3.ap-northeast-2.amazonaws.com",
    "secretsmanager.ap-northeast-2.amazonaws.com",
    "ssm.ap-northeast-2.amazonaws.com"
  ]
}
```

---

## 4. 기존 케이스 요약 (Case 01~07)

| 케이스 | 파일 | 핵심 포인트 |
|---|---|---|
| Case 01 | `case01-key-policy-3tier.json` | 관리/사용/Grant 역할 분리. Root 위임 문장 포함 여부가 핵심 |
| Case 02 | `case02-via-service-s3-only.json` | S3 경유만 허용. `StringNotEquals`로 직접 호출 Deny |
| Case 03 | `case03-encryption-context.json` | `kms:EncryptionContext:Department` 단일값 조건. `ForAllValues` 사용 금지 |
| Case 04 | `case04-deny-key-deletion.json` | 키 삭제/비활성화 Deny. `kms:ScheduleKeyDeletionPendingWindowInDays`로 대기 기간 강제 |
| Case 05 | `case05-encrypt-decrypt-split.json` | Producer(Encrypt 전용) / Consumer(Decrypt 전용) 분리 |
| Case 06 | `case06-cross-account-key.json` | 크로스 계정: Key Policy(소유 계정) + IAM Policy(사용 계정) 양쪽 필요 |
| Case 07 | `case07-grant-restrictions.json` | `kms:GrantOperations`로 Grant 허용 작업 제한. `ForAnyValue:StringEquals` 사용 |

---

## 5. 신규 케이스 상세 (Case 08~12)

### Case 08 — 다중 서비스 ViaService

**파일**: `case08-multi-service-via-service.json`

**시나리오**: S3, Secrets Manager, SSM 세 서비스를 통한 요청만 허용. 직접 KMS API 호출은 차단.

**핵심 메커니즘**:

```json
"Condition": {
  "StringEquals": {
    "kms:ViaService": [
      "s3.AWS_REGION.amazonaws.com",
      "secretsmanager.AWS_REGION.amazonaws.com",
      "ssm.AWS_REGION.amazonaws.com"
    ]
  }
}
```

`StringEquals`에 배열을 넣으면 OR 조건으로 동작한다. 세 서비스 중 하나를 통한 요청이면 허용.

**허용**: S3 PutObject/GetObject, Secrets Manager GetSecretValue, SSM GetParameter 시 자동 KMS 호출
**거부**: `aws kms encrypt` 직접 호출, 목록에 없는 서비스 경유

**주의사항**:
- `StringNotEquals` Deny 문장도 함께 추가해야 직접 호출이 완전히 차단된다
- 서비스를 추가할 때마다 두 Statement(Allow + Deny) 모두 업데이트 필요
- 리전 값은 실제 배포 리전으로 교체해야 한다

---

### Case 09 — 키 로테이션 강제

**파일**: `case09-key-rotation-enforce.json`

**시나리오**: 키 로테이션 활성화는 허용하되, 비활성화는 전면 차단. 로테이션 주기는 최대 365일로 제한.

**핵심 메커니즘**:

```json
{
  "Sid": "DenyKeyRotationDisable",
  "Effect": "Deny",
  "Principal": { "AWS": "*" },
  "Action": "kms:DisableKeyRotation",
  "Resource": "*"
}
```

`Principal: "*"`에 Deny를 걸면 Key Admin도 포함된다. 로테이션 비활성화는 누구도 할 수 없다.

로테이션 주기 상한선 강제:

```json
{
  "Sid": "DenyExcessiveRotationPeriod",
  "Effect": "Deny",
  "Action": "kms:EnableKeyRotation",
  "Condition": {
    "NumericGreaterThan": {
      "kms:RotationPeriodInDays": "365"
    }
  }
}
```

**허용**: `EnableKeyRotation` (주기 365일 이하), `GetKeyRotationStatus`
**거부**: `DisableKeyRotation` (무조건), 366일 이상 주기로 `EnableKeyRotation`

**주의사항**:
- `kms:RotationPeriodInDays`는 KMS 전용 조건 키. 일반 IAM 조건 키가 아니다
- 기본 로테이션 주기는 365일. 더 짧게 강제하려면 `NumericGreaterThan` 값을 낮춘다
- 대칭 키(SYMMETRIC_DEFAULT)만 자동 로테이션 지원. 비대칭 키는 수동 로테이션 필요

---

### Case 10 — 특정 리전 키만 사용

**파일**: `case10-region-restriction.json`

**시나리오**: `ap-northeast-2` 리전의 KMS 키만 사용 허용. 다른 리전 키 사용 시도는 차단.

**핵심 메커니즘**:

```json
{
  "Sid": "DenyKMSOutsideApprovedRegion",
  "Effect": "Deny",
  "Action": ["kms:Encrypt", "kms:Decrypt", ...],
  "Resource": "*",
  "Condition": {
    "StringNotEquals": {
      "aws:RequestedRegion": "ap-northeast-2"
    }
  }
}
```

`aws:RequestedRegion`은 KMS 전용 조건 키가 아니라 글로벌 조건 키다. IAM Policy에서도 동일하게 사용 가능.

**허용**: `ap-northeast-2` 리전 키에 대한 모든 암호화 작업
**거부**: 다른 리전 키 사용 시도, 다른 리전에서 KMS 키 생성

**주의사항**:
- `Resource` ARN에 리전을 명시하는 것과 `aws:RequestedRegion` 조건은 다르다. ARN 제한은 특정 키만 허용하고, 조건은 요청 리전을 제한한다
- SCP(Service Control Policy)에서 이 패턴을 쓰면 조직 전체에 리전 제한을 걸 수 있다
- Multi-Region Key는 여러 리전에 복제되므로 이 정책과 충돌할 수 있다

---

### Case 11 — 봉투 암호화 전용

**파일**: `case11-envelope-encryption-only.json`

**시나리오**: 이 키는 봉투 암호화(Envelope Encryption)에만 사용. `GenerateDataKey*`만 허용하고 직접 `Encrypt`/`Decrypt`는 차단.

**봉투 암호화 흐름**:

```
1. GenerateDataKey 호출 → 평문 데이터 키 + 암호화된 데이터 키 반환
2. 평문 데이터 키로 데이터 암호화 (로컬)
3. 평문 데이터 키 메모리에서 삭제
4. 암호화된 데이터 키를 데이터와 함께 저장
5. 복호화 시: 암호화된 데이터 키를 Decrypt로 복원 → 데이터 복호화
```

**핵심 메커니즘**:

```json
{
  "Sid": "AllowEnvelopeEncryptionOnly",
  "Effect": "Allow",
  "Action": [
    "kms:GenerateDataKey",
    "kms:GenerateDataKeyWithoutPlaintext",
    "kms:DescribeKey"
  ]
}
```

직접 Encrypt/Decrypt는 Key Admin을 제외하고 전면 Deny:

```json
{
  "Sid": "DenyDirectEncryptDecrypt",
  "Effect": "Deny",
  "Action": ["kms:Encrypt", "kms:Decrypt", "kms:ReEncryptFrom", "kms:ReEncryptTo"],
  "Condition": {
    "StringNotEquals": {
      "aws:PrincipalArn": "arn:aws:iam::ACCOUNT_ID:role/KEY_ADMIN_ROLE"
    }
  }
}
```

**허용**: `GenerateDataKey`, `GenerateDataKeyWithoutPlaintext`, `DescribeKey`
**거부**: `Encrypt`, `Decrypt`, `ReEncryptFrom`, `ReEncryptTo` (Key Admin 제외)

**주의사항**:
- 봉투 암호화에서 복호화 단계는 `kms:Decrypt`를 사용한다. 이 케이스에서는 Key Admin만 직접 Decrypt 가능하고, 일반 앱은 `GenerateDataKey`로 받은 암호화된 데이터 키를 별도 경로로 복호화해야 한다
- `GenerateDataKeyWithoutPlaintext`는 평문 키 없이 암호화된 키만 반환. 나중에 사용할 키를 미리 생성해 둘 때 유용하다
- AWS SDK의 암호화 라이브러리(AWS Encryption SDK)는 내부적으로 봉투 암호화를 자동으로 처리한다

---

### Case 12 — Key Policy + IAM Policy 조합 실전

**파일**: `case12-key-policy-iam-combo.json`

**시나리오**: Root 위임 문장 유무에 따라 IAM Policy의 효력이 달라지는 두 시나리오를 비교.

**시나리오 A: Root 위임 없음**

Key Policy에 Principal을 직접 나열해야 한다. IAM Policy에서 Allow해도 Key Policy에 없으면 거부.

```
KEY_USER_ROLE이 Encrypt 시도
→ Key Policy: KEY_USER_ROLE Allow 있음 → OK
→ IAM Policy: Allow 있음 → OK
→ 결과: 허용

KEY_USER_ROLE이 Encrypt 시도 (Key Policy에서 KEY_USER_ROLE 제거 시)
→ Key Policy: 없음 → 거부
→ 결과: AccessDenied (IAM Policy 무관)
```

**시나리오 B: Root 위임 있음**

Key Policy에 `arn:aws:iam::ACCOUNT_ID:root`를 Allow하면 IAM Policy에 위임된다.

```
KEY_USER_ROLE이 Encrypt 시도
→ Key Policy: root Allow 있음 → IAM Policy 확인으로 위임
→ IAM Policy: KEY_USER_ROLE Allow 있음 → OK
→ 결과: 허용

KEY_USER_ROLE이 Encrypt 시도 (IAM Policy 없을 때)
→ Key Policy: root Allow 있음 → IAM Policy 확인으로 위임
→ IAM Policy: 없음 → 거부
→ 결과: AccessDenied
```

**실전 권장 패턴**:

경쟁 환경에서는 시나리오 B(Root 위임 있음)를 기본으로 쓰고, Key Policy에는 Key Admin 권한만 명시한다. 일반 사용자 권한은 IAM Policy로 관리하면 Key Policy를 수정하지 않고도 권한을 추가/제거할 수 있다.

**주의사항**:
- Root 위임 문장은 `kms:*`를 허용하지만, 실제로 root 계정이 모든 작업을 할 수 있다는 뜻이 아니다. IAM Policy가 없으면 root도 키를 사용할 수 없다 (단, root 계정 자체는 예외)
- Key Policy를 잘못 설정해서 아무도 접근 못 하게 되면 AWS Support를 통해서만 복구 가능하다
- `kms:PutKeyPolicy`를 Key Admin에게만 허용하고 Key User에게는 주지 않는 것이 최소 권한 원칙

---

## 6. 감점 방지 포인트

### 최빈출 함정 TOP 5

**1. Root 위임 문장 누락**

Key Policy에 `arn:aws:iam::ACCOUNT_ID:root` Allow 없으면 IAM Policy 전체가 무효. 경쟁에서 가장 많이 틀리는 포인트.

**2. `kms:EncryptionContext:KEY`에 ForAllValues 사용**

```json
// 틀림
"ForAllValues:StringEquals": { "kms:EncryptionContext:Department": "Finance" }

// 맞음
"StringEquals": { "kms:EncryptionContext:Department": "Finance" }
```

**3. IAM Policy Resource에 alias ARN 사용**

```
# 틀림 (alias 관리 권한이지 키 사용 권한 아님)
"Resource": "arn:aws:kms:ap-northeast-2:123456789012:alias/my-key"

# 맞음
"Resource": "arn:aws:kms:ap-northeast-2:123456789012:key/KEY_ID"
```

**4. ViaService 값에 리전 누락**

```
# 틀림
"kms:ViaService": "s3.amazonaws.com"

# 맞음
"kms:ViaService": "s3.ap-northeast-2.amazonaws.com"
```

**5. 크로스 계정에서 AWS Managed Key 사용 시도**

`aws/s3`, `aws/ebs` 등 AWS Managed Key는 크로스 계정 사용 불가. 반드시 CMK(Customer Managed Key)를 사용해야 한다.

### 추가 주의사항

- Key Policy에서 Deny하면 IAM Policy로 우회 불가. Deny는 항상 우선
- 크로스 계정에서 관리 작업(`ScheduleKeyDeletion`, `EnableKey`, `DisableKey`)은 불가. 암호화 작업만 가능
- `kms:GrantOperations`는 `ForAnyValue:StringEquals` 사용. 하나라도 비허용 작업이 포함된 Grant 생성 시도는 거부
- Key Policy는 리소스 기반 정책이므로 `Principal` 필수. IAM Policy에는 `Principal` 없음
- `kms:CallerAccount`로 허용 계정을 제한할 때 계정 ID는 문자열로 입력 (`"123456789012"`)

---

## 정책 파일 전체 목록

| 케이스 | 파일 | 의도 |
|---|---|---|
| Case 01 | `policies/case01-key-policy-3tier.json` | Key Policy 3-tier 분리 (관리/사용/Grant) |
| Case 02 | `policies/case02-via-service-s3-only.json` | S3 경유 요청만 허용 (직접 호출 차단) |
| Case 03 | `policies/case03-encryption-context.json` | 암호화 컨텍스트 기반 세밀한 제어 |
| Case 04 | `policies/case04-deny-key-deletion.json` | 키 삭제/비활성화 차단 + 대기 기간 강제 |
| Case 05 | `policies/case05-encrypt-decrypt-split.json` | Encrypt 전용 / Decrypt 전용 분리 |
| Case 06 | `policies/case06-cross-account-key.json` | 크로스 계정 키 사용 (Key Policy + IAM) |
| Case 07 | `policies/case07-grant-restrictions.json` | Grant 생성 제한 (작업/수신자 범위) |
| Case 08 | `policies/case08-multi-service-via-service.json` | 다중 서비스 ViaService (S3 + Secrets Manager + SSM) |
| Case 09 | `policies/case09-key-rotation-enforce.json` | 키 로테이션 강제 (비활성화 Deny + 주기 상한) |
| Case 10 | `policies/case10-region-restriction.json` | 특정 리전 키만 사용 (aws:RequestedRegion) |
| Case 11 | `policies/case11-envelope-encryption-only.json` | 봉투 암호화 전용 (직접 Encrypt/Decrypt 차단) |
| Case 12 | `policies/case12-key-policy-iam-combo.json` | Key Policy + IAM Policy 조합 (Root 위임 유무 비교) |
