# SNS Fine-grained IAM 실전 가이드

> AWS Skills Competition 2026 대비. SNS Topic Policy와 IAM Policy를 조합해 서비스 연동 시나리오를 완벽하게 제어하는 방법을 정리했다.

---

## 목차

1. [기존 케이스 요약 (case01~06)](#1-기존-케이스-요약)
2. [신규 케이스 (case07~11)](#2-신규-케이스)
3. [Topic Policy vs IAM Policy 평가 로직](#3-topic-policy-vs-iam-policy-평가-로직)
4. [sns:Protocol / sns:Endpoint 조건 키 실전 활용](#4-snsprotocol--snsendpoint-조건-키-실전-활용)
5. [SSE 토픽 + 서비스 연동 시 KMS 권한 설계](#5-sse-토픽--서비스-연동-시-kms-권한-설계)
6. [검증 루틴](#6-검증-루틴)

---

## 1. 기존 케이스 요약

| 케이스 | 파일 | 핵심 |
|--------|------|------|
| case01 | `case01-publish-only.json` | 특정 토픽에 `sns:Publish`만 허용. `ListTopics`는 `Resource: "*"` 필수 |
| case02 | `case02-subscribe-https-only.json` | `sns:Protocol: "https"` 조건으로 HTTPS 구독만 허용. Deny로 비HTTPS 차단 |
| case03 | `case03-deny-delete-topic.json` | `sns:DeleteTopic`, `sns:RemovePermission` Explicit Deny. 토픽 보호 |
| case04 | `case04-topic-policy-sqs.json` | Topic Policy로 SQS 구독 허용 + 크로스 계정 Publish 제어 |
| case05 | `case05-topic-policy-s3-event.json` | S3 이벤트 알림 수신. `aws:SourceArn` + `aws:SourceAccount` 조합 |
| case06 | `case06-abac-tag-based.json` | `PrincipalTag/Team` = `ResourceTag/Team` 동적 매칭 ABAC |

---

## 2. 신규 케이스

### Case 07 — TLS 강제 (aws:SecureTransport Deny)

**시나리오**: HTTP로 SNS API를 호출하는 것을 전면 차단. 모든 요청이 TLS(HTTPS)를 통해서만 가능하도록 강제한다.

**핵심 메커니즘**:
- `Deny`: `sns:*` + `aws:SecureTransport: "false"` 조건
- Allow Statement는 별도로 필요한 액션만 명시

**정책 파일**: [case07-tls-enforce.json](./policies/case07-tls-enforce.json)

```json
{
  "Sid": "DenyNonTLS",
  "Effect": "Deny",
  "Action": "sns:*",
  "Resource": "arn:aws:sns:AWS_REGION:ACCOUNT_ID:TOPIC_NAME",
  "Condition": {
    "Bool": {
      "aws:SecureTransport": "false"
    }
  }
}
```

**주의사항**:
- `aws:SecureTransport`는 Bool 타입. `"false"` (문자열)로 작성해야 한다. `false` (불리언)로 쓰면 일부 평가 엔진에서 오동작 가능
- SSE-KMS 토픽은 이미 HTTPS를 강제하지만, 명시적 Deny를 추가하면 감사(Audit) 로그에서 의도가 명확해진다
- IAM Policy에 적용하면 해당 사용자/역할 전체에 적용. Topic Policy에 적용하면 해당 토픽에 접근하는 모든 Principal에 적용

---

### Case 08 — Topic Policy: CloudWatch Alarm 알림 수신

**시나리오**: CloudWatch Alarm이 상태 변경 시 SNS 토픽으로 알림을 보낼 수 있도록 Topic Policy를 설정한다.

**핵심 메커니즘**:
- `Principal: {"Service": "cloudwatch.amazonaws.com"}`
- `aws:SourceArn`: 특정 계정의 알람만 허용 (와일드카드로 전체 알람 허용 가능)
- `aws:SourceAccount`: confused deputy 방지

**정책 파일**: [case08-topic-policy-cloudwatch-alarm.json](./policies/case08-topic-policy-cloudwatch-alarm.json)

```json
{
  "Sid": "AllowCloudWatchAlarmPublish",
  "Effect": "Allow",
  "Principal": {
    "Service": "cloudwatch.amazonaws.com"
  },
  "Action": "sns:Publish",
  "Resource": "arn:aws:sns:AWS_REGION:ACCOUNT_ID:TOPIC_NAME",
  "Condition": {
    "ArnLike": {
      "aws:SourceArn": "arn:aws:cloudwatch:AWS_REGION:ACCOUNT_ID:alarm:*"
    },
    "StringEquals": {
      "aws:SourceAccount": "ACCOUNT_ID"
    }
  }
}
```

**주의사항**:
- `aws:SourceArn`에 `ArnLike`를 쓰면 와일드카드(`*`)로 계정 내 모든 알람을 허용할 수 있다. 특정 알람만 허용하려면 정확한 ARN을 `ArnEquals`로 지정
- CloudWatch Composite Alarm도 동일한 서비스 주체(`cloudwatch.amazonaws.com`)를 사용
- SSE-KMS 토픽이라면 KMS 키 정책에 `cloudwatch.amazonaws.com`의 `kms:GenerateDataKey*`, `kms:Decrypt` 권한도 추가해야 한다

---

### Case 09 — Topic Policy: Lambda 구독만 허용

**시나리오**: 토픽 구독을 Lambda 함수로만 제한한다. SQS, HTTP, 이메일 등 다른 프로토콜 구독은 차단.

**핵심 메커니즘**:
- Allow: `sns:Subscribe` + `sns:Protocol: "lambda"` + `sns:Endpoint`를 Lambda ARN 패턴으로 제한
- Deny: `sns:Protocol`이 `"lambda"`가 아닌 모든 구독 시도 차단

**정책 파일**: [case09-topic-policy-lambda-subscribe.json](./policies/case09-topic-policy-lambda-subscribe.json)

```json
{
  "Sid": "AllowLambdaSubscribeOnly",
  "Effect": "Allow",
  "Principal": {
    "AWS": "arn:aws:iam::ACCOUNT_ID:root"
  },
  "Action": "sns:Subscribe",
  "Resource": "arn:aws:sns:AWS_REGION:ACCOUNT_ID:TOPIC_NAME",
  "Condition": {
    "StringEquals": {
      "sns:Protocol": "lambda"
    },
    "ArnLike": {
      "sns:Endpoint": "arn:aws:lambda:AWS_REGION:ACCOUNT_ID:function:*"
    }
  }
}
```

**주의사항**:
- `sns:Endpoint`에 Lambda ARN 패턴을 지정하면 다른 계정의 Lambda 함수 구독도 차단할 수 있다
- Lambda 함수가 SNS 구독을 받으려면 Lambda 리소스 기반 정책에도 `sns:InvokeFunction` 허용이 필요하다 (SNS가 Lambda를 호출하는 권한)
- `Principal: {"AWS": "ACCOUNT_ID:root"}`는 해당 계정의 모든 IAM 엔티티를 포함. 특정 역할만 허용하려면 역할 ARN을 명시

---

### Case 10 — 토픽 생성 시 필수 태그 강제

**시나리오**: `sns:CreateTopic` 호출 시 `Team`과 `Environment` 태그가 없으면 생성을 차단한다. 태그 없는 토픽이 생성되는 것을 원천 봉쇄.

**핵심 메커니즘**:
- Allow: `sns:CreateTopic` + `aws:RequestTag/Team`, `aws:RequestTag/Environment` 모두 `Null: "false"` 조건
- Deny: 각 필수 태그가 `Null: "true"`이면 차단

**정책 파일**: [case10-enforce-tags-on-create.json](./policies/case10-enforce-tags-on-create.json)

```json
{
  "Sid": "DenyCreateTopicWithoutRequiredTags",
  "Effect": "Deny",
  "Action": "sns:CreateTopic",
  "Resource": "*",
  "Condition": {
    "Null": {
      "aws:RequestTag/Team": "true"
    }
  }
}
```

**주의사항**:
- `aws:RequestTag`는 `CreateTopic` 호출 시 함께 전달되는 태그에만 적용. 생성 후 `TagResource`로 추가하는 태그는 별도 Statement로 제어
- `aws:TagKeys`로 허용/금지 태그 키 목록을 제어할 수도 있다. 예를 들어 `ForAllValues:StringEquals`로 허용된 키만 사용 가능하게 강제
- Deny Statement를 두 개로 분리하면 어떤 태그가 누락됐는지 CloudTrail 로그에서 더 명확하게 추적 가능

---

### Case 11 — 크로스 계정 Publish: Organization 내부만 허용

**시나리오**: 여러 AWS 계정이 하나의 SNS 토픽에 메시지를 발행해야 하는 상황. Organization 내부 계정만 허용하고 외부 계정은 전면 차단.

**핵심 메커니즘**:
- Topic Policy: `Principal: {"AWS": "*"}` + `aws:PrincipalOrgID` 조건
- Deny: `aws:PrincipalOrgID`가 지정 Org ID와 다른 경우 차단

**정책 파일**: [case11-cross-account-org-publish.json](./policies/case11-cross-account-org-publish.json)

```json
{
  "Sid": "AllowCrossAccountPublishWithinOrg",
  "Effect": "Allow",
  "Principal": {
    "AWS": "*"
  },
  "Action": "sns:Publish",
  "Resource": "arn:aws:sns:AWS_REGION:ACCOUNT_ID:TOPIC_NAME",
  "Condition": {
    "StringEquals": {
      "aws:PrincipalOrgID": "o-ORGANIZATION_ID"
    }
  }
}
```

**주의사항**:
- `aws:PrincipalOrgID`는 IAM 사용자, 역할, 서비스 주체 모두에 적용된다. AWS 서비스(예: Lambda)가 다른 계정에서 Publish할 때도 해당 서비스의 Organization 멤버십이 확인된다
- 크로스 계정 Publish는 Topic Policy만으로는 부족하다. 발신 계정의 IAM Policy에도 `sns:Publish` 허용이 있어야 한다 (교집합 평가)
- Organization ID는 `aws organizations describe-organization` 명령으로 확인 가능

---

## 3. Topic Policy vs IAM Policy 평가 로직

SNS 접근 제어에서 가장 헷갈리는 부분이 바로 Topic Policy(리소스 기반 정책)와 IAM Policy(자격 증명 기반 정책)의 관계다.

### 같은 계정 내 접근

```
결과 = (IAM Policy Allow) OR (Topic Policy Allow)
단, Explicit Deny가 어느 쪽에든 있으면 최우선 차단
```

같은 계정이라면 둘 중 하나만 Allow해도 접근이 허용된다. 예를 들어 IAM Policy에 `sns:Publish`가 없어도 Topic Policy에 해당 사용자 ARN에 대한 Allow가 있으면 Publish가 된다.

### 크로스 계정 접근

```
결과 = (발신 계정 IAM Policy Allow) AND (수신 계정 Topic Policy Allow)
단, Explicit Deny가 어느 쪽에든 있으면 최우선 차단
```

크로스 계정은 반드시 양쪽 모두 Allow가 있어야 한다. Topic Policy만 열어놔도 발신 계정 IAM Policy가 없으면 차단된다.

### AWS 서비스 주체 (S3, CloudWatch 등)

```
결과 = Topic Policy Allow (IAM Policy 불필요)
```

S3, CloudWatch 같은 AWS 서비스가 SNS에 Publish할 때는 Topic Policy만 있으면 된다. 서비스 주체는 IAM 사용자/역할이 아니므로 IAM Policy 평가 대상이 아니다.

### 평가 순서 요약

| 상황 | 필요한 정책 |
|------|------------|
| 같은 계정 IAM 사용자/역할 | IAM Policy OR Topic Policy (하나만 있어도 됨) |
| 크로스 계정 IAM 사용자/역할 | IAM Policy AND Topic Policy (둘 다 필요) |
| AWS 서비스 주체 | Topic Policy만 필요 |
| Explicit Deny | 어디서든 최우선 차단 |

> 실전 팁: 경쟁 과제에서 "크로스 계정 Publish가 안 된다"는 상황이 나오면 발신 계정 IAM Policy와 수신 계정 Topic Policy를 모두 확인하자. 둘 중 하나만 봐서는 원인을 찾기 어렵다.

---

## 4. sns:Protocol / sns:Endpoint 조건 키 실전 활용

이 두 조건 키는 `Subscribe` 액션에만 적용된다. `Publish`에 걸어봤자 아무 효과가 없다.

### sns:Protocol 허용 값

| 값 | 설명 |
|----|------|
| `http` | HTTP 엔드포인트 |
| `https` | HTTPS 엔드포인트 |
| `email` | 이메일 (텍스트) |
| `email-json` | 이메일 (JSON 형식) |
| `sms` | SMS 문자 |
| `sqs` | SQS 큐 |
| `application` | 모바일 푸시 (APNs, GCM 등) |
| `lambda` | Lambda 함수 |
| `firehose` | Kinesis Data Firehose |

### 프로토콜 제한 패턴

**특정 프로토콜만 허용 (Allow + 조건)**:
```json
{
  "Effect": "Allow",
  "Action": "sns:Subscribe",
  "Resource": "arn:aws:sns:AWS_REGION:ACCOUNT_ID:TOPIC_NAME",
  "Condition": {
    "StringEquals": {
      "sns:Protocol": ["sqs", "lambda"]
    }
  }
}
```

**비보안 프로토콜 차단 (Deny)**:
```json
{
  "Effect": "Deny",
  "Action": "sns:Subscribe",
  "Resource": "*",
  "Condition": {
    "StringEquals": {
      "sns:Protocol": ["http", "email", "sms"]
    }
  }
}
```

### sns:Endpoint 활용

`sns:Endpoint`는 구독 대상 엔드포인트 값을 조건으로 건다. 와일드카드(`*`)를 지원한다.

```json
{
  "Effect": "Allow",
  "Action": "sns:Subscribe",
  "Resource": "arn:aws:sns:AWS_REGION:ACCOUNT_ID:TOPIC_NAME",
  "Condition": {
    "StringEquals": {
      "sns:Protocol": "sqs"
    },
    "ArnLike": {
      "sns:Endpoint": "arn:aws:sqs:AWS_REGION:ACCOUNT_ID:*"
    }
  }
}
```

이렇게 하면 같은 계정의 SQS 큐만 구독할 수 있고, 다른 계정의 SQS 큐 구독은 차단된다.

### 이메일 엔드포인트 주의사항

`sns:Endpoint`에서 이메일 주소는 소문자로 정규화된다. 정책에 `User@Example.com`으로 써도 `user@example.com`과 동일하게 매칭된다. 정책 작성 시 소문자로 통일하는 것이 혼란을 줄인다.

---

## 5. SSE 토픽 + 서비스 연동 시 KMS 권한 설계

SNS 토픽에 SSE-KMS(서버 측 암호화)를 적용하면 메시지가 KMS 키로 암호화된다. 이때 AWS 서비스(S3, CloudWatch, EventBridge 등)가 해당 토픽에 Publish하려면 KMS 키 정책에 해당 서비스 주체의 권한도 추가해야 한다.

### 왜 KMS 권한이 필요한가

SNS가 메시지를 저장할 때 KMS를 호출해 암호화한다. 이 과정에서 SNS는 메시지를 보낸 서비스 주체의 컨텍스트로 KMS를 호출한다. KMS 키 정책에 해당 서비스 주체가 없으면 KMS 호출이 거부되고 Publish 자체가 실패한다.

### KMS 키 정책 패턴

**S3 이벤트 알림 + SSE 토픽**:
```json
{
  "Sid": "AllowS3ToUseKey",
  "Effect": "Allow",
  "Principal": {
    "Service": "s3.amazonaws.com"
  },
  "Action": [
    "kms:GenerateDataKey*",
    "kms:Decrypt"
  ],
  "Resource": "*",
  "Condition": {
    "ArnLike": {
      "aws:SourceArn": "arn:aws:s3:::BUCKET_NAME"
    }
  }
}
```

**CloudWatch Alarm + SSE 토픽**:
```json
{
  "Sid": "AllowCloudWatchToUseKey",
  "Effect": "Allow",
  "Principal": {
    "Service": "cloudwatch.amazonaws.com"
  },
  "Action": [
    "kms:GenerateDataKey*",
    "kms:Decrypt"
  ],
  "Resource": "*",
  "Condition": {
    "StringEquals": {
      "aws:SourceAccount": "ACCOUNT_ID"
    }
  }
}
```

**EventBridge + SSE 토픽**:
```json
{
  "Sid": "AllowEventBridgeToUseKey",
  "Effect": "Allow",
  "Principal": {
    "Service": "events.amazonaws.com"
  },
  "Action": [
    "kms:GenerateDataKey*",
    "kms:Decrypt"
  ],
  "Resource": "*"
}
```

### 서비스별 KMS 권한 요약

| 서비스 | KMS Principal | 필요 액션 |
|--------|--------------|-----------|
| S3 이벤트 알림 | `s3.amazonaws.com` | `kms:GenerateDataKey*`, `kms:Decrypt` |
| CloudWatch Alarm | `cloudwatch.amazonaws.com` | `kms:GenerateDataKey*`, `kms:Decrypt` |
| EventBridge | `events.amazonaws.com` | `kms:GenerateDataKey*`, `kms:Decrypt` |
| Lambda (구독자) | Lambda 실행 역할 ARN | `kms:Decrypt` |
| SQS (구독자) | `sqs.amazonaws.com` 또는 큐 ARN | `kms:Decrypt` |

### 설계 원칙

1. KMS 키 정책에 `aws:SourceArn` 또는 `aws:SourceAccount` 조건을 추가해 confused deputy 공격을 방지한다.
2. SNS 토픽 정책과 KMS 키 정책을 함께 설계한다. 토픽 정책만 열어놓고 KMS 정책을 빠뜨리면 Publish가 실패한다.
3. 고객 관리형 KMS 키(CMK)를 사용해야 키 정책을 직접 제어할 수 있다. AWS 관리형 키(`aws/sns`)는 키 정책 수정이 불가능하다.

---

## 6. 검증 루틴

### 공통 변수

```bash
export AWS_REGION="ap-northeast-2"
export ACCOUNT_ID="123456789012"
export TOPIC_NAME="my-topic"
export TOPIC_ARN="arn:aws:sns:${AWS_REGION}:${ACCOUNT_ID}:${TOPIC_NAME}"
export ORG_ID="o-xxxxxxxxxxxx"
```

### Case 07 — TLS 강제 검증

```bash
# 성공 기대 (HTTPS)
aws sns publish \
  --topic-arn "$TOPIC_ARN" \
  --message "tls-test" \
  --region "$AWS_REGION"

# 실패 기대 (HTTP 강제 시도 — 실제로는 SDK가 HTTPS를 기본 사용하므로 시뮬레이터로 검증)
aws iam simulate-principal-policy \
  --policy-source-arn "arn:aws:iam::${ACCOUNT_ID}:user/test-user" \
  --action-names sns:Publish \
  --resource-arns "$TOPIC_ARN" \
  --context-entries "ContextKeyName=aws:SecureTransport,ContextKeyValues=false,ContextKeyType=boolean"
```

### Case 08 — CloudWatch Alarm 연동 검증

```bash
# 토픽 정책 적용
aws sns set-topic-attributes \
  --topic-arn "$TOPIC_ARN" \
  --attribute-name Policy \
  --attribute-value file://policies/case08-topic-policy-cloudwatch-alarm.json

# CloudWatch Alarm 생성 후 SNS 토픽 연결
aws cloudwatch put-metric-alarm \
  --alarm-name "test-alarm" \
  --metric-name CPUUtilization \
  --namespace AWS/EC2 \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1 \
  --alarm-actions "$TOPIC_ARN"
```

### Case 09 — Lambda 구독 제한 검증

```bash
# Lambda 구독 시도 (성공 기대)
aws sns subscribe \
  --topic-arn "$TOPIC_ARN" \
  --protocol lambda \
  --notification-endpoint "arn:aws:lambda:${AWS_REGION}:${ACCOUNT_ID}:function:my-function"

# SQS 구독 시도 (실패 기대)
aws sns subscribe \
  --topic-arn "$TOPIC_ARN" \
  --protocol sqs \
  --notification-endpoint "arn:aws:sqs:${AWS_REGION}:${ACCOUNT_ID}:my-queue"
```

### Case 10 — 필수 태그 강제 검증

```bash
# 성공 기대 (태그 포함)
aws sns create-topic \
  --name "tagged-topic" \
  --tags Key=Team,Value=platform Key=Environment,Value=prod

# 실패 기대 (태그 누락)
aws sns create-topic --name "untagged-topic"
```

### Case 11 — Organization 내부 Publish 검증

```bash
# 시뮬레이터로 Org 외부 계정 차단 확인
aws iam simulate-principal-policy \
  --policy-source-arn "arn:aws:iam::EXTERNAL_ACCOUNT_ID:user/external-user" \
  --action-names sns:Publish \
  --resource-arns "$TOPIC_ARN" \
  --context-entries "ContextKeyName=aws:PrincipalOrgID,ContextKeyValues=o-differentorgid,ContextKeyType=string"
```

---

## 참고 문서

- SNS 액션/리소스/조건키: https://docs.aws.amazon.com/service-authorization/latest/reference/list_amazonsns.html
- SNS Topic Policy 사용 사례: https://docs.aws.amazon.com/sns/latest/dg/sns-access-policy-use-cases.html
- SNS SSE: https://docs.aws.amazon.com/sns/latest/dg/sns-server-side-encryption.html
- KMS 키 정책: https://docs.aws.amazon.com/kms/latest/developerguide/key-policies.html
- AWS Organizations 조건 키: https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_policies_scps_examples.html
- Confused Deputy 방지: https://docs.aws.amazon.com/IAM/latest/UserGuide/confused-deputy.html
