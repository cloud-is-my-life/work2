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
| [case01-publish-only.json](./policies/case01-publish-only.json) | 특정 토픽에 Publish만 허용 |
| [case02-subscribe-https-only.json](./policies/case02-subscribe-https-only.json) | HTTPS 프로토콜 구독만 허용 |
| [case03-deny-delete-topic.json](./policies/case03-deny-delete-topic.json) | 토픽 삭제·속성 변경 차단 |
| [case04-topic-policy-sqs.json](./policies/case04-topic-policy-sqs.json) | Topic Policy — SQS 구독 + 크로스 계정 Publish |
| [case05-topic-policy-s3-event.json](./policies/case05-topic-policy-s3-event.json) | Topic Policy — S3 이벤트 알림 수신 |
| [case06-abac-tag-based.json](./policies/case06-abac-tag-based.json) | 태그 기반 ABAC |

---

## 5-1. 케이스별 상세 설명

### Case 01 — 특정 토픽에 Publish만 허용

**시나리오**: 애플리케이션이 특정 토픽에 메시지를 발행만 가능. 구독, 토픽 관리 불가.

**핵심 메커니즘**:
- Allow: `sns:Publish` → 특정 토픽 ARN
- Allow: `sns:ListTopics`, `sns:GetTopicAttributes` → Resource `*` (리소스 수준 제어 불가)

**허용**: 지정 토픽에 `Publish`
**거부**: `Subscribe`, `DeleteTopic`, 다른 토픽에 Publish

**주의사항**:
- `sns:ListTopics`는 `Resource: "*"` 필수 — 토픽 ARN 지정하면 동작 안 함
- `Publish`는 토픽 ARN 또는 전화번호/엔드포인트 ARN 대상 가능 — 토픽 ARN만 허용하려면 Resource 범위 한정
- FIFO 토픽에 Publish 시 `MessageGroupId` 필수 — IAM과 무관하지만 실패 원인으로 혼동 가능

---

### Case 02 — HTTPS 프로토콜 구독만 허용

**시나리오**: `Subscribe` 허용하되 HTTPS 프로토콜만 가능. email, HTTP, SMS 등 비보안 프로토콜 차단.

**핵심 메커니즘**:
- Allow: `sns:Subscribe` + `sns:Protocol: "https"` → 특정 토픽 ARN
- Deny: `sns:Subscribe` + `sns:Protocol` ≠ `"https"` → 비HTTPS 프로토콜 차단
- Allow: `sns:Unsubscribe` → 구독 해제 허용

**허용**: HTTPS 엔드포인트 구독
**거부**: email, HTTP, SMS, SQS, Lambda 프로토콜 구독 → `AccessDenied`

**주의사항**:
- `sns:Protocol` 조건은 `Subscribe` Action에만 적용 — `Publish`에는 무의미
- SQS, Lambda 프로토콜도 차단됨 → 서비스 연동이 필요하면 해당 프로토콜도 허용 목록에 추가
- `Unsubscribe`는 인증 없이도 동작 가능 — `AuthenticateOnUnsubscribe=true` 설정 권장
- Deny Statement에서 `StringNotEquals`로 HTTPS 외 전부 차단하는 것이 Allow 조건보다 확실

---

### Case 03 — 토픽 삭제·속성 변경 차단

**시나리오**: 토픽 사용(Publish/Subscribe)은 허용하되, 토픽 삭제와 속성 변경은 Explicit Deny로 차단.

**핵심 메커니즘**:
- Deny: `sns:DeleteTopic`, `sns:RemovePermission` → Resource `*`
- Allow: 일반 사용 Action (Publish, Subscribe, GetTopicAttributes 등)

**허용**: 메시지 발행, 구독, 토픽 조회
**거부**: 토픽 삭제, 권한 제거 → `AccessDenied`

