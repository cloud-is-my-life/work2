# AWS Secrets Manager Fine-grained IAM 완전 정복 가이드

> AWS Skills Competition 2026 | Module 3 | Secrets Manager 심화

---

## 들어가며

Secrets Manager는 단순히 "비밀번호 저장소"가 아니다. IAM 정책, KMS 키 정책, Resource Policy가 3중으로 맞물리는 복잡한 서비스다. 특히 Secret ARN의 6자리 랜덤 suffix, 크로스 계정 공유 제약, 로테이션 Lambda 권한 설계는 경기장에서 자주 틀리는 포인트다.

이 가이드는 12개 실전 케이스를 통해 Secrets Manager IAM을 완전히 이해하는 것을 목표로 한다.

---

## Secret ARN suffix 완전 정복

### 왜 suffix가 붙는가

Secrets Manager는 시크릿 생성 시 ARN 끝에 6자리 랜덤 문자열을 자동으로 붙인다.

```
arn:aws:secretsmanager:ap-northeast-2:123456789012:secret:prod/db/mysql-AbCdEf
                                                                              ^^^^^^
                                                                         6자리 랜덤
```

이름이 같아도 삭제 후 재생성하면 suffix가 바뀐다. 정확한 ARN을 모르는 상태에서 정책을 작성해야 할 때 문제가 된다.

### `??????` vs `*` 차이

| 패턴 | 매칭 예시 | 위험성 |
|---|---|---|
| `prod/db/mysql-??????` | `prod/db/mysql-AbCdEf` 만 매칭 | 낮음 |
| `prod/db/mysql-*` | `prod/db/mysql-AbCdEf`, `prod/db/mysql-extra-anything` 모두 매칭 | 높음 |
| `prod/*` | `prod/` prefix 전체 | 의도에 따라 다름 |

`??????`는 정확히 6자리만 매칭한다. `*`는 길이 제한이 없어서 `prod/db/mysql-AbCdEf-extra`처럼 suffix 뒤에 추가 문자열이 붙은 ARN도 매칭된다. 경기장에서는 `??????`를 쓰는 것이 더 안전하다.

```json
{
  "Resource": "arn:aws:secretsmanager:REGION:ACCOUNT_ID:secret:prod/db/mysql-??????"
}
```

### 경로 prefix 패턴

특정 경로 전체를 허용할 때는 `prod/*`처럼 쓴다. 이 경우 suffix까지 포함해서 매칭되므로 별도로 `??????`를 붙일 필요가 없다.

```json
{
  "Resource": "arn:aws:secretsmanager:REGION:ACCOUNT_ID:secret:prod/*"
}
```

---

## Resource Policy 작성법

### Identity Policy vs Resource Policy

Secrets Manager는 두 가지 정책 레이어를 지원한다.

- Identity Policy: IAM 사용자/역할에 붙이는 일반 IAM 정책
- Resource Policy: 시크릿 자체에 붙이는 정책 (`put-resource-policy` CLI로 설정)

### 같은 계정 vs 크로스 계정 평가 방식

| 상황 | 평가 방식 | 의미 |
|---|---|---|
| 같은 계정 | 합집합 (OR) | Identity Policy 또는 Resource Policy 중 하나만 Allow면 접근 가능 |
| 크로스 계정 | 교집합 (AND) | Identity Policy AND Resource Policy 둘 다 Allow여야 접근 가능 |

같은 계정에서는 Deny가 있으면 합집합이어도 차단된다. Explicit Deny는 항상 우선이다.

### Resource Policy 설정 CLI

```bash
aws secretsmanager put-resource-policy \
  --secret-id "prod/db/mysql" \
  --resource-policy file://case06-resource-policy-vpce.json \
  --block-public-policy

# 현재 Resource Policy 확인
aws secretsmanager get-resource-policy \
  --secret-id "prod/db/mysql"

# Resource Policy 삭제
aws secretsmanager delete-resource-policy \
  --secret-id "prod/db/mysql"
```

