# Lambda Fine-grained IAM 실전 케이스

## 핵심 요약

> **⚠️ Qualifier(버전/별칭) ARN 함정**: `function:my-fn` 허용 정책은 `function:my-fn:PROD` 호출을 거부한다. 반대도 마찬가지. ARN 타입을 정확히 맞춰야 한다.

> **⚠️ `lambda:InvokeFunction` vs `lambda:InvokeFunctionUrl`**: Function URL은 두 권한이 모두 필요하다 (2025년 10월 이후 신규 URL 기준). 하나만 있으면 403.

> **⚠️ `lambda:Layer`는 버전 ARN 전체**를 값으로 받는다: `arn:aws:lambda:REGION:ACCOUNT:layer:NAME:VERSION` — 레이어 이름만 쓰면 매칭 안 됨.

> **⚠️ `lambda:VpcIds`는 단일 String**, `lambda:SubnetIds`/`lambda:SecurityGroupIds`는 **ArrayOfString** — 연산자 선택이 달라진다 (`StringEquals` vs `ForAllValues:StringNotEquals`).

> **⚠️ `lambda:SourceFunctionArn`은 Lambda→AWS 서비스 호출 시 사용** — 함수가 다른 AWS API를 호출할 때 출처 함수를 제한하는 용도 (예: Secrets Manager 리소스 정책).

> **⚠️ Resource-based policy는 `AddPermission` API로 작성** — IAM 콘솔에서 직접 편집 불가. `aws lambda add-permission` CLI 사용.

---

## Lambda 전용 Condition Key 전체 목록

| Condition Key | 타입 | 적용 Action | 설명 |
|---|---|---|---|
| `lambda:FunctionArn` | ARN | `CreateEventSourceMapping`, `UpdateEventSourceMapping`, `DeleteEventSourceMapping`, `GetEventSourceMapping`, `CreateFunctionUrlConfig`, `DeleteFunctionUrlConfig`, `GetFunctionUrlConfig`, `UpdateFunctionUrlConfig`, `InvokeFunctionUrl` | 이벤트 소스 매핑/URL이 연결된 함수 ARN 제한 |
| `lambda:Layer` | ArrayOfString | `CreateFunction`, `UpdateFunctionConfiguration` | 함수에 첨부 가능한 레이어 버전 ARN 제한 |
| `lambda:VpcIds` | String | `CreateFunction`, `UpdateFunctionConfiguration` | 함수가 연결될 수 있는 VPC ID 제한 |
| `lambda:SubnetIds` | ArrayOfString | `CreateFunction`, `UpdateFunctionConfiguration` | 허용 서브넷 ID 목록 |
| `lambda:SecurityGroupIds` | ArrayOfString | `CreateFunction`, `UpdateFunctionConfiguration` | 허용 보안 그룹 ID 목록 |
| `lambda:CodeSigningConfigArn` | ARN | `CreateFunction`, `UpdateFunctionConfiguration`, `PutFunctionCodeSigningConfig` | 허용 코드 서명 구성 ARN |
| `lambda:EventSourceToken` | String | `InvokeFunction`, `InvokeFunctionUrl` | 비-AWS 이벤트 소스 토큰 검증 |
| `lambda:FunctionUrlAuthType` | String | `CreateFunctionUrlConfig`, `UpdateFunctionUrlConfig`, `DeleteFunctionUrlConfig`, `GetFunctionUrlConfig`, `ListFunctionUrlConfigs`, `AddPermission`, `RemovePermission`, `InvokeFunctionUrl` | URL 인증 타입 (`AWS_IAM` 또는 `NONE`) |
| `lambda:InvokedViaFunctionUrl` | Bool | `InvokeFunction` | Function URL을 통한 호출만 허용 (직접 Invoke 차단) |
| `lambda:Principal` | String | `AddPermission`, `RemovePermission` | 리소스 기반 정책에 추가 가능한 Principal 서비스/계정 제한 |
| `lambda:SourceFunctionArn` | ARN | (다른 서비스의 리소스 정책에서 사용) | 호출 출처 Lambda 함수 ARN 제한 |

