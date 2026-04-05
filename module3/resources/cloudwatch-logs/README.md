# CloudWatch Logs Fine-grained IAM 실전 케이스

## 핵심 요약

> **⚠️ Log Group ARN에 `:*` suffix 필요** — `arn:aws:logs:REGION:ACCOUNT:log-group:NAME:*` 형태로 써야 log stream까지 포함.

> **⚠️ `CreateLogGroup` vs `CreateLogStream` vs `PutLogEvents` 분리** — Lambda 실행 역할에는 3개 모두 필요.

> **⚠️ `DescribeLogGroups`는 리소스 수준 제어 불가** — `"Resource": "*"` 필수.

> **⚠️ Resource Policy(리소스 기반 정책)로 크로스 계정/서비스 로그 수신** — CloudTrail, Route53, VPC Flow Logs 등.

---

## ARN 패턴 (가장 빈출 함정)

```
# Log Group (log stream 포함 — 대부분의 Action에 사용)
arn:aws:logs:REGION:ACCOUNT_ID:log-group:LOG_GROUP_NAME:*

# Log Group만 (CreateLogGroup, DeleteLogGroup 등)
arn:aws:logs:REGION:ACCOUNT_ID:log-group:LOG_GROUP_NAME

# 와일드카드 (prefix 기반)
arn:aws:logs:REGION:ACCOUNT_ID:log-group:/app/prod/*:*

# 전체
arn:aws:logs:REGION:ACCOUNT_ID:*
```

> **`:*` suffix 규칙**: `PutLogEvents`, `GetLogEvents`, `FilterLogEvents`, `CreateLogStream` 등 log stream 수준 Action은 `:*` suffix가 있는 ARN 필요. 없으면 AccessDenied.

---

## 정책 파일

| 케이스 | 파일 | 의도 |
|---|---|---|
| Case 01 | `policies/case01-lambda-execution-role.json` | Lambda 실행 역할 최소 권한 |
| Case 02 | `policies/case02-readonly-specific-group.json` | 특정 Log Group 읽기 전용 |
| Case 03 | `policies/case03-deny-delete-retention.json` | 삭제 + 보존기간 변경 차단 |
| Case 04 | `policies/case04-prefix-based-write.json` | Prefix 기반 쓰기 허용 |
| Case 05 | `policies/case05-resource-policy-cross-service.json` | Resource Policy — 서비스 로그 수신 |

---

## 케이스별 상세 설명

### Case 01 — Lambda 실행 역할 최소 권한

**시나리오**: Lambda 함수의 실행 역할에 필요한 CloudWatch Logs 최소 권한. 자기 함수의 Log Group/Stream만 접근.

**핵심 메커니즘**:
- Allow: `logs:CreateLogGroup` → Resource `arn:aws:logs:REGION:ACCOUNT:log-group:/aws/lambda/FUNCTION_NAME`
- Allow: `logs:CreateLogStream`, `logs:PutLogEvents` → Resource `arn:aws:logs:REGION:ACCOUNT:log-group:/aws/lambda/FUNCTION_NAME:*`

**허용**: 자기 함수의 Log Group 생성, Log Stream 생성, 로그 이벤트 기록
**거부**: 다른 함수의 Log Group 접근, 로그 읽기, 삭제

**주의사항**:
- `CreateLogGroup`은 `:*` suffix **없는** ARN 사용, `CreateLogStream`/`PutLogEvents`는 `:*` suffix **있는** ARN 사용 — 혼동 시 `AccessDenied`
- `CreateLogGroup` 빠뜨리면 첫 실행 시 Log Group 자동 생성 실패 → 로그 유실
- Lambda 함수명이 변경되면 ARN도 변경 → 와일드카드 `/aws/lambda/*` 사용 시 모든 Lambda 로그 접근 가능해짐

---

### Case 02 — 특정 Log Group 읽기 전용

**시나리오**: 운영팀이 특정 Log Group의 로그만 조회 가능. 쓰기/삭제/설정 변경 불가.

**핵심 메커니즘**:
- Allow: `logs:GetLogEvents`, `logs:FilterLogEvents`, `logs:DescribeLogStreams` → Resource `arn:aws:logs:REGION:ACCOUNT:log-group:LOG_GROUP:*`
- Allow: `logs:DescribeLogGroups` → Resource `*` (리소스 수준 제어 불가)

**허용**: 지정 Log Group의 로그 이벤트 조회, 필터링, 스트림 목록 확인
**거부**: 로그 쓰기, 삭제, 다른 Log Group 접근

**주의사항**:
- `DescribeLogGroups`는 `Resource: "*"` 필수 — 특정 ARN 지정하면 오류
- `FilterLogEvents`는 `:*` suffix ARN 필요 — suffix 없으면 `AccessDenied`
- `GetLogRecord`, `GetQueryResults` 등 Insights 관련 Action도 읽기에 포함할지 결정 필요
- `StartQuery`/`StopQuery`는 Insights 쿼리용 — 읽기 전용에 포함 여부는 요구사항에 따라

---

### Case 03 — 삭제 + 보존기간 변경 차단

**시나리오**: Log Group/Stream 삭제와 보존기간(`RetentionPolicy`) 변경을 Explicit Deny로 차단. 로그 데이터 보호.

