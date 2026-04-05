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