### Resource Policy에서 Principal 지정

Resource Policy는 반드시 `Principal`을 명시해야 한다. Identity Policy와 달리 "누가" 접근하는지를 정책 안에 적어야 한다.

```json
{
  "Principal": {
    "AWS": "arn:aws:iam::ACCOUNT_ID:role/AppRole"
  }
}
```

크로스 계정 허용 시에는 상대 계정의 root 또는 특정 역할을 지정한다.

```json
{
  "Principal": {
    "AWS": "arn:aws:iam::TRUSTED_ACCOUNT_ID:root"
  }
}
```

---

## 로테이션 Lambda 권한 설계

### 로테이션 4단계 흐름

Secrets Manager 로테이션은 Lambda를 통해 4단계로 진행된다.

1. `createSecret` - `AWSPENDING` 스테이지로 새 버전 생성
2. `setSecret` - 실제 DB/서비스에 새 자격증명 적용
3. `testSecret` - 새 자격증명으로 접속 테스트
4. `finishSecret` - `AWSCURRENT`로 스테이지 전환, `AWSPREVIOUS`로 이전 버전 이동

### Lambda 실행 역할 필수 권한

```json
{
  "Action": [
    "secretsmanager:DescribeSecret",
    "secretsmanager:GetSecretValue",
    "secretsmanager:PutSecretValue",
    "secretsmanager:UpdateSecretVersionStage"
  ]
}
```

`AWSPENDING` 스테이지 접근이 반드시 필요하다. Case 05처럼 `VersionStage: AWSCURRENT`만 허용하는 정책을 로테이션 Lambda 역할에 적용하면 로테이션이 실패한다.

### VPC 내 Lambda 추가 권한

Lambda가 VPC 안에서 실행되면 ENI 생성/삭제 권한도 필요하다.

```json
{
  "Action": [
    "ec2:CreateNetworkInterface",
    "ec2:DeleteNetworkInterface",
    "ec2:DescribeNetworkInterfaces",
    "ec2:DetachNetworkInterface"
  ],
  "Resource": "*"
}
```

### CMK 사용 시 KMS 권한

시크릿이 CMK로 암호화된 경우 Lambda 역할에 KMS 권한도 추가해야 한다.

```json
{
  "Action": [
    "kms:Decrypt",
    "kms:DescribeKey",
    "kms:GenerateDataKey"
  ],
  "Resource": "arn:aws:kms:REGION:ACCOUNT_ID:key/CMK_KEY_ID"
}
```

---

## 크로스 계정 시크릿 공유 3단계

크로스 계정 시크릿 공유는 3개의 정책을 모두 설정해야 한다. 하나라도 빠지면 접근이 안 된다.

### 1단계: 시크릿 Resource Policy (소유 계정)

시크릿에 Resource Policy를 붙여 상대 계정의 접근을 허용한다.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowCrossAccountAccess",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::TRUSTED_ACCOUNT_ID:role/ConsumerRole"
      },
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": "*"
    }
  ]
}
```

### 2단계: KMS Key Policy (소유 계정)

크로스 계정 공유 시 반드시 CMK를 써야 한다. `aws/secretsmanager` AWS managed key는 크로스 계정 Key Policy 수정이 불가능하다.

```json
{
  "Sid": "AllowCrossAccountKMSAccess",
  "Effect": "Allow",
  "Principal": {
    "AWS": "arn:aws:iam::TRUSTED_ACCOUNT_ID:role/ConsumerRole"
  },
  "Action": [
    "kms:Decrypt",
    "kms:DescribeKey"
  ],
  "Resource": "*"
}
```

### 3단계: IAM Policy (상대 계정)

상대 계정의 역할/사용자에게 소유 계정의 시크릿 ARN을 명시한 IAM 정책을 붙인다.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": "arn:aws:secretsmanager:REGION:OWNER_ACCOUNT_ID:secret:prod/db/mysql-??????"
    },
    {
      "Effect": "Allow",
      "Action": [
        "kms:Decrypt",
        "kms:DescribeKey"
      ],
      "Resource": "arn:aws:kms:REGION:OWNER_ACCOUNT_ID:key/CMK_KEY_ID"
    }
  ]
}
```

