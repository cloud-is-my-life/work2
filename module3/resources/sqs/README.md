# SQS Fine-grained IAM 실전 케이스

## 핵심 요약

> **⚠️ IAM Policy vs Queue Policy 구분 필수** — 크로스 계정/서비스(SNS, S3, EventBridge)는 반드시 Queue Policy 필요.

> **⚠️ 같은 계정이면 합집합, 크로스 계정이면 교집합** — Queue Policy에 Allow 있어도 크로스 계정은 IAM Policy도 필요.

> **⚠️ `sqs:ListQueues`는 리소스 수준 제어 불가** — `"Resource": "*"` 필수.

> **⚠️ 크로스 계정에서 동작 안 하는 Action 존재** — `DeleteQueue`, `SetQueueAttributes`, `CreateQueue` 등 관리 Action은 큐 소유 계정만 가능.

> **⚠️ 암호화 큐에 SNS가 메시지 보내려면 KMS Key Policy도 수정 필요** — Queue Policy만으로 부족.

---

## Producer / Consumer 필수 Action 분리

| 역할 | 필수 Actions |
|---|---|
| Producer | `sqs:SendMessage` |
| Consumer | `sqs:ReceiveMessage`, `sqs:DeleteMessage`, `sqs:ChangeMessageVisibility`, `sqs:GetQueueAttributes` |
| 모니터링 | `sqs:GetQueueAttributes` |
| 관리 | `sqs:SetQueueAttributes`, `sqs:AddPermission`, `sqs:RemovePermission` |

---

## ARN 패턴

```
# 특정 큐
arn:aws:sqs:REGION:ACCOUNT_ID:QUEUE_NAME

# Prefix 와일드카드
arn:aws:sqs:REGION:ACCOUNT_ID:prod-*

# FIFO 큐 (반드시 .fifo 접미사)
arn:aws:sqs:REGION:ACCOUNT_ID:QUEUE_NAME.fifo
```

---

## 정책 파일

| 케이스 | 파일 | 의도 |
|---|---|---|
| Case 01 | `policies/case01-producer-only.json` | Producer 전용 (SendMessage만) |
| Case 02 | `policies/case02-consumer-only.json` | Consumer 전용 (Receive+Delete) |
| Case 03 | `policies/case03-deny-delete-purge.json` | 큐 삭제/퍼지 차단 |
| Case 04 | `policies/case04-queue-policy-sns.json` | Queue Policy — SNS → SQS |
| Case 05 | `policies/case05-queue-policy-s3-event.json` | Queue Policy — S3 이벤트 알림 |
| Case 06 | `policies/case06-deny-unsecure-transport.json` | TLS 강제 + Org 외부 차단 |
| Case 07 | `policies/case07-abac-tag-based.json` | 태그 기반 ABAC |

---

## 케이스별 상세 설명

### Case 01 — Producer 전용 (SendMessage만)

**시나리오**: 애플리케이션이 특정 큐에 메시지를 전송만 가능. 수신, 삭제, 큐 관리 불가.

**핵심 메커니즘**:
- Allow: `sqs:SendMessage` → 특정 큐 ARN
- Allow: `sqs:GetQueueUrl`, `sqs:GetQueueAttributes` → 큐 URL 조회용

**허용**: `SendMessage`, `SendMessageBatch` (큐 ARN 범위 내)
**거부**: `ReceiveMessage`, `DeleteMessage`, `PurgeQueue`, 큐 설정 변경

**주의사항**:
- `sqs:ListQueues`는 `Resource: "*"` 필수 — 큐 ARN 지정 불가
- `SendMessageBatch`는 `SendMessage` 권한으로 커버됨 (별도 Action 아님)
- FIFO 큐에 전송 시 `MessageGroupId` 필수 — IAM과 무관하지만 실패 원인으로 혼동 가능

---

### Case 02 — Consumer 전용 (Receive+Delete)

**시나리오**: 워커가 큐에서 메시지를 수신하고 처리 후 삭제만 가능. 메시지 전송, 큐 관리 불가.

**핵심 메커니즘**:
- Allow: `sqs:ReceiveMessage`, `sqs:DeleteMessage`, `sqs:ChangeMessageVisibility`, `sqs:GetQueueAttributes` → 특정 큐 ARN

