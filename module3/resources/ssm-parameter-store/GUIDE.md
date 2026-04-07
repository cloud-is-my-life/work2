# SSM Parameter Store Fine-grained IAM 완전 정복

> AWS Skills Competition 2026 | Module 3 실전 가이드

---

## 왜 SSM Parameter Store IAM이 까다로운가

S3나 DynamoDB와 달리 SSM Parameter Store는 몇 가지 독특한 함정이 있다. ARN 구조가 직관적이지 않고, `DescribeParameters`는 리소스 수준 제어가 아예 불가능하며, `GetParameterHistory` 하나로 모든 읽기 제한을 우회할 수 있다. 이 가이드는 그 함정들을 하나씩 짚으면서 10가지 실전 케이스를 다룬다.

---

## ARN /parameter 접두사 함정

SSM Parameter Store에서 가장 많이 틀리는 부분이다.

파라미터 이름이 `/app/prod/db/host`라면 ARN은 이렇게 생겼다.

```
arn:aws:ssm:ap-northeast-2:123456789012:parameter/app/prod/db/host
```

`parameter`와 `/app/prod/db/host` 사이에 슬래시가 하나뿐이다. 파라미터 이름 자체가 `/`로 시작하기 때문에 ARN에서는 `parameter/app/...`처럼 보인다. `parameter//app/...`이 아니다.

경로 와일드카드를 쓸 때도 마찬가지다.

```
# 올바른 패턴
arn:aws:ssm:REGION:ACCOUNT_ID:parameter/app/prod/*

# 틀린 패턴 (이중 슬래시)
arn:aws:ssm:REGION:ACCOUNT_ID:parameter//app/prod/*
```

이중 슬래시로 쓰면 정책이 적용되지 않아 `AccessDenied`가 나거나, 반대로 의도치 않은 접근이 허용된다. 경기 중에 이 실수 하나로 케이스 전체가 날아간다.

---

## 경로 계층 구조 완전 정복

SSM Parameter Store의 경로는 파일 시스템처럼 계층 구조를 가진다.

```
/app/
  prod/
    db/
      host
      password
    api/
      key
  dev/
    db/
      host
```

`/app/prod/*` 권한을 주면 `/app/prod/db/host`, `/app/prod/api/key` 등 하위 전체에 접근 가능하다. `/app/prod/db/*`로 좁히면 `db` 하위만 허용된다.

`GetParametersByPath`를 쓸 때 `--recursive` 플래그 유무가 중요하다.

- `--recursive` 없음: 지정 경로의 직계 하위만 반환
- `--recursive` 있음: 지정 경로 아래 모든 계층 반환

`ssm:Recursive` 조건 키로 재귀 조회를 차단할 수 있다. Case 03이 이 패턴을 다룬다.

### DescribeParameters는 항상 `"Resource": "*"`

`DescribeParameters`는 리소스 수준 제어가 불가능한 액션이다. 특정 ARN을 지정하면 오류가 난다. 반드시 `"Resource": "*"`로 써야 한다. 이 액션은 파라미터 이름과 메타데이터를 반환하지만 값은 반환하지 않는다.

---

## SecureString + KMS 연동 설계

SecureString은 KMS로 암호화되는 파라미터 타입이다. 여기서 중요한 점이 있다.

기본 키인 `aws/ssm`을 쓰면 계정 내 모든 IAM 엔티티가 Decrypt할 수 있다. SecureString으로 만들어도 사실상 암호화 의미가 없어진다. 민감한 값을 진짜로 보호하려면 고객 관리형 KMS 키(CMK)를 써야 한다.

CMK를 강제하는 방법은 두 가지다.

**방법 1: KMS 키 정책에서 `aws/ssm` 사용 차단**
KMS 키 정책 레벨에서 특정 IAM 엔티티의 기본 키 사용을 막는다.

**방법 2: IAM 정책에서 기본 키 ARN에 대한 KMS 액션 Deny**
Case 04가 이 방식을 쓴다. `kms:Encrypt`, `kms:GenerateDataKey`, `kms:Decrypt`를 기본 키 ARN에 대해 Deny한다.