### 글로벌 Condition Key (Lambda에서 자주 쓰는 것)

| Condition Key | 타입 | 설명 |
|---|---|---|
| `aws:ResourceTag/${TagKey}` | String | 리소스 태그 기반 접근 제어 |
| `aws:RequestTag/${TagKey}` | String | 요청 시 태그 강제 |
| `aws:PrincipalTag/${TagKey}` | String | Principal 태그 기반 분기 |
| `aws:TagKeys` | ArrayOfString | 허용 태그 키 제한 |
| `aws:SourceAccount` | String | 리소스 기반 정책에서 혼동 대리인 방지 |
| `aws:SourceArn` | ARN | 리소스 기반 정책에서 특정 리소스로 제한 |

---

## ARN 패턴 레퍼런스

```
# 함수 (비정규화 — 버전/별칭 없음)
arn:aws:lambda:REGION:ACCOUNT_ID:function:FUNCTION_NAME

# 함수 특정 버전
arn:aws:lambda:REGION:ACCOUNT_ID:function:FUNCTION_NAME:VERSION_NUMBER

# 함수 별칭
arn:aws:lambda:REGION:ACCOUNT_ID:function:FUNCTION_NAME:ALIAS_NAME

# 함수 와일드카드 (모든 버전/별칭 포함)
arn:aws:lambda:REGION:ACCOUNT_ID:function:FUNCTION_NAME:*

# 이벤트 소스 매핑
arn:aws:lambda:REGION:ACCOUNT_ID:event-source-mapping:UUID

# 레이어 (버전 없음 — PublishLayerVersion에 사용)
arn:aws:lambda:REGION:ACCOUNT_ID:layer:LAYER_NAME

# 레이어 버전 (GetLayerVersion, AddLayerVersionPermission에 사용)
arn:aws:lambda:REGION:ACCOUNT_ID:layer:LAYER_NAME:VERSION_NUMBER

# 코드 서명 구성
arn:aws:lambda:REGION:ACCOUNT_ID:code-signing-config:CSC_ID
```

### ARN 매칭 동작 요약

| Resource ARN 패턴 | 비정규화 ARN 허용 | 특정 버전/별칭 허용 | 모든 버전/별칭 허용 |
|---|:---:|:---:|:---:|
| `function:my-fn` | ✅ | ❌ | ❌ |
| `function:my-fn:1` | ❌ | ✅ (버전 1만) | ❌ |
| `function:my-fn:PROD` | ❌ | ✅ (PROD만) | ❌ |
| `function:my-fn:*` | ❌ | ✅ | ✅ |
| `function:my-fn*` | ✅ | ✅ | ✅ |

---

## 정책 파일

| 케이스 | 파일 | 의도 |
|---|---|---|
| Case 01 | `policies/case01-invoke-specific-function.json` | 특정 함수만 Invoke 허용 (별칭 포함) |
| Case 02 | `policies/case02-deploy-only.json` | 코드 배포만 허용 (설정 변경·삭제 차단) |
| Case 03 | `policies/case03-deny-delete-function.json` | 함수 삭제 차단 |
| Case 04 | `policies/case04-vpc-restriction.json` | 특정 VPC/서브넷에서만 함수 생성 허용 |
| Case 05 | `policies/case05-passrole-scoped.json` | PassRole을 특정 실행 역할로만 제한 |
| Case 06 | `policies/case06-abac-tag-based.json` | 태그 기반 ABAC |
| Case 07 | `policies/case07-resource-policy-apigw.json` | Resource-based Policy — API Gateway 호출 허용 |

---

## 케이스별 상세 설명

### Case 01 — 특정 함수만 Invoke 허용 (별칭 포함)

**시나리오**: 특정 Lambda 함수만 호출 가능. 별칭(`PROD`)이나 버전 번호로 호출하는 경우도 허용.