**허용**: 메시지 수신, 삭제, 가시성 타임아웃 변경
**거부**: `SendMessage`, `PurgeQueue`, 큐 설정 변경

**주의사항**:
- `ChangeMessageVisibility` 빠뜨리면 처리 시간 초과 시 메시지 재처리 제어 불가
- `GetQueueAttributes`는 큐 상태 확인용 — 빠뜨려도 수신은 가능하지만 모니터링 불가
- DLQ(Dead Letter Queue) Consumer는 소스 큐의 KMS 키에 대한 `kms:Decrypt`도 필요
- Long Polling은 `ReceiveMessage`의 `WaitTimeSeconds` 파라미터 — IAM과 무관

---

### Case 03 — 큐 삭제/퍼지 차단

**시나리오**: 큐 사용(Send/Receive)은 허용하되, 큐 삭제와 메시지 전체 지는 Explicit Deny로 차단.

**핵심 메커니즘**:
- Deny: `sqs:DeleteQueue`, `sqs:PurgeQueue` → Resource `*`
- Allow: Send/Receive 등 일반 사용 Action

**허용**: 메시지 전송, 수신, 삭제 (개별 메시지)
**거부**: 큐 자체 삭제, 큐 내 모든 메시지 퍼지 → `AccessDenied`

**주의사항**:
- `PurgeQueue`는 `DeleteQueue`와 별도 Action — 둘 다 Deny 필요
- `DeleteMessage`(개별 메시지 삭제)는 Consumer에 필수이므로 Deny하면 안 됨 — `PurgeQueue`(전체 삭제)와 구분
- `SetQueueAttributes`도 Deny 고려 — 큐 설정(DLQ, 보존기간 등) 변경 방지

---

### Case 04 — Queue Policy: SNS → SQS

**시나리오**: SNS 토픽이 SQS 큐에 메시지를 전송할 수 있도록 Queue Policy(Resource-based) 설정. 혼동 대리인 방지 포함.

**핵심 메커니즘**:
- Queue Policy: `Principal: {"Service": "sns.amazonaws.com"}`
- Allow: `sqs:SendMessage`
- Condition: `aws:SourceArn` → 특정 SNS 토픽 ARN만 허용

**허용**: 지정 SNS 토픽에서 SQS로 메시지 전송
**거부**: 다른 SNS 토픽, 다른 서비스에서의 전송

**주의사항**:
- `aws:SourceArn` 없이 `Principal: {"Service": "sns.amazonaws.com"}`만 쓰면 **모든** SNS 토픽이 전송 가능 → 반드시 조건 추가
- 암호화 큐(SSE-KMS)에 SNS가 메시지 보내려면 KMS Key Policy에 `sns.amazonaws.com` 서비스 주체의 `kms:GenerateDataKey*`, `kms:Decrypt` 허용 필요
- Queue Policy는 `aws sqs set-queue-attributes --attribute-names Policy` CLI로 설정
- 같은 계정 내 SNS → SQS는 Queue Policy만으로 충분 (IAM Policy 불필요)

---

### Case 05 — Queue Policy: S3 이벤트 알림

**시나리오**: S3 버킷의 이벤트 알림(ObjectCreated 등)이 SQS 큐로 전송되도록 Queue Policy 설정.

**핵심 메커니즘**:
- Queue Policy: `Principal: {"Service": "s3.amazonaws.com"}`
- Allow: `sqs:SendMessage`
- Condition: `aws:SourceArn` → 특정 S3 버킷 ARN, `aws:SourceAccount` → 버킷 소유 계정

**허용**: 지정 S3 버킷의 이벤트 알림 수신
**거부**: 다른 버킷, 다른 서비스에서의 전송

**주의사항**:
- S3 이벤트 알림은 **FIFO 큐 사용 불가** — Standard 큐만 지원
- `aws:SourceAccount` 조건 추가 권장 — 버킷 이름은 글로벌 유니크이므로 다른 계정의 동명 버킷 방지
- S3 버킷 알림 설정(`PutBucketNotificationConfiguration`)은 버킷 소유자가 수행 — Queue Policy가 먼저 설정되어 있어야 함
- 암호화 큐 사용 시 KMS Key Policy에 `s3.amazonaws.com` 허용 필요

---

