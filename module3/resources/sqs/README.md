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
