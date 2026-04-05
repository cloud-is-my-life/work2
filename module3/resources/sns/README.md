# SNS Fine-grained IAM Policy Reference

> CloudShell 복붙 가능 + Console 재현 가능 + Allow/AccessDenied 검증 포함

---

## 공통 변수

```bash
export AWS_REGION="ap-northeast-2"
export ACCOUNT_ID="123456789012"
export TOPIC_NAME="my-topic"
export TOPIC_ARN="arn:aws:sns:${AWS_REGION}:${ACCOUNT_ID}:${TOPIC_NAME}"
export KMS_KEY_ARN="arn:aws:kms:${AWS_REGION}:${ACCOUNT_ID}:key/KEY_ID"
export PUBLISHER_USER="sns-publisher"
export SUBSCRIBER_USER="sns-subscriber"
export PROFILE_PUB="sns-publisher"
export PROFILE_SUB="sns-subscriber"
```

---

## 1. SNS 전용 Condition Key 표

| Condition Key | 타입 | 적용 Action | 설명 |
|---|---|---|---|
| `sns:Endpoint` | String | `Subscribe` | 구독 엔드포인트 (URL, 이메일, ARN). 와일드카드(`*`) 사용 가능 |
| `sns:Protocol` | String | `Subscribe` | 구독 프로토콜: `http`, `https`, `email`, `email-json`, `sms`, `sqs`, `application`, `lambda`, `firehose` |

> ⚠️ `sns:Endpoint`와 `sns:Protocol`은 **`Subscribe` 액션에만** 적용된다. `Publish`에는 효과 없음.

---

## 2. 자주 쓰는 Global Condition Key (SNS 맥락)

| Condition Key | 타입 | 설명 |
|---|---|---|
| `aws:SecureTransport` | Bool | `false`이면 HTTP 요청 → Deny로 TLS 강제 |
| `aws:SourceArn` | ARN | 서비스(S3, CloudWatch 등)가 Publish할 때 소스 ARN 제한 |
| `aws:SourceAccount` | String | 서비스 Publish 시 소스 계정 ID 제한 (confused deputy 방지) |
| `aws:SourceOwner` | String | **Deprecated** — `aws:SourceAccount` 사용 권장 |
| `aws:PrincipalOrgID` | String | AWS Organizations 조직 ID로 Publish 허용 범위 제한 |
| `aws:ResourceTag/${TagKey}` | String | 토픽 태그 기반 접근 제어 (ABAC) |
| `aws:RequestTag/${TagKey}` | String | `CreateTopic`/`TagResource` 시 요청 태그 강제 |
| `aws:TagKeys` | ArrayOfString | 허용/금지 태그 키 목록 |
| `aws:sourceVpce` | String | 특정 VPC 엔드포인트에서만 Publish 허용 |
| `aws:SourceIp` | IP | 소스 IP/CIDR 기반 제한 |
| `aws:PrincipalTag/${TagKey}` | String | 호출자(Principal) 태그 기반 ABAC |

---

## 3. ARN 패턴

```
# 토픽 (유일한 SNS 리소스 타입)
arn:aws:sns:{region}:{account-id}:{topic-name}

# 예시
arn:aws:sns:ap-northeast-2:123456789012:my-topic

# 와일드카드 — 특정 prefix 토픽 전체
arn:aws:sns:ap-northeast-2:123456789012:prod-*

# 모든 리전의 동일 토픽명
arn:aws:sns:*:123456789012:my-topic
```

> ⚠️ SNS에는 **구독(Subscription) ARN을 Resource로 지정하는 IAM 액션이 없다**.  
> `Unsubscribe`, `GetSubscriptionAttributes`, `SetSubscriptionAttributes`는 Resource `*` 또는 토픽 ARN으로 제어.

---

## 4. 핵심 액션 분류

| 역할 | 액션 | Resource |
|---|---|---|
| Publisher | `sns:Publish` | 토픽 ARN |
| Subscriber | `sns:Subscribe` | 토픽 ARN |
| 구독 확인 | `sns:ConfirmSubscription` | 토픽 ARN |
| 구독 해제 | `sns:Unsubscribe` | `*` (인증 불필요 — IAM으로 제어 불가) |
| 토픽 관리 | `sns:CreateTopic`, `sns:DeleteTopic`, `sns:SetTopicAttributes` | 토픽 ARN / `*` |
| 조회 | `sns:GetTopicAttributes`, `sns:ListTopics`, `sns:ListSubscriptionsByTopic` | 토픽 ARN / `*` |
| 태그 | `sns:TagResource`, `sns:UntagResource`, `sns:ListTagsForResource` | 토픽 ARN |
| 암호화 | `sns:GetDataProtectionPolicy`, `sns:PutDataProtectionPolicy` | 토픽 ARN |

---

## 5. 정책 파일 목록

| 파일 | 시나리오 |
|---|---|
| [p01-topic-publish-subscribe-split.json](./policies/p01-topic-publish-subscribe-split.json) | Publisher/Subscriber 역할 분리 |
| [p02-subscribe-https-only.json](./policies/p02-subscribe-https-only.json) | HTTPS 프로토콜 구독만 허용 |
| [p03-enforce-encryption-kms.json](./policies/p03-enforce-encryption-kms.json) | KMS 암호화 토픽 Publish + TLS 강제 |
| [p04-cross-account-publish.json](./policies/p04-cross-account-publish.json) | 크로스 계정 Publish (confused deputy 방지) |
| [p05-abac-tag-based.json](./policies/p05-abac-tag-based.json) | 태그 기반 ABAC (ResourceTag/environment) |
| [p06-source-ip-restriction.json](./policies/p06-source-ip-restriction.json) | 소스 IP/CIDR 제한 |
| [p07-vpc-endpoint-only.json](./policies/p07-vpc-endpoint-only.json) | VPC 엔드포인트 전용 Publish |