CMK를 쓸 때는 해당 키의 Key Policy에도 사용자의 `kms:Encrypt`, `kms:Decrypt`, `kms:GenerateDataKey` 권한이 있어야 한다. IAM 정책만 있고 Key Policy에 없으면 접근이 안 된다.

---

## GetParameterHistory 우회 방지

`GetParameter`를 Deny해도 `GetParameterHistory`로 파라미터의 모든 이전 값을 조회할 수 있다. SecureString도 마찬가지다. 읽기를 제한할 때 `GetParameterHistory`를 빠뜨리면 우회 경로가 열린다.

읽기 전용 정책을 만들 때 포함 여부를 명확히 결정해야 한다.

- 이전 값 조회도 허용: `GetParameterHistory` Allow에 포함
- 이전 값 조회 차단: 명시적 Deny 추가 (Case 10)

Case 07(Lambda 읽기 전용)에서는 `GetParameterHistory`를 명시적으로 Deny해서 현재 값만 읽을 수 있도록 설계했다.

---

## 케이스별 상세 분석

### Case 01 — 경로 기반 읽기 전용

**파일**: `policies/case01-path-readonly.json`

`/app/prod/` 경로 하위 파라미터만 읽기 허용. 쓰기와 삭제는 허용하지 않는다.

```json
{
  "Sid": "AllowReadProdPath",
  "Effect": "Allow",
  "Action": [
    "ssm:GetParameter",
    "ssm:GetParameters",
    "ssm:GetParametersByPath",
    "ssm:GetParameterHistory"
  ],
  "Resource": "arn:aws:ssm:AWS_REGION:ACCOUNT_ID:parameter/app/prod/*"
}
```

`DescribeParameters`는 별도 Statement로 `"Resource": "*"` 처리한다.

검증 포인트:
- `/app/prod/db/host` 읽기 성공
- `/app/dev/db/host` 읽기 `AccessDenied`
- `PutParameter` `AccessDenied`

---

### Case 02 — 덮어쓰기 + 삭제 차단

**파일**: `policies/case02-deny-overwrite-delete.json`

신규 파라미터 생성은 허용하되 기존 값 변경과 삭제를 막는다.

`ssm:Overwrite` 조건 키가 핵심이다. `PutParameter`를 호출할 때 `--overwrite` 플래그를 쓰면 이 조건이 `"true"`가 된다.

```json
{
  "Sid": "DenyOverwrite",
  "Effect": "Deny",
  "Action": "ssm:PutParameter",
  "Resource": "arn:aws:ssm:AWS_REGION:ACCOUNT_ID:parameter/app/prod/*",
  "Condition": {
    "StringEquals": {
      "ssm:Overwrite": "true"
    }
  }
}
```

삭제 차단은 `DeleteParameter`(단건)와 `DeleteParameters`(복수) 둘 다 Deny해야 한다. 하나만 막으면 다른 쪽으로 우회된다.

---

### Case 03 — 민감 경로 재귀 조회 차단

**파일**: `policies/case03-deny-recursive-sensitive.json`

`/app/prod/secrets/` 경로는 개별 조회만 허용하고 `GetParametersByPath --recursive`로 한 번에 긁어가는 것을 막는다.

```json
{
  "Sid": "DenyRecursiveOnSecrets",
  "Effect": "Deny",
  "Action": "ssm:GetParametersByPath",
  "Resource": "arn:aws:ssm:AWS_REGION:ACCOUNT_ID:parameter/app/prod/secrets/*",
  "Condition": {
    "StringEquals": {
      "ssm:Recursive": "true"
    }
  }
}
```

`ssm:Recursive` 조건은 `GetParametersByPath`에만 적용된다. `--no-recursive`로 직계 하위만 조회하는 것도 막으려면 조건 없이 Action 자체를 Deny해야 한다.

---

### Case 04 — CMK 강제 + 기본 키 차단

**파일**: `policies/case04-enforce-cmk-securestring.json`

SecureString 생성 시 승인된 CMK만 쓰도록 강제한다. 기본 `aws/ssm` 키 사용을 KMS 액션 Deny로 차단한다.

```json
{
  "Sid": "DenyDefaultSSMKey",
  "Effect": "Deny",
  "Action": [
    "kms:Encrypt",
    "kms:GenerateDataKey",
    "kms:Decrypt"
  ],
  "Resource": "arn:aws:kms:AWS_REGION:ACCOUNT_ID:key/DEFAULT_SSM_KEY_ID"
}
```