### Case 06 — TLS 강제 + Org 외부 차단

**시나리오**: HTTP(비암호화) 요청 차단 + Organization 외부 Principal의 접근 차단. 이중 보안.

**핵심 메커니즘**:
- Deny: `aws:SecureTransport: "false"` → 모든 SQS Action (TLS 강제)
- Deny: `aws:PrincipalOrgID` ≠ `ORG_ID` → Organization 외부 차단

**허용**: Organization 내부 + HTTPS 요청만
**거부**: HTTP 요청, Organization 외부 Principal → `AccessDenied`

**주의사항**:
- `aws:SecureTransport` Deny는 Queue Policy(Resource-based)에 넣는 것이 일반적
- CloudShell은 항상 HTTPS → 검증에 영향 없음
- `aws:PrincipalOrgID`는 AWS 서비스 주체(SNS, S3 등)에는 적용 안 됨 → 서비스 연동 시 별도 Statement 필요
- 두 Deny를 같은 Statement에 넣으면 AND 조건 → 별도 Statement로 분리해야 각각 독립 적용

---

### Case 07 — 태그 기반 ABAC

**시나리오**: 큐의 `Team` 태그와 IAM 사용자의 `PrincipalTag/Team`이 일치할 때만 접근 허용.

**핵심 메커니즘**:
- `aws:ResourceTag/Team` + `StringEquals` + `${aws:PrincipalTag/Team}` 동적 매칭
- Deny: `aws:PrincipalTag/Team` `Null: "true"` → 태그 없는 사용자 전면 차단

**허용**: `PrincipalTag/Team = orders` → `ResourceTag/Team = orders` 큐만
**거부**: 태그 불일치 또는 태그 미설정 시 `AccessDenied`

**주의사항**:
- `sqs:ListQueues`는 태그 조건 적용 불가 → `Resource: "*"` 별도 Statement 필요
- 큐 생성 시 태그 강제는 `aws:RequestTag/Team` + `Null` 조건으로 별도 구현
- `sqs:TagQueue`/`sqs:UntagQueue` 권한도 제어해야 태그 변경으로 우회 방지
- FIFO 큐도 동일하게 태그 기반 제어 가능

---

## 크로스 계정 불가 Actions (함정)

다음 Actions는 Queue Policy에서 외부 계정에 부여해도 동작하지 않음:

```
sqs:CreateQueue, sqs:DeleteQueue, sqs:SetQueueAttributes,
sqs:AddPermission, sqs:RemovePermission,
sqs:TagQueue, sqs:UntagQueue, sqs:ListQueues, sqs:ListQueueTags
```

---

## CloudShell 준비

```bash
export AWS_REGION="ap-northeast-2"
export ACCOUNT_ID="123456789012"
export QUEUE_NAME="prod-orders"
export QUEUE_URL="https://sqs.$AWS_REGION.amazonaws.com/$ACCOUNT_ID/$QUEUE_NAME"
export USER_NAME="mod3-sqs-user"
export PROFILE_NAME="mod3-sqs-user"
```

---

## 검증 예시

```bash
# 메시지 전송 — 성공 기대
aws sqs send-message \
  --queue-url "$QUEUE_URL" \
  --message-body "test-message" \
  --profile "$PROFILE_NAME"

# 메시지 수신 — Consumer 역할이면 성공, Producer면 AccessDenied
aws sqs receive-message \
  --queue-url "$QUEUE_URL" \
  --profile "$PROFILE_NAME"

# 큐 삭제 — AccessDenied 기대
aws sqs delete-queue \
  --queue-url "$QUEUE_URL" \
  --profile "$PROFILE_NAME"
```

---

## 감점 방지 포인트

- SNS → SQS 연동 시 Queue Policy에 `"Service": "sns.amazonaws.com"` + `aws:SourceArn` 조건 필수
- 암호화 큐에 서비스가 메시지 보내려면 KMS Key Policy에도 서비스 주체 허용 필요
- `sqs:PurgeQueue`는 `DeleteQueue`와 별도 — 둘 다 Deny해야 완전 차단
- FIFO 큐는 S3 이벤트 알림 대상으로 사용 불가 (Standard만 가능)
- DLQ Consumer는 소스 큐의 KMS 키에 대한 `kms:Decrypt`도 필요