**핵심 메커니즘**:
- Allow: `lambda:InvokeFunction` → Resource에 unqualified ARN + qualified ARN(`:*`) 둘 다 지정
- `arn:aws:lambda:REGION:ACCOUNT:function:FUNCTION_NAME` — `$LATEST` 호출
- `arn:aws:lambda:REGION:ACCOUNT:function:FUNCTION_NAME:*` — 별칭/버전 호출

**허용**: `invoke --function-name FUNCTION_NAME`, `invoke --function-name FUNCTION_NAME:PROD`
**거부**: 다른 함수 호출, `ListFunctions` 외 관리 작업

**주의사항**:
- Unqualified ARN(`function:my-fn`)과 Qualified ARN(`function:my-fn:PROD`)은 **별개 리소스** — 하나만 넣으면 다른 쪽 호출이 `AccessDenied`
- 둘 다 허용하려면 Resource 배열에 두 패턴 모두 명시하거나 `function:my-fn*` 패턴 사용
- `lambda:ListFunctions`는 `Resource: "*"` 필수

---

### Case 02 — 코드 배포만 허용 (설정 변경·삭제 차단)

**시나리오**: 개발자가 함수 코드를 업데이트하고 버전/별칭을 관리할 수 있지만, 함수 설정(메모리, 타임아웃, VPC 등) 변경과 삭제는 불가.

**핵심 메커니즘**:
- Allow: `lambda:UpdateFunctionCode`, `lambda:PublishVersion`, `lambda:CreateAlias`, `lambda:UpdateAlias`, `lambda:GetFunction`, `lambda:ListVersionsByFunction`, `lambda:ListAliases`
- Deny: `lambda:UpdateFunctionConfiguration`, `lambda:DeleteFunction`, `lambda:CreateFunction`

**허용**: 코드 업데이트, 버전 발행, 별칭 생성/변경
**거부**: 함수 설정 변경, 함수 삭제, 새 함수 생성

**주의사항**:
- `UpdateFunctionCode`와 `UpdateFunctionConfiguration`은 별도 Action — 코드만 허용하고 설정은 차단 가능
- `PublishVersion`은 코드 배포 후 버전 고정에 필수 — 빠뜨리면 별칭이 `$LATEST`만 가리킴
- `PutFunctionConcurrency`/`DeleteFunctionConcurrency`도 Deny 고려 — 동시성 설정 변경 방지

---

### Case 03 — 함수 삭제 차단

**시나리오**: Lambda 함수 전체 관리는 허용하되, 함수 삭제와 별칭 삭제만 Explicit Deny로 차단.

**핵심 메커니즘**:
- Deny: `lambda:DeleteFunction`, `lambda:DeleteAlias` → Resource `*`
- Allow: 그 외 Lambda 관리 Action 전체

**허용**: 함수 생성, 코드/설정 변경, 호출, 버전/별칭 관리
**거부**: 함수 삭제, 별칭 삭제 → `AccessDenied`

**주의사항**:
- `DeleteFunction`은 특정 버전 삭제에도 사용됨 — 버전 삭제도 차단됨
- `DeleteAlias`를 Deny하지 않으면 별칭 삭제 후 재생성으로 다른 버전 가리키기 가능
- `DeleteLayerVersion`은 별도 Action — Layer 삭제도 차단하려면 추가 Deny 필요

---

### Case 04 — 특정 VPC/서브넷에서만 함수 생성 허용

**시나리오**: Lambda 함수가 반드시 지정 VPC/서브넷/보안그룹에 연결되어야 함. VPC 없는 함수 생성 차단.

**핵심 메커니즘**:
- Allow: `lambda:CreateFunction`, `lambda:UpdateFunctionConfiguration` + `lambda:VpcIds: "VPC_ID"` 조건
- `ForAllValues:StringEquals` → `lambda:SubnetIds`, `lambda:SecurityGroupIds` 허용 목록
- Deny: `lambda:VpcIds` `Null: "true"` → VPC 미지정 함수 생성 차단

