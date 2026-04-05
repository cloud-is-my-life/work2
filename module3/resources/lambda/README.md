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
| Case 01 | `policies/case01-function-invoke-specific.json` | 특정 함수/별칭만 Invoke 허용 (Qualifier 처리 포함) |
| Case 02 | `policies/case02-layer-access-control.json` | 허용 레이어 목록 강제 (lambda:Layer) |
| Case 03 | `policies/case03-vpc-enforcement.json` | VPC/서브넷/보안그룹 배포 강제 (SCP 패턴) |
| Case 04 | `policies/case04-tag-based-abac.json` | 태그 기반 ABAC (PrincipalTag → ResourceTag 매칭) |
| Case 05 | `policies/case05-function-url-auth.json` | Function URL 인증 타입 강제 + InvokedViaFunctionUrl |
| Case 06 | `policies/case06-alias-version-restriction.json` | 별칭/버전 기반 호출 제한 (프로덕션 보호) |
| Case 07 | `policies/case07-resource-based-cross-account.json` | 리소스 기반 정책 패턴 (크로스 계정, 서비스 Principal) |

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