---

## 6. 주요 함정 (Gotchas)

### ① `sns:Endpoint` / `sns:Protocol`은 Subscribe 전용
```
Publish 액션에 sns:Protocol 조건을 걸어도 아무 효과 없음.
전송 프로토콜(HTTPS) 강제는 aws:SecureTransport 로 해야 함.
```

### ② `Unsubscribe`는 IAM으로 막기 어렵다
```
ConfirmSubscription/Unsubscribe는 인증 없이도 동작하도록 설계됨.
AuthenticateOnUnsubscribe=true 로 구독 확인 시 설정해야 함.
```

### ③ 이메일 엔드포인트 정규화
```
sns:Endpoint 조건에서 이메일은 소문자로 정규화됨.
정책에 대문자 이메일 써도 매칭되지만, 정책 자체는 소문자로 작성 권장.
```

### ④ HTTP/HTTPS 엔드포인트 정규화
```
scheme + hostname만 소문자 변환, path/query/fragment는 원본 유지.
"https://EXAMPLE.COM/path?A=B" → scheme+host만 소문자로 비교.
```

### ⑤ SSE 토픽은 HTTPS 필수
```
KMS 암호화 토픽에 HTTP로 Publish하면 거부됨.
aws:SecureTransport Deny 정책 없어도 SSE 토픽은 자동으로 HTTPS 요구.
```

### ⑥ `aws:SourceOwner` Deprecated
```
새 서비스 통합은 aws:SourceArn + aws:SourceAccount 사용.
aws:SourceOwner는 기존 SES 등 일부 서비스에서만 유지.
```

### ⑦ 토픽 정책(Resource-based) vs IAM 정책 평가
```
같은 계정: IAM 정책 OR 토픽 정책 중 하나만 Allow면 허용.
크로스 계정: IAM 정책 AND 토픽 정책 둘 다 Allow여야 허용.
Explicit Deny는 어디서든 최우선.
```

### ⑧ `AddPermission` API 한계
```
AddPermission은 Condition 블록을 지원하지 않음.
프로토콜 제한, IP 제한 등 조건이 필요하면 SetTopicAttributes로 직접 정책 JSON 작성.
```

### ⑨ `ListTopics` / `ListSubscriptions`는 Resource `*` 필요
```
이 두 액션은 특정 토픽 ARN을 Resource로 지정할 수 없음.
반드시 "Resource": "*" 로 허용해야 함.
```

### ⑩ KMS + SNS 조합 시 서비스 주체 KMS 권한 필요
```
S3/CloudWatch 등 AWS 서비스가 암호화 토픽에 Publish하려면
해당 서비스 주체(s3.amazonaws.com 등)에게
kms:GenerateDataKey* + kms:Decrypt 권한이 KMS 키 정책에 있어야 함.
```

---

## 7. 검증 루틴 (CloudShell)

```bash
# 토픽 생성
aws sns create-topic --name "$TOPIC_NAME" --region "$AWS_REGION"

# Publish 테스트 (성공 기대)
aws sns publish \
  --topic-arn "$TOPIC_ARN" \
  --message "test" \
  --profile "$PROFILE_PUB"

# Subscribe 테스트 (성공 기대 — HTTPS 엔드포인트)
aws sns subscribe \
  --topic-arn "$TOPIC_ARN" \
  --protocol https \
  --notification-endpoint "https://example.com/endpoint" \
  --profile "$PROFILE_SUB"

# Subscribe 테스트 (실패 기대 — HTTP 엔드포인트, p02 정책 적용 시)
aws sns subscribe \
  --topic-arn "$TOPIC_ARN" \
  --protocol http \
  --notification-endpoint "http://example.com/endpoint" \
  --profile "$PROFILE_SUB"

# 시뮬레이터
aws iam simulate-principal-policy \
  --policy-source-arn "arn:aws:iam::${ACCOUNT_ID}:user/${PUBLISHER_USER}" \
  --action-names sns:Publish sns:Subscribe \
  --resource-arns "$TOPIC_ARN"
```

---

## 8. 공식 문서

- SNS 액션/리소스/조건키: https://docs.aws.amazon.com/service-authorization/latest/reference/list_amazonsns.html
- SNS IAM 정책 예시: https://docs.aws.amazon.com/sns/latest/dg/sns-using-identity-based-policies.html
- SNS 액세스 제어 사용 사례: https://docs.aws.amazon.com/sns/latest/dg/sns-access-policy-use-cases.html
- SNS 보안 모범 사례: https://docs.aws.amazon.com/sns/latest/dg/sns-security-best-practices.html
- SNS SSE: https://docs.aws.amazon.com/sns/latest/dg/sns-server-side-encryption.html
- SNS 태그 기반 접근 제어: https://docs.aws.amazon.com/sns/latest/dg/sns-tags.html
- SNS VPC 엔드포인트 정책: https://docs.aws.amazon.com/sns/latest/dg/sns-vpc-endpoint-policy.html