---

## 케이스별 상세 가이드

### Case 01 — 경로 Prefix 기반 읽기 전용

**파일**: `policies/case01-path-prefix-readonly.json`

`prod/` prefix 시크릿만 읽기 허용하는 가장 기본적인 패턴이다.

핵심 포인트:
- `GetSecretValue`, `DescribeSecret`은 특정 ARN 패턴으로 제한 가능
- `ListSecrets`는 리소스 수준 제어가 불가능해서 `Resource: "*"` 필수
- `DescribeSecret`은 시크릿 값은 반환하지 않지만 태그, 로테이션 설정 등 메타데이터를 노출한다. 민감한 메타데이터가 있다면 별도로 제한해야 한다

```bash
# 성공 기대
aws secretsmanager get-secret-value --secret-id "prod/db/mysql" --profile test-user

# AccessDenied 기대
aws secretsmanager get-secret-value --secret-id "dev/db/mysql" --profile test-user
```

---

### Case 02 — 삭제 차단 + 즉시 삭제 방지 + 복구 기간 강제

**파일**: `policies/case02-deny-delete-force.json`

시크릿 삭제를 완전히 차단하거나, 삭제 시 최소 복구 기간을 강제한다.

핵심 포인트:
- `ForceDeleteWithoutRecovery: "true"` 조건으로 즉시 삭제만 차단 가능
- `NumericLessThan: { "secretsmanager:RecoveryWindowInDays": "7" }`로 7일 미만 복구 기간 차단
- 전면 Deny(`DenyDeleteSecret`)와 조건부 Deny를 함께 쓰면 모든 삭제가 차단된다. 의도에 맞게 선택해야 한다

함정: 삭제만 차단해도 `UpdateSecret`으로 시크릿 값을 덮어쓸 수 있다. 값 변경도 막으려면 Case 08을 함께 적용해야 한다.

---

### Case 03 — PrincipalTag vs ResourceTag 동적 ABAC

**파일**: `policies/case03-abac-principaltag.json`

IAM 사용자의 `Project` 태그와 시크릿의 `Project` 태그가 일치할 때만 접근을 허용한다. 하나의 정책으로 여러 팀을 동시에 관리할 수 있다.

핵심 포인트:
- `"aws:ResourceTag/Project": "${aws:PrincipalTag/Project}"` 로 태그 값을 동적으로 비교
- `Null: { "aws:PrincipalTag/Project": "true" }` Deny로 태그 없는 사용자를 전면 차단해야 한다. 이 Deny가 없으면 태그 없는 사용자가 태그 없는 시크릿에 접근할 수 있다
- `ListSecrets`는 태그 필터링이 불가능해서 모든 시크릿 이름이 노출된다. 값은 노출되지 않는다

```bash
# IAM 사용자에 태그 설정
aws iam tag-user --user-name dev-user --tags Key=Project,Value=backend

# 시크릿에 태그 설정
aws secretsmanager tag-resource \
  --secret-id "prod/backend/api-key" \
  --tags Key=Project,Value=backend
```

---

### Case 04 — CMK 강제 + AWS Managed Key 차단

**파일**: `policies/case04-enforce-cmk.json`

시크릿 생성/업데이트 시 반드시 고객 관리형 KMS 키(CMK)를 사용하도록 강제한다.