**핵심 메커니즘**:
- Deny: `logs:DeleteLogGroup`, `logs:DeleteLogStream` → Resource `*`
- Deny: `logs:PutRetentionPolicy`, `logs:DeleteRetentionPolicy` → Resource `*`

**허용**: 로그 읽기, 쓰기 (기존 Log Group에)
**거부**: Log Group/Stream 삭제, 보존기간 변경/삭제 → `AccessDenied`

**주의사항**:
- `DeleteLogGroup`과 `DeleteLogStream` **둘 다** Deny해야 완전 차단 — Stream만 삭제하면 데이터 유실
- `PutRetentionPolicy`와 `DeleteRetentionPolicy` 둘 다 차단 — 보존기간을 1일로 줄이거나 무제한으로 변경하는 것 모두 방지
- Explicit Deny는 관리자 정책의 Allow보다 우선 — 의도적으로 강력한 보호

---

### Case 04 — Prefix 기반 쓰기 허용

**시나리오**: 특정 prefix(`/app/prod/`)로 시작하는 Log Group에만 로그 쓰기 허용. 다른 prefix는 차단.

**핵심 메커니즘**:
- Allow: `logs:CreateLogGroup` → Resource `arn:aws:logs:REGION:ACCOUNT:log-group:/app/prod/*`
- Allow: `logs:CreateLogStream`, `logs:PutLogEvents` → Resource `arn:aws:logs:REGION:ACCOUNT:log-group:/app/prod/*:*`

**허용**: `/app/prod/my-service`, `/app/prod/api` 등 Log Group 생성 및 로그 기록
**거부**: `/app/dev/*`, `/aws/lambda/*` 등 다른 prefix Log Group 접근

**주의사항**:
- prefix 와일드카드에서 `*`는 `/` 포함 모든 문자 매칭 → `/app/prod/a/b/c`도 허용됨
- `CreateLogGroup`과 `CreateLogStream`/`PutLogEvents`의 ARN suffix 차이 주의 (`:*` 유무)
- 기존 Log Group이 없으면 `CreateLogGroup` 권한 필요 — 이미 존재하면 `CreateLogStream`부터 시작

---

### Case 05 — Resource Policy: 서비스 로그 수신

**시나리오**: CloudTrail, Route53, VPC Flow Logs 등 AWS 서비스가 CloudWatch Logs에 로그를 전송할 수 있도록 Resource Policy 설정.

**핵심 메커니즘**:
- Resource Policy: `Principal: {"Service": "SERVICE.amazonaws.com"}`
- Allow: `logs:CreateLogStream`, `logs:PutLogEvents` → 특정 Log Group ARN
- Condition: `aws:SourceArn`, `aws:SourceAccount`로 혼동 대리인 방지

**허용**: 지정 서비스가 지정 Log Group에 로그 전송
**거부**: 비허용 서비스, 비허용 Log Group

**주의사항**:
- Resource Policy는 `aws logs put-resource-policy` CLI로 설정 — IAM Policy와 별개
- Resource Policy 크기 제한 **5120자** — 너무 많은 서비스/Log Group 추가 시 초과 가능
- 서비스별 Principal 값이 다름: `delivery.logs.amazonaws.com` (VPC Flow Logs), `cloudtrail.amazonaws.com` (CloudTrail) 등
- `aws:SourceArn` 조건으로 특정 리소스(특정 VPC, 특정 Trail)만 허용 가능

---

## CloudShell 준비

```bash
export AWS_REGION="ap-northeast-2"
export ACCOUNT_ID="123456789012"
export LOG_GROUP="/app/prod/my-service"
export USER_NAME="mod3-cwl-user"
export PROFILE_NAME="mod3-cwl-user"
```

---

## 검증 예시

```bash
# 로그 이벤트 조회 — 성공 기대
aws logs filter-log-events \
  --log-group-name "$LOG_GROUP" \
  --limit 5 \
  --profile "$PROFILE_NAME"

# 다른 Log Group — AccessDenied 기대
aws logs filter-log-events \
  --log-group-name "/app/dev/other-service" \
  --limit 5 \
  --profile "$PROFILE_NAME"

# 삭제 시도 — AccessDenied 기대
aws logs delete-log-group \
  --log-group-name "$LOG_GROUP" \
  --profile "$PROFILE_NAME"

# 보존기간 변경 — AccessDenied 기대
aws logs put-retention-policy \
  --log-group-name "$LOG_GROUP" \
  --retention-in-days 1 \
  --profile "$PROFILE_NAME"
```

---

## 감점 방지 포인트

- ARN에 `:*` 빠뜨리면 `PutLogEvents`, `FilterLogEvents` 등 전부 실패
- `DescribeLogGroups`를 특정 ARN에 넣으면 오류 — 반드시 `"*"`
- Lambda 역할에 `CreateLogGroup` 빠뜨리면 첫 실행 시 로그 그룹 생성 실패
- `DeleteLogGroup`과 `DeleteLogStream` 둘 다 Deny해야 완전 차단
- Resource Policy 크기 제한 5120자 — 너무 많은 서비스 추가 시 초과 가능