`DEFAULT_SSM_KEY_ID`는 실제 환경에서 `aws kms describe-key --key-id alias/aws/ssm`으로 확인한다.

String/StringList 타입은 KMS와 무관하므로 이 정책의 영향을 받지 않는다.

---

### Case 05 — 태그 기반 ABAC

**파일**: `policies/case05-abac-tag-based.json`

파라미터의 `Team` 태그와 IAM 주체의 `PrincipalTag/Team`이 일치할 때만 접근 허용한다.

```json
{
  "Sid": "AllowReadByTag",
  "Effect": "Allow",
  "Action": [
    "ssm:GetParameter",
    "ssm:GetParameters",
    "ssm:GetParametersByPath"
  ],
  "Resource": "arn:aws:ssm:AWS_REGION:ACCOUNT_ID:parameter/*",
  "Condition": {
    "StringEquals": {
      "aws:ResourceTag/Team": "${aws:PrincipalTag/Team}"
    }
  }
}
```

태그 없는 주체를 막으려면 `Null` 조건으로 Deny를 추가해야 한다. Allow만 있으면 태그가 없는 사용자가 조건을 우회할 수 있다.

`DescribeParameters`는 태그 필터링이 불가능해서 모든 파라미터 이름이 노출된다. 값은 노출되지 않지만 이름 자체가 민감 정보일 수 있다.

레이블(Label) 기반 접근 제어는 IAM 조건 키가 없어서 불가능하다. 태그만 쓸 수 있다.

---

### Case 06 — EC2 Run Command 파라미터 참조

**파일**: `policies/case06-ec2-run-command-params.json`

EC2 Run Command 실행 시 SSM 파라미터를 참조할 수 있도록 읽기 권한을 주되, 파라미터 수정은 차단한다.

`SendCommand` 권한은 문서(Document) ARN과 인스턴스 ARN 두 가지 Resource가 필요하다. 문서는 `ssm` 서비스 ARN, 인스턴스는 `ec2` 서비스 ARN이다.

```json
{
  "Sid": "AllowSendCommand",
  "Effect": "Allow",
  "Action": [
    "ssm:SendCommand",
    "ssm:ListCommands",
    "ssm:ListCommandInvocations",
    "ssm:GetCommandInvocation"
  ],
  "Resource": [
    "arn:aws:ssm:REGION:*:document/AWS-RunShellScript",
    "arn:aws:ec2:REGION:ACCOUNT_ID:instance/*"
  ]
}
```

파라미터 경로는 `/ec2/run-command/*`로 분리해서 Run Command 전용 파라미터만 읽을 수 있게 범위를 좁혔다.

---

### Case 07 — Lambda 환경 설정 읽기 전용

**파일**: `policies/case07-lambda-env-ssm-readonly.json`

Lambda 실행 역할에 붙이는 정책이다. `/lambda/*` 경로의 설정값을 읽기만 하고 수정하거나 이전 값을 조회하지 못하도록 설계했다.

`GetParameterHistory`를 명시적으로 Deny한 것이 핵심이다. Lambda가 현재 설정값만 읽어야 하는 상황에서 이전 버전 값이 노출되면 보안 문제가 생길 수 있다.

태그 변경(`AddTagsToResource`, `RemoveTagsFromResource`)도 Deny에 포함했다. 태그를 바꿔서 ABAC 조건을 우회하는 경로를 막기 위해서다.

---

### Case 08 — SecureString 생성 차단

**파일**: `policies/case08-deny-securestring-create.json`

String과 StringList 타입만 생성 허용하고 SecureString 생성을 차단한다. 특정 환경에서 KMS 비용 통제나 타입 일관성 유지를 위해 쓰는 패턴이다.

```json
{
  "Sid": "DenySecureStringCreate",
  "Effect": "Deny",
  "Action": "ssm:PutParameter",
  "Resource": "arn:aws:ssm:REGION:ACCOUNT_ID:parameter/*",
  "Condition": {
    "StringEquals": {
      "ssm:ParamType": "SecureString"
    }
  }
}
```