**주의사항**:
- `sns:SetTopicAttributes`도 Deny 고려 — 토픽 정책, 전송 정책, 암호화 설정 변경 방지
- `sns:RemovePermission`은 토픽 정책에서 Statement 제거 — 크로스 계정 접근 차단에 악용 가능
- Explicit Deny는 관리자 Allow보다 우선 — 의도적으로 강력한 보호

---

### Case 04 — Topic Policy: SQS 구독 + 크로스 계정 Publish

**시나리오**: SQS 큐가 토픽을 구독할 수 있도록 허용 + 외부 계정이 Organization 내부에서만 Publish 가능하도록 Topic Policy 설정.

**핵심 메커니즘**:
- Statement 1: `Principal: {"Service": "sqs.amazonaws.com"}` + `sns:Subscribe` + `aws:SourceArn` 조건
- Statement 2: `Principal: {"AWS": "EXTERNAL_ACCOUNT"}` + `sns:Publish` + `aws:PrincipalOrgID` 조건

**허용**: 지정 SQS 큐의 구독, Organization 내부 계정의 Publish
**거부**: 비허용 SQS 큐, Organization 외부 계정

**주의사항**:
- Topic Policy는 Resource-based 정책 — `Principal` 필수
- 같은 계정 내 SNS → SQS 연동은 Topic Policy 또는 Queue Policy 중 하나만 있으면 됨
- 크로스 계정은 Topic Policy + 상대 계정 IAM Policy 양쪽 모두 필요 (교집합)
- `aws:SourceArn` 조건으로 특정 SQS 큐만 구독 허용 — 없으면 모든 SQS 큐가 구독 가능

---

### Case 05 — Topic Policy: S3 이벤트 알림 수신

**시나리오**: S3 버킷의 이벤트 알림(ObjectCreated 등)이 SNS 토픽으로 전송되도록 Topic Policy 설정.

**핵심 메커니즘**:
- Topic Policy: `Principal: {"Service": "s3.amazonaws.com"}`
- Allow: `sns:Publish`
- Condition: `aws:SourceArn` → 특정 S3 버킷 ARN, `aws:SourceAccount` → 버킷 소유 계정

**허용**: 지정 S3 버킷의 이벤트 알림 수신
**거부**: 다른 버킷, 다른 서비스에서의 Publish

**주의사항**:
- `aws:SourceAccount` 조건 추가 권장 — confused deputy 방지
- S3 버킷 알림 설정은 버킷 소유자가 수행 — Topic Policy가 먼저 설정되어 있어야 함
- 암호화 토픽(SSE-KMS) 사용 시 KMS Key Policy에 `s3.amazonaws.com`의 `kms:GenerateDataKey*`, `kms:Decrypt` 허용 필요
- `AddPermission` API는 Condition 블록 미지원 → `SetTopicAttributes`로 직접 정책 JSON 작성

---

### Case 06 — 태그 기반 ABAC

**시나리오**: 토픽의 `Team` 태그와 IAM 사용자의 `PrincipalTag/Team`이 일치할 때만 Publish 허용.

**핵심 메커니즘**:
- `aws:ResourceTag/Team` + `StringEquals` + `${aws:PrincipalTag/Team}` 동적 매칭
- Deny: `aws:PrincipalTag/Team` `Null: "true"` → 태그 없는 사용자 전면 차단
- Deny: `sns:CreateTopic` + `aws:RequestTag/Team` `Null: "true"` → 생성 시 태그 강제

**허용**: `PrincipalTag/Team = orders` → `ResourceTag/Team = orders` 토픽만
**거부**: 태그 불일치, 태그 미설정, 태그 없이 토픽 생성

**주의사항**:
- `sns:ListTopics`는 태그 조건 적용 불가 → `Resource: "*"` 별도 Statement 필요
- `sns:TagResource`/`sns:UntagResource` 권한도 제어해야 태그 변경으로 우회 방지
- 토픽 생성 시 태그 강제와 기존 토픽 접근 제어는 별도 Statement로 구현

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
