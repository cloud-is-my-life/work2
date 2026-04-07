# SQS Fine-grained IAM 실전 가이드

> AWS Skills Competition 2026 대비. SQS Queue Policy + KMS 조합은 매년 출제 빈도가 높다.

---

## 목차

1. [IAM Policy vs Queue Policy 평가 로직](#1-iam-policy-vs-queue-policy-평가-로직)
2. [크로스 계정 불가 Action 완전 목록](#2-크로스-계정-불가-action-완전-목록)
3. [케이스별 정책 설명 (Case 01~07)](#3-케이스별-정책-설명-case-0107)
4. [신규 케이스 (Case 08~12)](#4-신규-케이스-case-0812)
5. [SNS → SQS → Lambda 파이프라인 권한 설계](#5-sns--sqs--lambda-파이프라인-권한-설계)
6. [KMS 연동 핵심 정리](#6-kms-연동-핵심-정리)
7. [검증 루틴](#7-검증-루틴)

---

## 1. IAM Policy vs Queue Policy 평가 로직

SQS 접근 제어에서 가장 많이 틀리는 부분이 바로 이 평가 로직이다. 두 정책이 동시에 존재할 때 AWS가 어떻게 판단하는지 정확히 알아야 한다.

### 같은 계정 (Same Account)

```
최종 결과 = IAM Policy Allow ∪ Queue Policy Allow
           (단, Explicit Deny가 있으면 무조건 거부)
```

같은 계정 내에서는 IAM Policy와 Queue Policy 중 하나만 Allow해도 접근이 허용된다. 합집합 원칙이다.

예를 들어 IAM Policy에 `sqs:SendMessage`가 없어도 Queue Policy에 해당 IAM 사용자 ARN을 Allow로 넣으면 전송이 된다. 반대도 마찬가지다.

### 크로스 계정 (Cross Account)

```
최종 결과 = IAM Policy Allow ∩ Queue Policy Allow
           (둘 다 Allow여야 접근 가능)
```

크로스 계정에서는 교집합이다. Queue Policy에 외부 계정 Allow가 있어도, 외부 계정의 IAM Policy에도 해당 Action이 Allow되어 있어야 한다. 어느 한쪽만 있으면 `AccessDenied`다.

### 서비스 주체 (SNS, S3, EventBridge 등)

AWS 서비스가 SQS에 메시지를 보내는 경우는 Queue Policy(Resource-based Policy)만으로 제어한다. IAM Policy는 사람(사용자/역할)에게 붙이는 것이고, 서비스 주체는 Queue Policy의 `Principal.Service`로 제어한다.

```
서비스 → SQS: Queue Policy만 필요
사람(같은 계정) → SQS: IAM Policy 또는 Queue Policy (합집합)
사람(다른 계정) → SQS: IAM Policy AND Queue Policy (교집합)
```

### Explicit Deny 우선 원칙

어디에 있든 Explicit Deny는 모든 Allow를 이긴다. IAM Policy에 Deny가 있으면 Queue Policy의 Allow가 있어도 거부된다. 반대도 동일하다.

---

## 2. 크로스 계정 불가 Action 완전 목록

Queue Policy에서 외부 계정 Principal에게 아래 Action을 부여해도 실제로는 동작하지 않는다. 이 Action들은 큐 소유 계정의 IAM 주체만 실행할 수 있다.

| Action | 이유 |
|---|---|
| `sqs:CreateQueue` | 큐 생성은 소유 계정에서만 가능 |
| `sqs:DeleteQueue` | 큐 삭제는 소유 계정에서만 가능 |
| `sqs:SetQueueAttributes` | 큐 속성 변경은 소유 계정에서만 가능 |
| `sqs:AddPermission` | Queue Policy 직접 수정은 소유 계정에서만 가능 |
| `sqs:RemovePermission` | Queue Policy 직접 수정은 소유 계정에서만 가능 |
| `sqs:TagQueue` | 태그 관리는 소유 계정에서만 가능 |
| `sqs:UntagQueue` | 태그 관리는 소유 계정에서만 가능 |
| `sqs:ListQueues` | 리소스 수준 제어 자체가 불가 (`Resource: "*"` 필수) |
| `sqs:ListQueueTags` | 태그 조회는 소유 계정에서만 가능 |

크로스 계정에서 허용 가능한 Action은 실질적으로 메시지 송수신 관련(`SendMessage`, `ReceiveMessage`, `DeleteMessage`, `ChangeMessageVisibility`, `GetQueueAttributes`, `GetQueueUrl`)으로 제한된다.

---

## 3. 케이스별 정책 설명 (Case 01~07)

### Case 01 — Producer 전용

`sqs:SendMessage`만 허용. `ReceiveMessage`, `DeleteMessage`, 큐 관리 Action은 모두 차단된다.

주의: `sqs:ListQueues`는 큐 ARN을 `Resource`로 지정할 수 없다. 반드시 `"Resource": "*"`로 별도 Statement를 추가해야 한다.

```
파일: policies/case01-producer-only.json
```

### Case 02 — Consumer 전용

`ReceiveMessage`, `DeleteMessage`, `ChangeMessageVisibility`, `GetQueueAttributes`를 허용. `SendMessage`와 큐 관리는 차단된다.

`ChangeMessageVisibility`를 빠뜨리면 처리 시간이 길어질 때 메시지가 재처리되는 상황을 제어할 수 없다. 반드시 포함해야 한다.

```
파일: policies/case02-consumer-only.json
```

### Case 03 — 큐 삭제/퍼지 차단

`sqs:DeleteQueue`와 `sqs:PurgeQueue`를 Explicit Deny로 차단. `DeleteMessage`(개별 메시지 삭제)는 Consumer에 필수이므로 건드리지 않는다.

`PurgeQueue`는 `DeleteQueue`와 별개 Action이다. 둘 다 Deny해야 완전히 막힌다.

```
파일: policies/case03-deny-delete-purge.json
```

### Case 04 — Queue Policy: SNS → SQS

Queue Policy에서 `Principal.Service: sns.amazonaws.com`을 허용. `aws:SourceArn` 조건으로 특정 SNS 토픽만 허용해야 한다. 조건 없이 서비스 주체만 허용하면 같은 리전의 모든 SNS 토픽이 메시지를 보낼 수 있다.

암호화 큐(SSE-KMS)라면 KMS Key Policy에도 `sns.amazonaws.com`의 `kms:GenerateDataKey*`, `kms:Decrypt`를 허용해야 한다. Queue Policy만으로는 부족하다.

```
파일: policies/case04-queue-policy-sns.json
```

### Case 05 — Queue Policy: S3 이벤트 알림

`Principal.Service: s3.amazonaws.com`으로 S3 이벤트 알림을 허용. `aws:SourceArn`(버킷 ARN)과 `aws:SourceAccount`(버킷 소유 계정)를 함께 쓰는 것이 안전하다.

S3 이벤트 알림은 FIFO 큐를 지원하지 않는다. Standard 큐만 사용 가능하다.

```
파일: policies/case05-queue-policy-s3-event.json
```

### Case 06 — TLS 강제 + Org 외부 차단

`aws:SecureTransport: "false"` 조건으로 HTTP 요청을 Deny. `aws:PrincipalOrgID` 조건으로 Organization 외부 Principal을 Deny.

두 Deny를 같은 Statement에 넣으면 AND 조건이 된다. 각각 독립적으로 적용하려면 별도 Statement로 분리해야 한다.

```
파일: policies/case06-deny-unsecure-transport.json
```

### Case 07 — 태그 기반 ABAC

`aws:ResourceTag/Environment`와 `${aws:PrincipalTag/Environment}`를 `StringEquals`로 비교. 태그가 없는 사용자는 `Null` 조건으로 전면 차단한다.

`sqs:ListQueues`는 태그 조건 적용이 불가하므로 `Resource: "*"` 별도 Statement가 필요하다.

```
파일: policies/case07-abac-tag-based.json
```

---

## 4. 신규 케이스 (Case 08~12)

### Case 08 — DLQ Consumer + KMS Decrypt

**시나리오**: Dead Letter Queue에서 실패 메시지를 수신하는 워커. 소스 큐가 SSE-KMS로 암호화되어 있을 때.

**핵심**: DLQ에 저장된 메시지는 소스 큐(원본 큐)의 KMS 키로 암호화된 상태로 이동한다. DLQ 자체에 별도 KMS 키가 없어도 소스 큐의 KMS 키로 복호화해야 읽을 수 있다. 따라서 DLQ Consumer의 IAM Policy에는 소스 큐 KMS 키에 대한 `kms:Decrypt`가 반드시 포함되어야 한다.

```json
{
  "Sid": "AllowKMSDecryptForDLQ",
  "Effect": "Allow",
  "Action": ["kms:Decrypt", "kms:GenerateDataKey"],
  "Resource": "arn:aws:kms:REGION:ACCOUNT_ID:key/SOURCE_QUEUE_KMS_KEY_ID"
}
```

`kms:GenerateDataKey`는 DLQ Consumer가 메시지를 다시 원본 큐로 재전송(redrive)할 때 필요하다. 수신만 한다면 `kms:Decrypt`만으로 충분하다.

```
파일: policies/case08-dlq-consumer-kms.json
```

### Case 09 — FIFO 큐 전용 Producer

**시나리오**: 특정 FIFO 큐에만 메시지를 전송하고, 실수로 Standard 큐에 전송하는 것을 방지.

**핵심**: FIFO 큐 ARN은 반드시 `.fifo` 접미사가 붙는다. IAM Policy의 `Resource`에도 `.fifo`를 포함해야 한다.

```
arn:aws:sqs:ap-northeast-2:123456789012:my-queue.fifo
```

FIFO 큐에 메시지를 보낼 때 `MessageGroupId`는 필수 파라미터다. IAM 권한과는 무관하지만, 누락 시 `InvalidParameterValue` 오류가 발생한다. 권한 문제로 혼동하기 쉬운 함정이다.

`ContentBasedDeduplication`이 비활성화된 FIFO 큐라면 `MessageDeduplicationId`도 필수다.

`NotResource`를 활용해 지정 FIFO 큐 외의 모든 큐에 `SendMessage`를 Deny하면 실수를 방지할 수 있다.

```
파일: policies/case09-fifo-producer.json
```

### Case 10 — Queue Policy: EventBridge → SQS

**시나리오**: EventBridge 규칙이 SQS 큐를 타겟으로 이벤트를 전달.

**핵심**: EventBridge의 서비스 주체는 `events.amazonaws.com`이다. SNS의 `sns.amazonaws.com`과 혼동하지 않도록 주의.

```json
{
  "Principal": {"Service": "events.amazonaws.com"},
  "Action": "sqs:SendMessage",
  "Condition": {
    "ArnLike": {
      "aws:SourceArn": "arn:aws:events:REGION:ACCOUNT_ID:rule/RULE_NAME"
    }
  }
}
```

`aws:SourceArn`에 규칙 ARN을 지정하지 않으면 같은 리전의 모든 EventBridge 규칙이 이 큐에 메시지를 보낼 수 있다. 혼동 대리인(Confused Deputy) 공격 방지를 위해 반드시 특정 규칙 ARN으로 제한해야 한다.

암호화 큐라면 KMS Key Policy에 `events.amazonaws.com`의 `kms:GenerateDataKey*`, `kms:Decrypt`도 허용해야 한다.

```
파일: policies/case10-queue-policy-eventbridge.json
```

### Case 11 — Queue Policy: Lambda 트리거

**시나리오**: Lambda Event Source Mapping으로 SQS 큐를 Lambda 함수의 트리거로 설정.

**핵심**: Lambda가 SQS를 폴링하는 실제 권한은 Lambda 실행 역할(IAM Role)의 Policy가 주 제어 포인트다. Queue Policy의 `lambda.amazonaws.com` Principal은 같은 계정 내에서는 선택적이지만, 크로스 계정 Lambda 트리거 시에는 필수다.

Lambda 실행 역할에 필요한 최소 권한:

```json
{
  "Action": [
    "sqs:ReceiveMessage",
    "sqs:DeleteMessage",
    "sqs:GetQueueAttributes"
  ]
}
```

`sqs:ChangeMessageVisibility`는 Lambda가 처리 시간을 연장할 때 필요하다. 처리 시간이 `VisibilityTimeout`을 초과할 가능성이 있다면 포함하는 것이 좋다.

암호화 큐라면 Lambda 실행 역할에 `kms:Decrypt`도 추가해야 한다.

```
파일: policies/case11-queue-policy-lambda-trigger.json
```

### Case 12 — 큐 설정 변경 차단 (SetQueueAttributes Deny)

**시나리오**: 일반 사용자는 메시지 송수신만 가능하고, DLQ 연결/메시지 보존기간/암호화 설정 등 큐 속성 변경은 차단.

**핵심**: `sqs:SetQueueAttributes` 하나로 다음 모든 속성을 변경할 수 있다.

| 속성 | 설명 |
|---|---|
| `RedrivePolicy` | DLQ 연결 및 maxReceiveCount 설정 |
| `MessageRetentionPeriod` | 메시지 보존기간 (60초~14일) |
| `KmsMasterKeyId` | SSE-KMS 키 변경 또는 암호화 해제 |
| `VisibilityTimeout` | 메시지 가시성 타임아웃 |
| `ReceiveMessageWaitTimeSeconds` | Long Polling 대기 시간 |

이 중 하나라도 무단 변경되면 운영 장애나 보안 사고로 이어질 수 있다. Explicit Deny로 차단하는 것이 안전하다.

`DeleteQueue`와 `PurgeQueue`도 함께 Deny하는 것이 일반적이다.

```
파일: policies/case12-deny-set-queue-attributes.json
```

---

## 5. SNS → SQS → Lambda 파이프라인 권한 설계

실전에서 자주 나오는 3단 파이프라인이다. 각 구간마다 필요한 권한이 다르다.

```
SNS Topic → SQS Queue → Lambda Function
```

### 구간 1: SNS → SQS

Queue Policy(Resource-based)로 제어한다. IAM Policy로는 해결할 수 없다.

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "AllowSNSToSend",
    "Effect": "Allow",
    "Principal": {"Service": "sns.amazonaws.com"},
    "Action": "sqs:SendMessage",
    "Resource": "arn:aws:sqs:REGION:ACCOUNT_ID:QUEUE_NAME",
    "Condition": {
      "ArnLike": {
        "aws:SourceArn": "arn:aws:sns:REGION:ACCOUNT_ID:TOPIC_NAME"
      }
    }
  }]
}
```

큐가 SSE-KMS로 암호화되어 있다면 KMS Key Policy에도 추가해야 한다.

```json
{
  "Sid": "AllowSNSKMS",
  "Effect": "Allow",
  "Principal": {"Service": "sns.amazonaws.com"},
  "Action": ["kms:GenerateDataKey*", "kms:Decrypt"],
  "Resource": "*"
}
```

### 구간 2: SQS → Lambda (Event Source Mapping)

Lambda 실행 역할(IAM Role)에 SQS 폴링 권한을 부여한다.

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "AllowSQSPolling",
    "Effect": "Allow",
    "Action": [
      "sqs:ReceiveMessage",
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes"
    ],
    "Resource": "arn:aws:sqs:REGION:ACCOUNT_ID:QUEUE_NAME"
  }]
}
```

큐가 SSE-KMS로 암호화되어 있다면 Lambda 실행 역할에도 KMS 권한이 필요하다.

```json
{
  "Sid": "AllowKMSForSQS",
  "Effect": "Allow",
  "Action": ["kms:Decrypt"],
  "Resource": "arn:aws:kms:REGION:ACCOUNT_ID:key/KEY_ID"
}
```

### 구간 3: SNS 구독 설정

SNS 토픽에서 SQS 큐를 구독(Subscribe)하는 것은 SNS 토픽 소유자가 수행한다. 크로스 계정이라면 SNS 토픽 Policy에도 `sns:Subscribe`를 허용해야 한다.

### 전체 권한 체크리스트

```
[ ] SQS Queue Policy — sns.amazonaws.com SendMessage 허용 (aws:SourceArn 조건 포함)
[ ] KMS Key Policy — sns.amazonaws.com GenerateDataKey*, Decrypt 허용 (암호화 큐인 경우)
[ ] Lambda 실행 역할 — sqs:ReceiveMessage, DeleteMessage, GetQueueAttributes 허용
[ ] Lambda 실행 역할 — kms:Decrypt 허용 (암호화 큐인 경우)
[ ] SNS 구독 설정 — SQS 큐 ARN을 엔드포인트로 등록
[ ] Event Source Mapping — Lambda 콘솔 또는 CLI로 SQS 트리거 등록
```

---

## 6. KMS 연동 핵심 정리

SQS + KMS 조합은 경기에서 자주 나오는 함정이다. 권한이 여러 곳에 분산되어 있어서 하나라도 빠지면 전체가 동작하지 않는다.

### 서비스별 필요 KMS 권한

| 서비스 주체 | KMS Action | 시점 |
|---|---|---|
| SNS (`sns.amazonaws.com`) | `kms:GenerateDataKey*`, `kms:Decrypt` | 메시지 전송 시 |
| S3 (`s3.amazonaws.com`) | `kms:GenerateDataKey*`, `kms:Decrypt` | 이벤트 알림 전송 시 |
| EventBridge (`events.amazonaws.com`) | `kms:GenerateDataKey*`, `kms:Decrypt` | 이벤트 전달 시 |
| Lambda 실행 역할 | `kms:Decrypt` | 메시지 수신 시 |
| DLQ Consumer | `kms:Decrypt` | DLQ 메시지 수신 시 (소스 큐 키 사용) |

### KMS Key Policy 예시 (SNS용)

```json
{
  "Sid": "AllowSNSToUseKey",
  "Effect": "Allow",
  "Principal": {"Service": "sns.amazonaws.com"},
  "Action": [
    "kms:GenerateDataKey*",
    "kms:Decrypt"
  ],
  "Resource": "*",
  "Condition": {
    "ArnLike": {
      "aws:SourceArn": "arn:aws:sns:REGION:ACCOUNT_ID:TOPIC_NAME"
    }
  }
}
```

### 자주 나오는 오류 패턴

- Queue Policy는 맞는데 KMS Key Policy 누락 → `KMS.KMSInvalidStateException` 또는 `AccessDenied`
- DLQ Consumer가 DLQ 키만 허용하고 소스 큐 키 누락 → 메시지 수신 시 `AccessDenied`
- Lambda 실행 역할에 SQS 권한은 있는데 KMS Decrypt 누락 → Event Source Mapping 폴링 실패

---

## 7. 검증 루틴

### 환경 변수 설정

```bash
export AWS_REGION="ap-northeast-2"
export ACCOUNT_ID="123456789012"
export QUEUE_NAME="prod-orders"
export DLQ_NAME="prod-orders-dlq"
export QUEUE_URL="https://sqs.$AWS_REGION.amazonaws.com/$ACCOUNT_ID/$QUEUE_NAME"
export DLQ_URL="https://sqs.$AWS_REGION.amazonaws.com/$ACCOUNT_ID/$DLQ_NAME"
export PROFILE_NAME="mod3-sqs-user"
```

### Queue Policy 적용

```bash
# Queue Policy를 파일로 적용
aws sqs set-queue-attributes \
  --queue-url "$QUEUE_URL" \
  --attributes Policy="$(cat policies/case04-queue-policy-sns.json)"
```

### 메시지 전송/수신 검증

```bash
# 메시지 전송 — Producer 역할이면 성공
aws sqs send-message \
  --queue-url "$QUEUE_URL" \
  --message-body "test-$(date +%s)" \
  --profile "$PROFILE_NAME"

# 메시지 수신 — Consumer 역할이면 성공
aws sqs receive-message \
  --queue-url "$QUEUE_URL" \
  --wait-time-seconds 5 \
  --profile "$PROFILE_NAME"

# 큐 삭제 — Deny 정책이면 AccessDenied
aws sqs delete-queue \
  --queue-url "$QUEUE_URL" \
  --profile "$PROFILE_NAME"
```

### FIFO 큐 메시지 전송 검증

```bash
export FIFO_URL="https://sqs.$AWS_REGION.amazonaws.com/$ACCOUNT_ID/my-queue.fifo"

# MessageGroupId 필수 — 없으면 InvalidParameterValue (권한 문제 아님)
aws sqs send-message \
  --queue-url "$FIFO_URL" \
  --message-body "fifo-test" \
  --message-group-id "group-1" \
  --message-deduplication-id "$(date +%s)" \
  --profile "$PROFILE_NAME"
```

### IAM Policy 시뮬레이터로 사전 검증

```bash
aws iam simulate-principal-policy \
  --policy-source-arn "arn:aws:iam::$ACCOUNT_ID:user/$PROFILE_NAME" \
  --action-names sqs:SendMessage sqs:DeleteQueue sqs:PurgeQueue \
  --resource-arns "arn:aws:sqs:$AWS_REGION:$ACCOUNT_ID:$QUEUE_NAME"
```

시뮬레이터 결과는 1차 검증용이다. 실제 호출 결과와 다를 수 있으므로 채점 증빙은 실제 CLI 호출 결과로 준비하는 것이 안전하다.

---

## 감점 방지 포인트

- SNS/S3/EventBridge → SQS 연동 시 Queue Policy에 서비스 주체 + `aws:SourceArn` 조건 필수
- 암호화 큐에 서비스가 메시지를 보내려면 KMS Key Policy에도 서비스 주체 허용 필요
- DLQ Consumer는 소스 큐의 KMS 키에 대한 `kms:Decrypt` 필요 (DLQ 키가 아님)
- FIFO 큐 ARN은 `.fifo` 접미사 포함 필수
- `MessageGroupId` 누락은 IAM 권한 문제가 아님 — 혼동 주의
- `sqs:PurgeQueue`와 `sqs:DeleteQueue`는 별개 Action — 둘 다 Deny해야 완전 차단
- `sqs:ListQueues`는 `Resource: "*"` 필수 — 큐 ARN 지정 불가
- 크로스 계정에서 `SetQueueAttributes`, `DeleteQueue` 등 관리 Action은 Queue Policy로 부여해도 동작 안 함