핵심 포인트:
- `StringLikeIfExists`로 `aws/secretsmanager` alias ARN 패턴을 차단
- `Null: { "secretsmanager:KmsKeyArn": "true" }` Deny로 KMS 키 미지정 케이스도 차단해야 한다. 이게 없으면 KMS 키를 아예 지정하지 않고 기본 키로 생성할 수 있다
- CMK의 Key Policy에도 해당 사용자/역할의 `kms:GenerateDataKey*`, `kms:Decrypt` 권한이 있어야 한다

크로스 계정 공유 시 필수: `aws/secretsmanager`는 크로스 계정 Key Policy 수정이 불가능하다. 크로스 계정 공유가 필요한 시크릿은 반드시 CMK를 써야 한다.

---

### Case 05 — AWSCURRENT 버전만 조회 허용

**파일**: `policies/case05-version-stage-current-only.json`

`GetSecretValue` 호출 시 현재 활성 버전(`AWSCURRENT`)만 조회 가능하도록 제한한다.

핵심 포인트:
- `secretsmanager:VersionStage: "AWSCURRENT"` Allow로 현재 버전만 허용
- `AWSPREVIOUS` Deny로 이전 버전 접근 차단
- `AWSPENDING`은 로테이션 중간 단계 버전이다. 이 정책을 로테이션 Lambda 역할에 적용하면 로테이션이 실패한다

주의: `--version-id`로 특정 버전 ID를 직접 지정하면 `VersionStage` 조건이 적용되지 않을 수 있다. 실제 환경에서 테스트가 필요하다.

---

### Case 06 — Resource Policy: VPC Endpoint 강제

**파일**: `policies/case06-resource-policy-vpce.json`

시크릿에 Resource Policy를 붙여 VPC Endpoint 경유 요청만 허용한다. 인터넷 경유 접근을 차단한다.

핵심 포인트:
- `Principal: "*"` + `StringNotEquals: { "aws:sourceVpce": "vpce-XXXXXXXXX" }` Deny 조합
- Resource Policy이므로 `Principal` 필드가 필수다
- 같은 계정 내에서도 Resource Policy의 Deny는 IAM Allow로 우회할 수 없다

적용 전 확인사항: VPC Endpoint가 없는 환경에서 이 정책을 적용하면 모든 접근이 차단된다. 적용 전에 반드시 VPC Endpoint 존재 여부를 확인해야 한다.

```bash
# VPC Endpoint 확인
aws ec2 describe-vpc-endpoints \
  --filters "Name=service-name,Values=com.amazonaws.ap-northeast-2.secretsmanager"
```

---

### Case 07 — 로테이션 Lambda 실행 역할 정책

**파일**: `policies/case07-rotation-lambda-permissions.json`

시크릿 로테이션 Lambda의 실행 역할에 필요한 최소 권한 정책이다.

핵심 포인트:
- `UpdateSecretVersionStage`가 반드시 필요하다. 이게 없으면 `finishSecret` 단계에서 실패한다
- `GetRandomPassword`는 `Resource: "*"` 필수다. 리소스 수준 제어가 불가능하다
- VPC 내 Lambda는 EC2 네트워크 인터페이스 권한도 필요하다

```bash
aws secretsmanager rotate-secret \
  --secret-id "prod/db/mysql" \
  --rotation-lambda-arn "arn:aws:lambda:REGION:ACCOUNT_ID:function:MyRotationFunction" \
  --rotation-rules AutomaticallyAfterDays=30
```

---

### Case 08 — 시크릿 값 변경 차단

**파일**: `policies/case08-deny-update-secret.json`

읽기는 허용하되 시크릿 값 변경을 완전히 차단한다. 감사(audit) 역할이나 읽기 전용 서비스 계정에 적합하다.

차단 대상 액션:
- `PutSecretValue` - 새 버전으로 값 저장
- `UpdateSecret` - 시크릿 메타데이터 및 값 업데이트
- `UpdateSecretVersionStage` - 버전 스테이지 변경

