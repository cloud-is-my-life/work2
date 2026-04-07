# Lambda Fine-grained IAM 완전 정복 가이드

> AWS Skills Competition 2026 대비. ARN qualifier 함정 하나로 점수가 갈린다.

---

## 목차

1. [왜 Lambda IAM이 까다로운가](#1-왜-lambda-iam이-까다로운가)
2. [Qualified vs Unqualified ARN 완전 정복](#2-qualified-vs-unqualified-arn-완전-정복)
3. [실행 역할 vs 호출 권한 구분](#3-실행-역할-vs-호출-권한-구분)
4. [Lambda 전용 Condition Key 핵심 정리](#4-lambda-전용-condition-key-핵심-정리)
5. [Resource-based Policy 작성법 (add-permission CLI)](#5-resource-based-policy-작성법-add-permission-cli)
6. [케이스별 정책 해설 (Case 01~12)](#6-케이스별-정책-해설-case-0112)
7. [감점 방지 체크리스트](#7-감점-방지-체크리스트)

---

## 1. 왜 Lambda IAM이 까다로운가

Lambda는 IAM에서 두 가지 권한 레이어가 동시에 작동한다.

- **Identity-based policy**: 누가 Lambda API를 호출할 수 있는가 (함수 생성, 코드 배포, Invoke 등)
- **Resource-based policy (함수 정책)**: 어떤 서비스/계정이 이 함수를 호출할 수 있는가

여기에 ARN qualifier(버전/별칭) 문제가 더해지면 경험 없이는 바로 틀린다. 이 가이드는 그 함정을 전부 짚는다.

---

## 2. Qualified vs Unqualified ARN 완전 정복

Lambda ARN에는 두 종류가 있다.

```
# Unqualified ARN — 버전/별칭 없음, $LATEST 호출
arn:aws:lambda:ap-northeast-2:123456789012:function:my-fn

# Qualified ARN — 버전 번호
arn:aws:lambda:ap-northeast-2:123456789012:function:my-fn:3

# Qualified ARN — 별칭
arn:aws:lambda:ap-northeast-2:123456789012:function:my-fn:PROD
```

### 핵심 규칙: 두 ARN은 IAM에서 별개 리소스다

정책 Resource에 unqualified ARN만 넣으면 `my-fn:PROD` 호출이 `AccessDenied`다. 반대도 마찬가지.

| Resource 패턴 | `my-fn` 호출 | `my-fn:PROD` 호출 | `my-fn:3` 호출 |
|---|:---:|:---:|:---:|
| `function:my-fn` | ✅ | ❌ | ❌ |
| `function:my-fn:PROD` | ❌ | ✅ | ❌ |
| `function:my-fn:*` | ❌ | ✅ | ✅ |
| `function:my-fn*` | ✅ | ✅ | ✅ |

### 실전 권장 패턴

별칭/버전 호출을 모두 허용하려면 Resource 배열에 두 패턴을 같이 쓴다.

```json
"Resource": [
  "arn:aws:lambda:ap-northeast-2:123456789012:function:my-fn",
  "arn:aws:lambda:ap-northeast-2:123456789012:function:my-fn:*"
]
```

또는 와일드카드 suffix를 쓴다.

```json
"Resource": "arn:aws:lambda:ap-northeast-2:123456789012:function:my-fn*"
```

`my-fn*`은 `my-fn-v2` 같은 다른 함수도 매칭되므로 함수 이름이 고유하다는 확신이 있을 때만 사용한다.

### $LATEST vs 버전 번호

`$LATEST`는 unqualified ARN과 동일하게 취급된다. `function:my-fn:$LATEST`로 명시 호출해도 unqualified ARN 허용 정책이 있으면 통과한다.

---

## 3. 실행 역할 vs 호출 권한 구분

이 둘을 혼동하면 설계 자체가 틀린다.

### 실행 역할 (Execution Role)

함수가 **실행될 때** AWS 서비스를 호출하는 권한이다.

- 함수에 붙이는 IAM Role
- `lambda.amazonaws.com`이 이 Role을 assume
- 예: 함수가 S3에서 파일을 읽거나 DynamoDB에 쓸 때 필요한 권한

```
[Lambda 함수] --assume--> [실행 역할] --권한--> [S3, DynamoDB, ...]
```

실행 역할을 함수에 연결하려면 호출자(개발자/CI)에게 `iam:PassRole` 권한이 필요하다.

```json
{
  "Effect": "Allow",
  "Action": "iam:PassRole",
  "Resource": "arn:aws:iam::123456789012:role/lambda-exec-*",
  "Condition": {
    "StringEquals": {
      "iam:PassedToService": "lambda.amazonaws.com"
    }
  }
}
```

### 호출 권한 (Invoke Permission)

누가 **함수를 호출**할 수 있는가다.

- Identity-based policy: IAM 사용자/역할이 `lambda:InvokeFunction`을 가지면 호출 가능
- Resource-based policy: API Gateway, SNS, EventBridge 같은 AWS 서비스가 함수를 호출할 때 필요

```
[API Gateway] --resource-based policy--> [Lambda 함수]
[IAM User]    --identity-based policy--> [Lambda 함수]
```

같은 계정 내 IAM 주체가 호출할 때는 identity-based policy만으로 충분하다. 다른 계정이나 AWS 서비스가 호출할 때는 resource-based policy가 필요하다.

### Function URL의 특수성

Function URL은 두 권한이 모두 필요하다 (2025년 10월 이후 신규 URL 기준).

- `lambda:InvokeFunctionUrl`: URL 엔드포인트 호출 권한
- `lambda:InvokeFunction`: 실제 함수 실행 권한

하나만 있으면 403이 반환된다.

---

## 4. Lambda 전용 Condition Key 핵심 정리

### lambda:Layer

함수에 첨부 가능한 레이어를 제한한다. **레이어 버전 ARN 전체**를 값으로 써야 한다.

```json
"Condition": {
  "ForAnyValue:StringNotEquals": {
    "lambda:Layer": [
      "arn:aws:lambda:ap-northeast-2:123456789012:layer:approved-layer:1"
    ]
  }
}
```

레이어 이름만 쓰면 매칭이 안 된다. `:VERSION_NUMBER`까지 포함해야 한다.

타입이 `ArrayOfString`이므로 `ForAnyValue:` / `ForAllValues:` prefix를 붙인다.

### lambda:FunctionUrlAuthType

Function URL 인증 타입을 강제한다. 값은 `AWS_IAM` 또는 `NONE`.

```json
"Condition": {
  "StringNotEquals": {
    "lambda:FunctionUrlAuthType": "AWS_IAM"
  }
}
```

`NONE`으로 설정된 URL은 인터넷에 공개된다. 조직 정책으로 `AWS_IAM`만 허용하려면 Deny + `StringNotEquals` 조합을 쓴다.

### lambda:VpcIds vs lambda:SubnetIds / lambda:SecurityGroupIds

타입이 다르므로 연산자 선택이 달라진다.

| Condition Key | 타입 | 연산자 |
|---|---|---|
| `lambda:VpcIds` | String | `StringEquals`, `StringNotEquals` |
| `lambda:SubnetIds` | ArrayOfString | `ForAllValues:StringEquals` |
| `lambda:SecurityGroupIds` | ArrayOfString | `ForAllValues:StringEquals` |

### lambda:InvokedViaFunctionUrl

Bool 타입이다. `StringEquals`를 쓰면 오류가 난다.

```json
"Condition": {
  "Bool": {
    "lambda:InvokedViaFunctionUrl": "true"
  }
}
```

### lambda:SourceFunctionArn

Lambda 함수가 다른 AWS 서비스를 호출할 때 출처 함수를 제한한다. 이 조건은 **Lambda 함수의 실행 역할 정책이 아닌 대상 서비스의 리소스 정책**에 작성한다.

예: Secrets Manager 리소스 정책에서 특정 Lambda 함수만 시크릿을 읽도록 제한할 때 사용.

---

## 5. Resource-based Policy 작성법 (add-permission CLI)

Lambda의 resource-based policy는 IAM 콘솔에서 직접 편집할 수 없다. `aws lambda add-permission` CLI로만 추가한다.

### 기본 구조

```bash
aws lambda add-permission \
  --function-name FUNCTION_NAME \
  --statement-id STATEMENT_ID \
  --action lambda:InvokeFunction \
  --principal SERVICE_OR_ACCOUNT \
  --source-arn SOURCE_ARN \
  --source-account ACCOUNT_ID
```

### API Gateway 트리거 허용

```bash
aws lambda add-permission \
  --function-name my-fn \
  --statement-id allow-apigw \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:ap-northeast-2:123456789012:abc123def/*/POST/orders" \
  --source-account 123456789012
```

### SNS 트리거 허용

```bash
aws lambda add-permission \
  --function-name my-fn \
  --statement-id allow-sns \
  --action lambda:InvokeFunction \
  --principal sns.amazonaws.com \
  --source-arn "arn:aws:sns:ap-northeast-2:123456789012:my-topic" \
  --source-account 123456789012
```

### EventBridge 트리거 허용

```bash
aws lambda add-permission \
  --function-name my-fn \
  --statement-id allow-eventbridge \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn "arn:aws:events:ap-northeast-2:123456789012:rule/my-rule" \
  --source-account 123456789012
```

### 현재 정책 확인

```bash
aws lambda get-policy --function-name my-fn
```

### 특정 Statement 제거

```bash
aws lambda remove-permission \
  --function-name my-fn \
  --statement-id allow-apigw
```

### 혼동 대리인(Confused Deputy) 방지

서비스 Principal을 사용할 때는 `--source-arn`과 `--source-account`를 항상 같이 지정한다. `source-arn`만 있으면 다른 계정의 같은 서비스가 호출할 수 있는 경우가 생긴다.

---

## 6. 케이스별 정책 해설 (Case 01~12)

### Case 01 — 특정 함수만 Invoke 허용 (별칭 포함)

파일: `policies/case01-invoke-specific-function.json`

별칭(`PROD`)이나 버전 번호로 호출하는 경우도 허용한다. Resource에 unqualified ARN과 `:*` 패턴을 둘 다 넣는다.

```
허용: invoke --function-name FUNCTION_NAME
허용: invoke --function-name FUNCTION_NAME:PROD
거부: 다른 함수 호출
```

### Case 02 — 코드 배포만 허용 (설정 변경 차단)

파일: `policies/case02-deploy-only.json`

`UpdateFunctionCode`와 `UpdateFunctionConfiguration`은 별도 Action이다. 코드만 허용하고 설정은 Deny로 차단한다.

```
허용: UpdateFunctionCode, PublishVersion, CreateAlias, UpdateAlias
거부: UpdateFunctionConfiguration, DeleteFunction, CreateFunction
```

### Case 03 — 함수 삭제 차단

파일: `policies/case03-deny-delete-function.json`

Explicit Deny로 삭제를 막는다. `DeleteFunction`은 특정 버전 삭제에도 사용되므로 버전 삭제도 함께 차단된다.

### Case 04 — 특정 VPC/서브넷에서만 함수 생성 허용

파일: `policies/case04-vpc-restriction.json`

`lambda:VpcIds`는 String, `lambda:SubnetIds`는 ArrayOfString이다. 연산자를 다르게 써야 한다. `Null` 조건으로 VPC 미지정 케이스도 차단한다.

### Case 05 — PassRole을 특정 실행 역할로만 제한

파일: `policies/case05-passrole-scoped.json`

`iam:PassRole`의 Resource는 전달 대상 Role ARN이다. Lambda 함수 ARN이 아니다. `iam:PassedToService` 조건으로 Lambda 서비스에만 전달을 허용한다.

### Case 06 — 태그 기반 ABAC

파일: `policies/case06-abac-tag-based.json`

`aws:ResourceTag/Team`과 `${aws:PrincipalTag/Team}`을 동적 매칭한다. 태그 없는 사용자는 Deny로 전면 차단한다.

### Case 07 — Resource-based Policy: API Gateway 호출 허용

파일: `policies/case07-resource-policy-apigw.json`

`aws:SourceArn`으로 특정 API Gateway 엔드포인트만 허용한다. `aws:SourceAccount`를 같이 써서 혼동 대리인을 방지한다.

---

### Case 08 — 레이어 버전 제한

파일: `policies/case08-layer-version-restriction.json`

승인된 레이어 버전 ARN 목록 외의 레이어를 함수에 첨부하지 못하도록 차단한다.

**핵심 메커니즘**:
- Deny: `lambda:CreateFunction`, `lambda:UpdateFunctionConfiguration`
- Condition: `ForAnyValue:StringNotEquals` + `lambda:Layer` + 허용 레이어 버전 ARN 목록

```json
"Condition": {
  "ForAnyValue:StringNotEquals": {
    "lambda:Layer": [
      "arn:aws:lambda:AWS_REGION:ACCOUNT_ID:layer:LAYER_NAME:1",
      "arn:aws:lambda:AWS_REGION:ACCOUNT_ID:layer:LAYER_NAME:2"
    ]
  }
}
```

**주의사항**:
- `lambda:Layer` 값은 레이어 버전 ARN 전체다. 레이어 이름만 쓰면 매칭 실패
- `ForAnyValue:StringNotEquals`는 "요청한 레이어 중 하나라도 허용 목록에 없으면 Deny"
- 레이어를 아예 안 붙이는 경우(빈 배열)는 이 조건에 걸리지 않는다. 레이어 없는 함수 생성은 허용됨

```
허용: 승인된 레이어 버전만 첨부한 함수 생성/수정
거부: 미승인 레이어 첨부 시도
```

---

### Case 09 — Function URL 인증 타입 강제 (AWS_IAM)

파일: `policies/case09-function-url-auth-enforce.json`

Function URL을 `NONE`(공개) 타입으로 생성하거나 변경하지 못하도록 강제한다. 조직 내 모든 Function URL은 `AWS_IAM` 인증만 허용한다.

**핵심 메커니즘**:
- Deny: `lambda:CreateFunctionUrlConfig`, `lambda:UpdateFunctionUrlConfig`
- Condition: `StringNotEquals` + `lambda:FunctionUrlAuthType: "AWS_IAM"`
- 추가 Deny: `lambda:AddPermission` + `lambda:FunctionUrlAuthType: "NONE"` (공개 URL에 권한 추가 차단)

```json
"Condition": {
  "StringNotEquals": {
    "lambda:FunctionUrlAuthType": "AWS_IAM"
  }
}
```

**주의사항**:
- `lambda:FunctionUrlAuthType`은 String 타입이므로 `StringEquals`/`StringNotEquals` 사용
- `AddPermission`에도 Deny를 걸어야 `NONE` 타입 URL에 public 접근 권한 추가를 막을 수 있다
- 기존에 `NONE`으로 생성된 URL은 이 정책으로 소급 차단되지 않는다. 기존 URL은 별도로 수정 필요

```
허용: AWS_IAM 인증 타입으로 Function URL 생성/수정
거부: NONE(공개) 타입 URL 생성/수정 시도
```

---

### Case 10 — 동시성 설정 변경 차단

파일: `policies/case10-deny-concurrency-change.json`

개발자가 코드 배포는 할 수 있지만 함수의 동시성(reserved/provisioned concurrency) 설정은 변경하지 못하도록 차단한다. 동시성 설정은 운영팀만 관리한다.

**핵심 메커니즘**:
- Allow: 코드 배포 관련 Action (`UpdateFunctionCode`, `PublishVersion`, `CreateAlias`, `UpdateAlias`)
- Deny: `lambda:PutFunctionConcurrency`, `lambda:DeleteFunctionConcurrency`, `lambda:PutProvisionedConcurrencyConfig`, `lambda:DeleteProvisionedConcurrencyConfig`

**주의사항**:
- Reserved concurrency와 provisioned concurrency는 별도 Action이다. 둘 다 Deny해야 완전 차단
- `GetFunctionConcurrency`, `ListProvisionedConcurrencyConfigs`는 읽기 전용이므로 Allow에 포함해도 무방
- Case 02(코드 배포만 허용)와 조합하면 더 강력한 배포 전용 정책이 된다

```
허용: 코드 업데이트, 버전 발행, 별칭 관리, 동시성 조회
거부: 예약 동시성 설정/삭제, 프로비저닝 동시성 설정/삭제
```

---

### Case 11 — 환경 변수 변경 차단 (코드만 배포 허용)

파일: `policies/case11-deny-env-var-change.json`

`UpdateFunctionConfiguration`을 Deny해서 환경 변수, 메모리, 타임아웃, VPC 설정 등 모든 함수 설정 변경을 차단한다. 코드 업데이트와 버전/별칭 관리만 허용한다.

**핵심 메커니즘**:
- Allow: `lambda:UpdateFunctionCode`, `lambda:PublishVersion`, `lambda:CreateAlias`, `lambda:UpdateAlias`, `lambda:GetFunction`, `lambda:GetFunctionConfiguration`, `lambda:ListVersionsByFunction`, `lambda:ListAliases`
- Deny: `lambda:UpdateFunctionConfiguration`

**Case 02와의 차이점**:

| 항목 | Case 02 | Case 11 |
|---|---|---|
| 함수 생성 | Deny | 미포함 (상위 정책에 위임) |
| 함수 삭제 | Deny | 미포함 |
| 설정 변경 | Deny | Deny (명시적) |
| 코드 배포 | Allow | Allow |
| 대상 Resource | 특정 함수 | 특정 함수 |

Case 11은 특정 함수에 대한 코드 배포 전용 권한을 부여하는 데 집중한다.

**주의사항**:
- `UpdateFunctionConfiguration`은 환경 변수뿐 아니라 메모리, 타임아웃, 핸들러, 레이어, VPC 설정도 포함한다. 하나의 Action으로 모든 설정 변경이 차단됨
- `GetFunctionConfiguration`은 읽기 전용이므로 Allow에 포함해도 보안 문제 없음

```
허용: 코드 업데이트, 버전 발행, 별칭 생성/수정, 함수 정보 조회
거부: 환경 변수 변경, 메모리/타임아웃 변경, VPC 설정 변경
```

---

### Case 12 — Resource-based Policy: SNS 트리거 허용

파일: `policies/case12-resource-policy-sns-trigger.json`

SNS 토픽이 Lambda 함수를 트리거할 수 있도록 resource-based policy를 설정한다. `aws:SourceArn`으로 특정 토픽만 허용하고 `aws:SourceAccount`로 혼동 대리인을 방지한다.

**핵심 메커니즘**:
- Principal: `sns.amazonaws.com`
- Action: `lambda:InvokeFunction`
- Condition: `ArnLike` + `aws:SourceArn` (특정 SNS 토픽 ARN)
- Condition: `StringEquals` + `aws:SourceAccount` (계정 ID)

```json
{
  "Principal": { "Service": "sns.amazonaws.com" },
  "Action": "lambda:InvokeFunction",
  "Condition": {
    "ArnLike": {
      "aws:SourceArn": "arn:aws:sns:ap-northeast-2:123456789012:my-topic"
    },
    "StringEquals": {
      "aws:SourceAccount": "123456789012"
    }
  }
}
```

**CLI로 적용하는 방법**:

```bash
aws lambda add-permission \
  --function-name my-fn \
  --statement-id allow-sns-trigger \
  --action lambda:InvokeFunction \
  --principal sns.amazonaws.com \
  --source-arn "arn:aws:sns:ap-northeast-2:123456789012:my-topic" \
  --source-account 123456789012
```

**주의사항**:
- SNS 구독 생성은 별도 작업이다. `add-permission`은 호출 권한만 부여하고 구독은 `aws sns subscribe`로 따로 생성
- `aws:SourceArn`에 `ArnLike`를 쓰면 와일드카드(`*`) 사용 가능. 정확한 ARN이면 `ArnEquals`도 동일하게 동작
- 크로스 계정 SNS 트리거는 `aws:SourceAccount`가 필수다. 같은 계정이라도 명시하는 것이 권장됨

```
허용: 지정 SNS 토픽에서 Lambda 호출
거부: 다른 토픽, 다른 계정의 SNS에서 호출
```

---

## 7. 감점 방지 체크리스트

경기 중 자주 틀리는 포인트만 모았다.

**ARN 관련**
- [ ] Invoke 정책에 unqualified ARN과 `:*` 패턴을 둘 다 넣었는가
- [ ] `lambda:Layer` 조건값에 레이어 버전 ARN 전체(`:VERSION_NUMBER` 포함)를 썼는가
- [ ] `lambda:ListFunctions`는 `Resource: "*"` 필수임을 확인했는가

**타입/연산자 관련**
- [ ] `lambda:VpcIds`는 `StringEquals`, `lambda:SubnetIds`/`lambda:SecurityGroupIds`는 `ForAllValues:StringEquals` 사용했는가
- [ ] `lambda:InvokedViaFunctionUrl`은 `Bool` 연산자를 썼는가 (`StringEquals` 아님)
- [ ] `lambda:Layer`는 `ForAnyValue:` / `ForAllValues:` prefix를 붙였는가

**Function URL 관련**
- [ ] Function URL 호출 시 `lambda:InvokeFunctionUrl` + `lambda:InvokeFunction` 둘 다 있는가
- [ ] `NONE` 타입 URL 차단 시 `AddPermission`에도 Deny를 걸었는가

**Resource-based Policy 관련**
- [ ] `add-permission` CLI에 `--source-arn`과 `--source-account`를 둘 다 지정했는가
- [ ] `lambda:SourceFunctionArn`은 Lambda 실행 역할이 아닌 대상 서비스의 리소스 정책에 작성했는가

**PassRole 관련**
- [ ] `iam:PassRole`의 Resource가 Lambda 함수 ARN이 아닌 Role ARN인지 확인했는가
- [ ] `iam:PassedToService: "lambda.amazonaws.com"` 조건을 추가했는가

---

*AWS Skills Competition 2026 — Module 3 Lambda Fine-grained IAM*