**허용**: 지정 VPC/서브넷/보안그룹에 연결된 함수 생성
**거부**: VPC 없는 함수, 다른 VPC/서브넷 사용 → `AccessDenied`

**주의사항**:
- `lambda:VpcIds`는 **단일 String** → `StringEquals` 사용
- `lambda:SubnetIds`/`lambda:SecurityGroupIds`는 **ArrayOfString** → `ForAllValues:StringEquals` 사용 (연산자 선택 다름)
- `Null` 조건으로 VPC 미지정 케이스 차단 필수 — 없으면 VPC 없는 함수 생성 가능
- VPC Lambda는 `ec2:CreateNetworkInterface`, `ec2:DescribeNetworkInterfaces`, `ec2:DeleteNetworkInterface` 권한도 실행 역할에 필요

---

### Case 05 — PassRole을 특정 실행 역할로만 제한

**시나리오**: Lambda 함수 생성/업데이트 시 `iam:PassRole`을 특정 실행 역할(`lambda-exec-*`)로만 제한. 고권한 역할 전달 차단.

**핵심 메커니즘**:
- Allow: `iam:PassRole` → Resource `arn:aws:iam::ACCOUNT:role/lambda-exec-*` + `iam:PassedToService: "lambda.amazonaws.com"`
- Deny: `iam:PassRole` → Resource `arn:aws:iam::ACCOUNT:role/Admin*`, `role/FullAccess*`

**허용**: `lambda-exec-` prefix 역할을 Lambda에 전달
**거부**: Admin, FullAccess 등 고권한 역할 전달 → `AccessDenied`

**주의사항**:
- `iam:PassRole`의 Resource는 **전달 대상 Role ARN**이지 Lambda 함수 ARN이 아님 — 혼동 주의
- `iam:PassedToService` 조건으로 Lambda 서비스에만 전달 허용 — 다른 서비스(EC2, ECS 등)에 전달 차단
- `CreateFunction` + `PassRole`이 있으면 해당 Role의 권한을 간접 획득 가능 → PassRole 범위 최소화 필수
- Deny Statement로 고권한 역할을 명시적 차단하는 것이 Allow 범위 제한보다 확실

---

### Case 06 — 태그 기반 ABAC

**시나리오**: 함수의 `Team` 태그와 IAM 사용자의 `PrincipalTag/Team`이 일치할 때만 Invoke/관리 허용.

**핵심 메커니즘**:
- `aws:ResourceTag/Team` + `StringEquals` + `${aws:PrincipalTag/Team}` 동적 매칭
- Deny: `aws:PrincipalTag/Team` `Null: "true"` → 태그 없는 사용자 전면 차단
- Deny: `lambda:CreateFunction` + `aws:RequestTag/Team` `Null: "true"` → 생성 시 태그 강제

**허용**: `PrincipalTag/Team = backend` → `ResourceTag/Team = backend` 함수만
**거부**: 태그 불일치, 태그 미설정, 태그 없이 함수 생성

**주의사항**:
- `lambda:ListFunctions`는 태그 조건 적용 불가 → `Resource: "*"` 별도 Statement 필요
- `lambda:TagResource`/`lambda:UntagResource` 권한도 제어해야 태그 변경으로 우회 방지
- Layer에는 태그 기반 ABAC 미지원 — 함수 수준에서만 동작

---

### Case 07 — Resource-based Policy: API Gateway 호출 허용

**시나리오**: API Gateway가 특정 Lambda 함수를 호출할 수 있도록 Resource-based Policy(함수 정책) 설정.

**핵심 메커니즘**:
- Resource-based Policy: `Principal: {"Service": "apigateway.amazonaws.com"}`
- Allow: `lambda:InvokeFunction`
- Condition: `aws:SourceArn` → 특정 API Gateway 리소스 ARN (`arn:aws:execute-api:REGION:ACCOUNT:API_ID/*/METHOD/PATH`)

**허용**: 지정 API Gateway 엔드포인트에서 Lambda 호출
**거부**: 다른 API Gateway, 다른 서비스에서의 호출