`ssm:ParamType` 조건 키는 `PutParameter` 호출 시 `--type` 파라미터 값을 검사한다. `SecureString`을 지정하면 Deny가 발동한다.

---

### Case 09 — 크로스 계정 Advanced Tier 파라미터 공유

**파일**: `policies/case09-cross-account-advanced-tier.json`

Standard 파라미터는 크로스 계정 공유가 불가능하다. Advanced Tier 파라미터만 다른 계정에서 전체 ARN으로 접근할 수 있다.

소비 계정(Consumer Account)의 IAM 정책에서 소스 계정 ARN을 명시적으로 허용해야 한다.

```json
{
  "Sid": "AllowReadAdvancedTierCrossAccount",
  "Effect": "Allow",
  "Action": [
    "ssm:GetParameter",
    "ssm:GetParameters",
    "ssm:GetParametersByPath"
  ],
  "Resource": "arn:aws:ssm:REGION:SOURCE_ACCOUNT_ID:parameter/shared/*"
}
```

SecureString을 크로스 계정으로 공유할 때는 소스 계정의 CMK Key Policy에 소비 계정의 접근도 허용해야 한다. IAM 정책만으로는 부족하다.

소비 계정에서 파라미터 이름만으로는 접근이 안 된다. 반드시 전체 ARN을 써야 한다.

---

### Case 10 — GetParameterHistory 차단

**파일**: `policies/case10-history-deny.json`

현재 값 읽기는 허용하되 이전 버전 값 조회를 차단한다. SecureString의 이전 값이 노출되는 경로를 막는 가장 직접적인 방법이다.

```json
{
  "Sid": "DenyGetParameterHistory",
  "Effect": "Deny",
  "Action": "ssm:GetParameterHistory",
  "Resource": "arn:aws:ssm:REGION:ACCOUNT_ID:parameter/*"
}
```

Explicit Deny이므로 다른 정책에서 Allow가 있어도 이 Deny가 우선한다. 파라미터 값을 변경하는 운영 환경에서 이전 비밀번호나 API 키가 History API로 노출되는 것을 막는다.

---

## 감점 방지 포인트 정리

**ARN 관련**
- `parameter/app/prod/*` 패턴에서 이중 슬래시 금지
- `DescribeParameters`는 반드시 `"Resource": "*"`
- 크로스 계정 접근은 이름이 아닌 전체 ARN 사용

**Deny 관련**
- `DeleteParameter`와 `DeleteParameters` 둘 다 Deny
- `GetParameterHistory` 빠뜨리면 읽기 제한 우회 가능
- ABAC에서 태그 없는 주체 차단은 Allow만으로 부족, Deny 필수

**KMS 관련**
- SecureString 보호는 SSM 정책만으로 부족, KMS Decrypt Deny 필요
- CMK 사용 시 Key Policy에도 권한 추가 필수
- 기본 `aws/ssm` 키는 계정 내 전체 허용이 기본값

**크로스 계정 관련**
- Standard Tier는 크로스 계정 공유 불가
- Advanced Tier만 공유 가능, 소비 계정에서 전체 ARN 사용

---

## 검증 명령어

```bash
export AWS_REGION="ap-northeast-2"
export ACCOUNT_ID="123456789012"
export PROFILE_NAME="mod3-ssm-user"

# Case 01: 허용 경로 읽기
aws ssm get-parameter \
  --name "/app/prod/db/host" \
  --profile "$PROFILE_NAME"

# Case 01: 차단 경로 읽기 (AccessDenied 기대)
aws ssm get-parameter \
  --name "/app/dev/db/host" \
  --profile "$PROFILE_NAME"

# Case 02: 덮어쓰기 시도 (AccessDenied 기대)
aws ssm put-parameter \
  --name "/app/prod/db/host" \
  --value "new-value" \
  --overwrite \
  --profile "$PROFILE_NAME"

# Case 03: 재귀 조회 차단 (AccessDenied 기대)
aws ssm get-parameters-by-path \
  --path "/app/prod/secrets/" \
  --recursive \
  --profile "$PROFILE_NAME"

# Case 10: History 차단 (AccessDenied 기대)
aws ssm get-parameter-history \
  --name "/app/prod/db/password" \
  --profile "$PROFILE_NAME"
```