Case 02와의 조합: 삭제 차단(Case 02) + 값 변경 차단(Case 08)을 함께 적용하면 완전한 읽기 전용 정책이 된다.

---

### Case 09 — 크로스 계정 Resource Policy

**파일**: `policies/case09-cross-account-resource-policy.json`

크로스 계정 시크릿 공유를 위한 Resource Policy다. 신뢰하는 계정의 접근만 허용하고 나머지는 차단한다.

핵심 포인트:
- `aws:PrincipalAccount` 조건으로 허용된 계정 목록 외 모든 접근 차단
- CMK ARN 조건으로 올바른 키로 암호화된 시크릿만 접근 허용
- 이 정책은 시크릿에 직접 붙이는 Resource Policy다. IAM 정책이 아니다

3단계 설정 순서:
1. 소유 계정: 시크릿에 이 Resource Policy 적용
2. 소유 계정: CMK Key Policy에 상대 계정 허용 추가
3. 상대 계정: 역할/사용자 IAM 정책에 소유 계정 시크릿 ARN 추가

---

### Case 10 — 시크릿 이름 패턴 제한

**파일**: `policies/case10-name-pattern-restriction.json`

시크릿 생성 시 이름이 `prod/` prefix를 따르도록 강제한다. 네이밍 컨벤션을 정책으로 강제하는 패턴이다.

핵심 포인트:
- `secretsmanager:Name` 조건 키는 `CreateSecret` 액션에만 적용된다
- `StringLike: { "secretsmanager:Name": "prod/*" }` Allow + `StringNotLike` Deny 조합
- 이미 생성된 시크릿의 이름은 변경할 수 없다. 이 정책은 신규 생성에만 효과가 있다

```bash
# 성공 기대
aws secretsmanager create-secret \
  --name "prod/new-service/api-key" \
  --secret-string "my-secret-value"

# AccessDenied 기대
aws secretsmanager create-secret \
  --name "dev/new-service/api-key" \
  --secret-string "my-secret-value"
```

---

### Case 11 — 공개 정책 차단

**파일**: `policies/case11-block-public-policy.json`

`PutResourcePolicy` 호출 시 `--block-public-policy` 플래그를 강제한다. 실수로 시크릿을 공개 접근 가능하게 만드는 것을 방지한다.

핵심 포인트:
- `secretsmanager:BlockPublicPolicy: "false"` 조건으로 공개 정책 차단
- `--block-public-policy` 없이 `put-resource-policy`를 호출하면 Deny된다
- AWS 콘솔에서 Resource Policy 설정 시에도 이 조건이 적용된다

```bash
# 올바른 방법 (--block-public-policy 포함)
aws secretsmanager put-resource-policy \
  --secret-id "prod/db/mysql" \
  --resource-policy file://policy.json \
  --block-public-policy

# 이 방법은 Deny됨 (--block-public-policy 없음)
aws secretsmanager put-resource-policy \
  --secret-id "prod/db/mysql" \
  --resource-policy file://policy.json
```

---

### Case 12 — RDS 관리형 시크릿 접근

**파일**: `policies/case12-rds-managed-secret.json`

RDS가 자동으로 생성하고 관리하는 시크릿에 대한 접근 정책이다. RDS 관리형 시크릿은 ARN에 `rds!` prefix가 붙는다.

핵심 포인트:
- RDS 관리형 시크릿 ARN 패턴: `arn:aws:secretsmanager:REGION:ACCOUNT_ID:secret:rds!*`
- RDS가 직접 관리하므로 `PutSecretValue`, `UpdateSecret`, `RotateSecret`을 사용자가 직접 호출하면 안 된다. Deny로 차단한다
- CMK 사용 시 `kms:Decrypt`, `kms:DescribeKey` 권한이 필요하다

```bash
aws rds modify-db-instance \
  --db-instance-identifier my-db \
  --manage-master-user-password \
  --master-user-secret-kms-key-id "arn:aws:kms:REGION:ACCOUNT_ID:key/CMK_KEY_ID"
```

