# CloudWatch Logs Fine-grained IAM 실전 가이드

> AWS Skills Competition 2026 대비. 실수가 가장 많이 나오는 순서대로 정리했다.

---

## 목차

1. [ARN `:*` suffix 완전 정복](#arn--suffix-완전-정복)
2. [기존 케이스 5개 요약](#기존-케이스-5개-요약)
3. [신규 케이스 5개 상세](#신규-케이스-5개-상세)
4. [Lambda / ECS / EC2 실행 역할별 최소 권한 비교표](#lambda--ecs--ec2-실행-역할별-최소-권한-비교표)
5. [Resource Policy 작성법](#resource-policy-작성법)
6. [검증 명령어 모음](#검증-명령어-모음)

---

## ARN `:*` suffix 완전 정복

경기에서 가장 많이 틀리는 부분이다. `AccessDenied`가 나왔는데 정책은 맞아 보인다면, 십중팔구 여기서 막힌 거다.

### ARN 형태 4가지

```
# 1. Log Group 자체 (suffix 없음)
#    CreateLogGroup, DeleteLogGroup, PutRetentionPolicy 등에 사용
arn:aws:logs:REGION:ACCOUNT_ID:log-group:LOG_GROUP_NAME

# 2. Log Group + 하위 스트림 전체 (suffix :*)
#    CreateLogStream, PutLogEvents, GetLogEvents, FilterLogEvents 등에 사용
arn:aws:logs:REGION:ACCOUNT_ID:log-group:LOG_GROUP_NAME:*

# 3. Prefix 와일드카드 + suffix
#    /app/prod/ 하위 모든 Log Group의 스트림까지 포함
arn:aws:logs:REGION:ACCOUNT_ID:log-group:/app/prod/*:*

# 4. 계정 전체
arn:aws:logs:REGION:ACCOUNT_ID:*
```

### 어떤 Action에 어떤 ARN을 써야 하나

| Action | 필요한 ARN 형태 | suffix 유무 |
|---|---|---|
| `CreateLogGroup` | `log-group:NAME` | 없음 |
| `DeleteLogGroup` | `log-group:NAME` | 없음 |
| `PutRetentionPolicy` | `log-group:NAME` | 없음 |
| `PutMetricFilter` | `log-group:NAME` | 없음 |
| `DescribeMetricFilters` | `log-group:NAME` | 없음 |
| `CreateLogStream` | `log-group:NAME:*` | **있음** |
| `PutLogEvents` | `log-group:NAME:*` | **있음** |
| `GetLogEvents` | `log-group:NAME:*` | **있음** |
| `FilterLogEvents` | `log-group:NAME:*` | **있음** |
| `DescribeLogStreams` | `log-group:NAME:*` | **있음** |
| `StartQuery` | `log-group:NAME:*` | **있음** |
| `GetQueryResults` | `log-group:NAME:*` | **있음** |
| `DescribeLogGroups` | `*` (리소스 수준 제어 불가) | N/A |
| `DescribeQueries` | `*` (리소스 수준 제어 불가) | N/A |

### 핵심 규칙 요약

Log Stream 수준에서 동작하는 Action은 `:*` suffix가 필요하다. Log Group 자체를 대상으로 하는 Action(생성, 삭제, 설정 변경)은 suffix 없이 쓴다. `DescribeLogGroups`처럼 리소스 수준 제어가 아예 안 되는 Action은 `"Resource": "*"`로만 허용할 수 있다.

suffix 빠뜨리면 `PutLogEvents`가 `AccessDenied`로 떨어진다. 정책 JSON을 아무리 봐도 이상 없어 보이는데 실패한다면 ARN 끝을 먼저 확인하자.

---

## 기존 케이스 5개 요약

| 케이스 | 파일 | 핵심 포인트 |
|---|---|---|
| Case 01 | `case01-lambda-execution-role.json` | `CreateLogGroup`은 suffix 없음, `CreateLogStream`/`PutLogEvents`는 `:*` suffix 필요 |
| Case 02 | `case02-readonly-specific-group.json` | `FilterLogEvents`에 `:*` suffix 필수, `DescribeLogGroups`는 `"*"` |
| Case 03 | `case03-deny-delete-retention.json` | `DeleteLogGroup`과 `DeleteLogStream` 둘 다 Deny, `PutRetentionPolicy`도 함께 차단 |
| Case 04 | `case04-prefix-based-write.json` | prefix 와일드카드 `/app/prod/*`와 `/app/prod/*:*` 두 ARN 모두 필요 |
| Case 05 | `case05-resource-policy-cross-service.json` | Resource Policy는 IAM Policy와 별개, `aws logs put-resource-policy`로 적용 |

---

## 신규 케이스 5개 상세

### Case 06 — ECS Task 실행 역할 로그 권한 (awslogs 드라이버용)

**파일**: `policies/case06-ecs-task-execution-role.json`

ECS에서 `awslogs` 드라이버를 쓰면 컨테이너 로그가 CloudWatch Logs로 전송된다. 이때 Task Execution Role에 로그 권한이 없으면 컨테이너 자체가 시작되지 않는다.

**필요한 Action**:
- `logs:CreateLogGroup`: Log Group이 없을 때 자동 생성
- `logs:CreateLogStream`: 컨테이너 시작 시 Log Stream 생성
- `logs:PutLogEvents`: 실제 로그 전송
- `logs:DescribeLogStreams`: 스트림 상태 확인 (awslogs 드라이버 내부 사용)
- `logs:DescribeLogGroups`: `"Resource": "*"` 필수

**Lambda와의 차이점**:

Lambda는 `/aws/lambda/FUNCTION_NAME` 경로를 쓰지만, ECS는 보통 `/ecs/TASK_DEFINITION_NAME` 경로를 쓴다. Task Definition의 `logConfiguration` 섹션에서 `awslogs-group` 값으로 지정한 경로와 ARN이 일치해야 한다.

```json
// Task Definition logConfiguration 예시
"logConfiguration": {
  "logDriver": "awslogs",
  "options": {
    "awslogs-group": "/ecs/my-task",
    "awslogs-region": "ap-northeast-2",
    "awslogs-stream-prefix": "ecs"
  }
}
```

**주의사항**:
- Task Role과 Task Execution Role을 혼동하지 말 것. 로그 권한은 Task Execution Role에 붙인다.
- `DescribeLogStreams`에 `:*` suffix ARN을 써야 한다. suffix 없으면 `AccessDenied`.

---

### Case 07 — CloudWatch Insights 쿼리 전용

**파일**: `policies/case07-insights-query-only.json`

로그 분석 담당자에게 Insights 쿼리만 허용하고, 로그 쓰기나 설정 변경은 막는 케이스다.

**필요한 Action**:
- `logs:StartQuery`: 쿼리 시작
- `logs:StopQuery`: 실행 중인 쿼리 중단
- `logs:GetQueryResults`: 쿼리 결과 조회
- `logs:DescribeQueries`: 쿼리 목록 확인

**`GetLogEvents`와의 차이**:

`GetLogEvents`는 Log Stream을 직접 읽는 방식이고, `StartQuery`/`GetQueryResults`는 Insights 엔진을 통해 쿼리하는 방식이다. 둘 다 읽기지만 Action이 다르다. Insights 전용 권한을 주면서 `GetLogEvents`를 빠뜨리면 콘솔에서 로그 스트림 직접 조회가 안 된다. 의도적으로 막는 거라면 괜찮다.

**주의사항**:
- `StartQuery`는 `:*` suffix ARN이 필요하다.
- `DescribeQueries`는 리소스 수준 제어가 안 되므로 `"Resource": "*"` 사용.
- 쿼리 결과는 계정 수준에서 저장되므로 `GetQueryResults`에 특정 Log Group ARN을 지정해도 다른 Log Group 쿼리 결과를 못 막는 경우가 있다. 완전한 격리가 필요하면 별도 계정 분리를 고려해야 한다.

---

### Case 08 — 구독 필터 관리 차단

**파일**: `policies/case08-deny-subscription-filter.json`

구독 필터(Subscription Filter)는 로그를 Lambda, Kinesis, Firehose로 실시간 전달하는 기능이다. 무단으로 외부 시스템에 로그를 흘리는 걸 막으려면 이 Action을 Deny해야 한다.

**차단 대상**:
- `logs:PutSubscriptionFilter`: 구독 필터 생성/수정
- `logs:DeleteSubscriptionFilter`: 구독 필터 삭제

**왜 삭제도 막나**:

삭제를 허용하면 기존에 설정된 보안 모니터링용 구독 필터를 지울 수 있다. 공격자가 탐지 파이프라인을 끊는 방법으로 악용할 수 있으므로 생성과 삭제 모두 차단한다.

**주의사항**:
- `DescribeSubscriptionFilters`는 읽기 전용이라 별도로 허용/차단 여부를 결정해야 한다. 이 케이스에서는 차단하지 않았다.
- Explicit Deny이므로 관리자 정책의 Allow보다 우선한다. 운영팀 계정에 이 Deny 정책이 붙어 있으면 관리자도 구독 필터를 못 건드린다.

---

### Case 09 — 태그 기반 Log Group 접근 (ABAC)

**파일**: `policies/case09-tag-based-log-group-access.json`

Log Group에 태그를 붙이고, 사용자의 태그(`PrincipalTag`)와 리소스 태그(`ResourceTag`)가 일치할 때만 접근을 허용하는 ABAC 패턴이다.

**조건 키**:
- `aws:ResourceTag/Environment`: Log Group에 붙은 태그
- `aws:ResourceTag/Team`: Log Group의 팀 태그
- `aws:PrincipalTag/Team`: 사용자/역할에 붙은 팀 태그

**동작 방식**:

`Team` 태그가 `backend`인 사용자는 `Team=backend` 태그가 붙은 Log Group에만 접근할 수 있다. 같은 정책을 모든 팀에 붙이고 태그만 다르게 설정하면 된다.

**주의사항**:
- CloudWatch Logs의 `aws:ResourceTag` 조건은 Log Group 수준에서만 동작한다. Log Stream에는 태그를 붙일 수 없다.
- Log Group에 태그가 없으면 조건이 `false`가 되어 접근이 거부된다. 태그 관리가 선행되어야 한다.
- `DescribeLogGroups`는 `"Resource": "*"`로만 허용 가능하므로, 태그 기반 제어가 적용되지 않는다. 목록 조회는 모든 Log Group이 보인다.
- `aws:ResourceTag` 조건을 쓰려면 Log Group이 이미 존재해야 한다. 없는 Log Group에 대한 `CreateLogGroup`은 태그 조건으로 제어할 수 없다.

---

### Case 10 — Metric Filter 생성만 허용 (삭제 Deny)

**파일**: `policies/case10-metric-filter-create-only.json`

Metric Filter는 로그 패턴을 CloudWatch Metrics로 변환하는 기능이다. 알람의 기반이 되므로 삭제를 막아 모니터링 파이프라인을 보호한다.

**허용 Action**:
- `logs:PutMetricFilter`: Metric Filter 생성/수정
- `logs:DescribeMetricFilters`: 목록 조회

**차단 Action**:
- `logs:DeleteMetricFilter`: Explicit Deny

**`PutMetricFilter`의 ARN 주의사항**:

`PutMetricFilter`는 Log Group 자체를 대상으로 하므로 `:*` suffix 없이 쓴다. suffix를 붙이면 오히려 `AccessDenied`가 날 수 있다.

```
# 올바른 ARN
arn:aws:logs:REGION:ACCOUNT_ID:log-group:LOG_GROUP_NAME

# 잘못된 ARN (suffix 붙이면 안 됨)
arn:aws:logs:REGION:ACCOUNT_ID:log-group:LOG_GROUP_NAME:*
```

**주의사항**:
- Metric Filter를 수정하려면 `PutMetricFilter`를 다시 호출한다. 별도의 Update Action이 없다.
- `DeleteMetricFilter`를 Deny하면 잘못 만든 Metric Filter도 못 지운다. 운영 환경에서는 신중하게 적용해야 한다.

---

## Lambda / ECS / EC2 실행 역할별 최소 권한 비교표

| 항목 | Lambda 실행 역할 | ECS Task Execution Role | EC2 인스턴스 프로파일 (CloudWatch Agent) |
|---|---|---|---|
| Log Group 경로 | `/aws/lambda/FUNCTION_NAME` | `/ecs/TASK_DEFINITION_NAME` | 직접 지정 (예: `/ec2/my-app`) |
| `CreateLogGroup` | 필요 (suffix 없음) | 필요 (suffix 없음) | 필요 (suffix 없음) |
| `CreateLogStream` | 필요 (`:*` suffix) | 필요 (`:*` suffix) | 필요 (`:*` suffix) |
| `PutLogEvents` | 필요 (`:*` suffix) | 필요 (`:*` suffix) | 필요 (`:*` suffix) |
| `DescribeLogStreams` | 불필요 | 필요 (`:*` suffix) | 필요 (`:*` suffix) |
| `DescribeLogGroups` | 불필요 | 필요 (`"*"`) | 필요 (`"*"`) |
| `PutRetentionPolicy` | 불필요 | 불필요 | 선택 (Agent가 보존기간 설정 시) |
| 자동 생성 여부 | Lambda가 자동 생성 시도 | ECS가 자동 생성 시도 | CloudWatch Agent가 생성 |
| 권한 없을 때 증상 | 로그 유실, 함수는 실행됨 | 컨테이너 시작 실패 | Agent 오류, 로그 전송 안 됨 |

**Lambda와 ECS의 가장 큰 차이**: ECS는 `DescribeLogStreams`와 `DescribeLogGroups`가 추가로 필요하다. awslogs 드라이버가 내부적으로 스트림 상태를 확인하기 때문이다. Lambda는 런타임이 직접 처리하므로 이 두 Action이 없어도 동작한다.

**EC2 CloudWatch Agent**: Agent 설정 파일(`/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json`)에서 Log Group 이름을 지정한다. Agent가 Log Group을 자동 생성하도록 하려면 `CreateLogGroup`이 필요하고, 보존기간도 Agent가 설정하게 하려면 `PutRetentionPolicy`도 추가해야 한다.

---

## Resource Policy 작성법

IAM Policy(Identity-based)와 Resource Policy는 완전히 다른 개념이다. CloudWatch Logs에서 Resource Policy는 AWS 서비스(CloudTrail, Route53, VPC Flow Logs 등)가 로그를 전송할 때 사용한다.

### IAM Policy vs Resource Policy 비교

| 항목 | IAM Policy | Resource Policy |
|---|---|---|
| 적용 대상 | IAM User, Role, Group | CloudWatch Logs Log Group |
| 주체(Principal) | 명시 안 함 (정책이 붙은 주체) | 명시 필요 (`Service`, `AWS`) |
| 적용 명령어 | `aws iam put-user-policy` 등 | `aws logs put-resource-policy` |
| 크기 제한 | 6144자 (인라인), 6144자 (관리형) | **5120자** |
| 크로스 계정 | STS Assume Role 필요 | Principal에 다른 계정 ARN 직접 지정 가능 |

### Resource Policy 기본 구조

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "식별자",
      "Effect": "Allow",
      "Principal": {
        "Service": "서비스.amazonaws.com"
      },
      "Action": [
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:REGION:ACCOUNT_ID:log-group:LOG_GROUP_NAME:*",
      "Condition": {
        "StringEquals": {
          "aws:SourceAccount": "ACCOUNT_ID"
        }
      }
    }
  ]
}
```

### 서비스별 Principal 값

| 서비스 | Principal |
|---|---|
| CloudTrail | `cloudtrail.amazonaws.com` |
| VPC Flow Logs | `vpc-flow-logs.amazonaws.com` |
| Route 53 Resolver | `route53.amazonaws.com` |
| API Gateway | `apigateway.amazonaws.com` |
| CodeBuild | `codebuild.amazonaws.com` |

### 적용 명령어

```bash
# Resource Policy 적용
aws logs put-resource-policy \
  --policy-name "MyResourcePolicy" \
  --policy-document file://case05-resource-policy-cross-service.json

# 현재 Resource Policy 목록 확인
aws logs describe-resource-policies

# Resource Policy 삭제
aws logs delete-resource-policy \
  --policy-name "MyResourcePolicy"
```

### 혼동 대리인(Confused Deputy) 방지

`aws:SourceArn`과 `aws:SourceAccount` 조건을 반드시 추가해야 한다. 이 조건 없이 서비스 Principal만 허용하면, 다른 계정의 CloudTrail이 이 Log Group에 로그를 쓸 수 있다.

```json
"Condition": {
  "StringEquals": {
    "aws:SourceAccount": "ACCOUNT_ID"
  },
  "ArnLike": {
    "aws:SourceArn": "arn:aws:cloudtrail:REGION:ACCOUNT_ID:trail/MY_TRAIL"
  }
}
```

### 크기 제한 주의

Resource Policy는 5120자 제한이 있다. 여러 서비스와 여러 Log Group을 하나의 정책에 넣으면 금방 초과한다. 서비스별로 정책을 분리하거나, Log Group ARN에 와일드카드를 활용해 크기를 줄여야 한다.

---

## 검증 명령어 모음

```bash
export AWS_REGION="ap-northeast-2"
export ACCOUNT_ID="123456789012"
export LOG_GROUP="/app/prod/my-service"
export PROFILE_NAME="mod3-cwl-user"

# 로그 이벤트 조회 (Case 02, 07)
aws logs filter-log-events \
  --log-group-name "$LOG_GROUP" \
  --limit 5 \
  --profile "$PROFILE_NAME"

# Insights 쿼리 시작 (Case 07)
QUERY_ID=$(aws logs start-query \
  --log-group-name "$LOG_GROUP" \
  --start-time $(date -d '1 hour ago' +%s) \
  --end-time $(date +%s) \
  --query-string 'fields @timestamp, @message | limit 10' \
  --profile "$PROFILE_NAME" \
  --query 'queryId' \
  --output text)

# 쿼리 결과 조회
aws logs get-query-results \
  --query-id "$QUERY_ID" \
  --profile "$PROFILE_NAME"

# 구독 필터 생성 시도 (Case 08 — AccessDenied 기대)
aws logs put-subscription-filter \
  --log-group-name "$LOG_GROUP" \
  --filter-name "test-filter" \
  --filter-pattern "" \
  --destination-arn "arn:aws:lambda:$AWS_REGION:$ACCOUNT_ID:function:test" \
  --profile "$PROFILE_NAME"

# Metric Filter 생성 (Case 10)
aws logs put-metric-filter \
  --log-group-name "$LOG_GROUP" \
  --filter-name "ErrorCount" \
  --filter-pattern "ERROR" \
  --metric-transformations \
    metricName=ErrorCount,metricNamespace=MyApp,metricValue=1 \
  --profile "$PROFILE_NAME"

# Metric Filter 삭제 시도 (Case 10 — AccessDenied 기대)
aws logs delete-metric-filter \
  --log-group-name "$LOG_GROUP" \
  --filter-name "ErrorCount" \
  --profile "$PROFILE_NAME"

# Resource Policy 확인 (Case 05)
aws logs describe-resource-policies \
  --region "$AWS_REGION"

# IAM 시뮬레이터로 원인 추적
aws iam simulate-principal-policy \
  --policy-source-arn "arn:aws:iam::$ACCOUNT_ID:user/$PROFILE_NAME" \
  --action-names logs:PutLogEvents logs:FilterLogEvents logs:DeleteLogGroup \
  --resource-arns "arn:aws:logs:$AWS_REGION:$ACCOUNT_ID:log-group:$LOG_GROUP:*"
```

---

## 감점 방지 체크리스트

- `PutLogEvents`, `FilterLogEvents`, `CreateLogStream`에 `:*` suffix 확인
- `DescribeLogGroups`는 반드시 `"Resource": "*"`
- Lambda 역할에 `CreateLogGroup` 포함 여부 확인
- ECS Task Execution Role에 `DescribeLogStreams`, `DescribeLogGroups` 포함 여부 확인
- Resource Policy 적용은 `aws logs put-resource-policy` 명령어 사용
- Resource Policy 크기 5120자 초과 여부 확인
- 구독 필터 차단 시 `PutSubscriptionFilter`와 `DeleteSubscriptionFilter` 둘 다 Deny
- 태그 기반 접근 제어 시 Log Group에 태그가 실제로 붙어 있는지 확인
- `PutMetricFilter`는 `:*` suffix 없는 ARN 사용