**주의사항**:
- Resource-based Policy는 `aws lambda add-permission` CLI로 추가 — IAM 콘솔에서 직접 편집 불가
- `aws:SourceArn`의 API Gateway ARN 형식: `arn:aws:execute-api:REGION:ACCOUNT:API_ID/STAGE/METHOD/RESOURCE_PATH`
- `*`를 사용하면 모든 스테이지/메서드/경로 허용 — 최소 권한 원칙에 따라 범위 한정 권장
- `aws:SourceAccount` 조건 추가로 confused deputy 방지
- 같은 계정 내에서는 Resource-based Policy만으로 충분 — 호출자의 IAM Policy 불필요

---

## CloudShell 준비

```bash
export AWS_REGION="ap-northeast-2"
export ACCOUNT_ID="123456789012"
export FUNCTION_NAME="my-function"
export LAYER_NAME="my-layer"
export VPC_ID="vpc-0123456789abcdef0"
export SUBNET_ID_1="subnet-0123456789abcdef0"
export SUBNET_ID_2="subnet-0fedcba9876543210"
export SG_ID="sg-0123456789abcdef0"
export USER_NAME="mod3-lambda-user"
export PROFILE_NAME="mod3-lambda-user"
```

---

## 검증 예시

```bash
# 함수 Invoke — 성공 기대
aws lambda invoke \
  --function-name "$FUNCTION_NAME" \
  --payload '{}' /tmp/out.json \
  --profile "$PROFILE_NAME"

# 별칭 Invoke — 정책에 따라 성공/실패
aws lambda invoke \
  --function-name "$FUNCTION_NAME:PROD" \
  --payload '{}' /tmp/out.json \
  --profile "$PROFILE_NAME"

# 함수 생성 (VPC 없이) — SCP 있으면 AccessDenied 기대
aws lambda create-function \
  --function-name test-no-vpc \
  --runtime python3.12 \
  --handler index.handler \
  --role "arn:aws:iam::$ACCOUNT_ID:role/lambda-exec-role" \
  --zip-file fileb://function.zip \
  --profile "$PROFILE_NAME"

# 레이어 정책 시뮬레이션
aws iam simulate-principal-policy \
  --policy-source-arn "arn:aws:iam::$ACCOUNT_ID:user/$USER_NAME" \
  --action-names lambda:CreateFunction \
  --resource-arns "arn:aws:lambda:$AWS_REGION:$ACCOUNT_ID:function:test-fn" \
  --context-entries \
    "ContextKeyName=lambda:Layer,ContextKeyValues=[arn:aws:lambda:$AWS_REGION:$ACCOUNT_ID:layer:$LAYER_NAME:1],ContextKeyType=stringList"
```

---

## 감점 방지 포인트

- `lambda:Layer` 조건값은 **레이어 버전 ARN 전체** — 레이어 이름만 쓰면 매칭 실패
- Function URL 권한은 `lambda:InvokeFunctionUrl` + `lambda:InvokeFunction` **둘 다** 필요 (2025.10 이후)
- `lambda:InvokedViaFunctionUrl`은 **Bool 타입** — `"StringEquals"` 쓰면 오류, `"Bool"` 연산자 사용
- VPC 조건에서 `lambda:VpcIds`는 `StringEquals`/`StringNotEquals`, 배열 키(`SubnetIds`, `SecurityGroupIds`)는 `ForAllValues:StringNotEquals` 사용
- 리소스 기반 정책에서 서비스 Principal 사용 시 **혼동 대리인 방지**를 위해 `aws:SourceArn` + `aws:SourceAccount` 조건 필수
- `lambda:SourceFunctionArn`은 **Lambda 함수의 실행 역할 정책이 아닌 대상 서비스의 리소스 정책**에 작성
- 비정규화 ARN 허용 정책은 `:*` qualifier 호출을 거부함 — 둘 다 허용하려면 `function:my-fn*` 패턴 사용