---

## 전용 Condition Key 빠른 참조

| Condition Key | 적용 Action | 사용 예시 |
|---|---|---|
| `secretsmanager:Name` | `CreateSecret` | 이름 패턴 강제 |
| `secretsmanager:VersionStage` | `GetSecretValue` | AWSCURRENT만 허용 |
| `secretsmanager:ResourceTag/${TagKey}` | 대부분 | ABAC 태그 매칭 |
| `secretsmanager:ForceDeleteWithoutRecovery` | `DeleteSecret` | 즉시 삭제 차단 |
| `secretsmanager:RecoveryWindowInDays` | `DeleteSecret` | 복구 기간 최소값 강제 |
| `secretsmanager:KmsKeyArn` | `CreateSecret`, `UpdateSecret` | CMK 강제 |
| `secretsmanager:RotationLambdaARN` | `RotateSecret` | 특정 Lambda만 허용 |
| `secretsmanager:BlockPublicPolicy` | `PutResourcePolicy` | 공개 정책 차단 |

---

## 감점 방지 포인트 총정리

1. Secret ARN suffix: `??????` 6자리 와일드카드 vs `*` 차이를 반드시 이해하고 상황에 맞게 선택
2. 크로스 계정 = CMK 필수: `aws/secretsmanager` managed key는 크로스 계정 Key Policy 수정 불가
3. 로테이션 Lambda = AWSPENDING 필수: `VersionStage` 조건으로 과도하게 제한하면 로테이션 실패
4. Resource Policy + IAM Policy 이중 구조: 같은 계정은 합집합, 크로스 계정은 교집합
5. ForceDeleteWithoutRecovery 별도 차단: 일반 DeleteSecret Deny만으로는 즉시 삭제를 막지 못한다
6. DescribeSecret 메타데이터 노출: GetSecretValue만 차단해도 DescribeSecret으로 태그, 로테이션 설정이 노출된다
7. ListSecrets는 Resource: "*" 필수: 특정 ARN 지정 불가
8. VPC Lambda ENI 권한: VPC 내 로테이션 Lambda는 ec2:CreateNetworkInterface 등 추가 권한 필요
9. ABAC Null 조건 필수: 태그 없는 주체를 막으려면 Deny + Null 조건을 반드시 추가
10. RDS 관리형 시크릿 ARN: `rds!` prefix 패턴으로 일반 시크릿과 구분

---

## CloudShell 검증 루틴

```bash
export AWS_REGION="ap-northeast-2"
export ACCOUNT_ID="123456789012"
export SECRET_NAME="prod/db/mysql"
export USER_NAME="mod3-sm-user"
export PROFILE_NAME="mod3-sm-user"

# 사용자 생성 및 정책 연결
aws iam create-user --user-name "$USER_NAME"
aws iam create-policy \
  --policy-name "SM-Test-Policy" \
  --policy-document file://policies/case01-path-prefix-readonly.json
aws iam attach-user-policy \
  --user-name "$USER_NAME" \
  --policy-arn "arn:aws:iam::$ACCOUNT_ID:policy/SM-Test-Policy"

# 액세스 키 발급
aws iam create-access-key --user-name "$USER_NAME"
aws configure --profile "$PROFILE_NAME"

# 신분 확인
aws sts get-caller-identity --profile "$PROFILE_NAME"

# 허용 검증
aws secretsmanager get-secret-value \
  --secret-id "$SECRET_NAME" \
  --profile "$PROFILE_NAME"

# 차단 검증
aws secretsmanager get-secret-value \
  --secret-id "dev/db/mysql" \
  --profile "$PROFILE_NAME"

# 삭제 시도 차단 검증
aws secretsmanager delete-secret \
  --secret-id "$SECRET_NAME" \
  --force-delete-without-recovery \
  --profile "$PROFILE_NAME"
```
