# Module 3 Cheatsheet — Fine-grained IAM

## 1) 정책 평가 우선순위 (암기용)

1. 인증 성공(Principal 식별)
2. 명시적 Deny 탐색
3. Identity-based + Resource-based Allow 합집합 계산
4. Permissions Boundary / SCP / Session Policy 교집합 적용
5. 최종 Allow 아니면 Implicit Deny

---

## 2) 자주 쓰는 Condition Key / Operator

| 분류 | 키/연산자 | 실전 용도 |
|---|---|---|
| 전송 보안 | `aws:SecureTransport` + `Bool` | HTTP 차단 (TLS 강제) |
| 주체 태그 | `aws:PrincipalTag/KEY` + `StringEquals` | ABAC 분기 |
| 리소스 태그 | `aws:ResourceTag/KEY` + `StringEquals` | 리소스 라벨 기반 통제 |
| 시간 | `aws:CurrentTime` + `DateGreaterThan/DateLessThan` | 기간 제한 |
| CIDR | `aws:SourceIp` + `IpAddress/NotIpAddress` | 원천 IP 제한 |
| Null 체크 | `Null` | 컨텍스트 키 누락 차단 |
| 다중 값 | `ForAnyValue` / `ForAllValues` | 배열형 컨텍스트 검증 |

---

## 3) ABAC 패턴 (복붙 템플릿)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyIfTeamTagMissing",
      "Effect": "Deny",
      "Action": "s3:*",
      "Resource": "*",
      "Condition": {
        "Null": {
          "aws:PrincipalTag/Team": "true"
        }
      }
    },
    {
      "Sid": "AllowTeamHomePrefixOnly",
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket"
      ],
      "Resource": "arn:aws:s3:::DATA_BUCKET",
      "Condition": {
        "StringLike": {
          "s3:prefix": "home/${aws:PrincipalTag/Team}/*"
        }
      }
    },
    {
      "Sid": "AllowTeamObjects",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject"
      ],
      "Resource": "arn:aws:s3:::DATA_BUCKET/home/${aws:PrincipalTag/Team}/*"
    }
  ]
}
```

> `DATA_BUCKET`은 실제 버킷명으로 치환.

---

## 4) CloudShell 검증 루틴 (5분)

```bash
export AWS_REGION="ap-northeast-2"
export ACCOUNT_ID="123456789012"
export DATA_BUCKET="YOUR_DATA_BUCKET"
export USER_NAME="mod3-test-user"
export PROFILE_NAME="mod3-test-user"
```

### (1) 현재 신분 확인

```bash
aws sts get-caller-identity
```

### (2) 사용자 키 발급 후 프로파일 전환

```bash
aws iam create-access-key --user-name "$USER_NAME"
aws configure --profile "$PROFILE_NAME"
aws sts get-caller-identity --profile "$PROFILE_NAME"
```

### (3) Allow / Deny 동시 확인

```bash
# Allow 기대
aws s3 ls "s3://$DATA_BUCKET/home/analytics/" --profile "$PROFILE_NAME"

# Deny 기대
aws s3 ls "s3://$DATA_BUCKET/home/finance/" --profile "$PROFILE_NAME"
```

### (4) 정책 시뮬레이터

```bash
aws iam get-context-keys-for-principal-policy \
  --policy-source-arn "arn:aws:iam::$ACCOUNT_ID:user/$USER_NAME"

aws iam simulate-principal-policy \
  --policy-source-arn "arn:aws:iam::$ACCOUNT_ID:user/$USER_NAME" \
  --action-names s3:ListBucket s3:GetObject s3:DeleteObject \
  --resource-arns "arn:aws:s3:::$DATA_BUCKET" "arn:aws:s3:::$DATA_BUCKET/home/analytics/sample.txt"
```

---

## 5) 자주 터지는 실수

- `ListBucket`은 **버킷 ARN**(`arn:aws:s3:::BUCKET`)에 붙여야 함.
- `GetObject/PutObject/DeleteObject`는 **오브젝트 ARN**(`arn:aws:s3:::BUCKET/*`)에 붙여야 함.
- ABAC에 `${aws:PrincipalTag/...}` 넣고 사용자 태그를 안 달면 전부 Deny/ImplicitDeny 발생.
- `aws:SecureTransport` 강제 Deny 넣고 HTTP 엔드포인트 쓰면 무조건 실패.
- `iam:PassRole` 통제를 `ResourceTag`로만 설계하면 의도대로 안 막힐 수 있음(공식 문서 주의사항 확인).


---

## 6) IAM 위임 관리 (Delegated IAM) 핵심 조건 키

### iam:* 전용 조건 키 완전 정리

| 조건 키 | 연산자 | 용도 |
|---|---|---|
| `iam:PermissionsBoundary` | `ArnEquals` / `StringEquals` | CreateRole/CreateUser 시 Boundary 강제 |
| `iam:PassedToService` | `StringEquals` | PassRole 대상 서비스 제한 (e.g. `ec2.amazonaws.com`) |
| `iam:AssociatedResourceArn` | `ArnLike` | PassRole 시 연결될 리소스 ARN 제한 |
| `iam:PolicyARN` | `ArnEquals` / `ArnLike` | Attach/Detach 가능한 정책 ARN 제한 |
| `iam:ResourceTag/KEY` | `StringEquals` | IAM User/Role 태그 기반 접근 제어 |
| `iam:OrganizationsPolicyId` | `StringEquals` | Organizations 정책 ID 검증 |
| `iam:AWSServiceName` | `StringLike` | CreateServiceLinkedRole 서비스 제한 |

### 글로벌 조건 키 (IAM 위임에서 자주 쓰임)

| 조건 키 | 용도 |
|---|---|
| `aws:PrincipalArn` | 특정 관리자 ARN 제외 (NotResource 대신 사용) |
| `aws:PrincipalOrgID` | Organizations 전체 계정 허용 |
| `aws:MultiFactorAuthPresent` | MFA 인증 여부 강제 |
| `aws:MultiFactorAuthAge` | MFA 인증 후 경과 시간(초) 제한 |
| `aws:RequestedRegion` | 특정 리전만 허용 |

---

## 7) IAM ARN 패턴 레퍼런스

```
# 사용자
arn:aws:iam::ACCOUNT_ID:user/USERNAME
arn:aws:iam::ACCOUNT_ID:user/PATH/USERNAME

# 역할
arn:aws:iam::ACCOUNT_ID:role/ROLENAME
arn:aws:iam::ACCOUNT_ID:role/PATH/ROLENAME

# 정책
arn:aws:iam::ACCOUNT_ID:policy/POLICYNAME
arn:aws:iam::ACCOUNT_ID:policy/PATH/POLICYNAME
arn:aws:iam::aws:policy/MANAGED_POLICY_NAME   ← AWS 관리형

# 인스턴스 프로파일
arn:aws:iam::ACCOUNT_ID:instance-profile/PROFILE_NAME

# MFA 디바이스
arn:aws:iam::ACCOUNT_ID:mfa/DEVICE_NAME

# STS 세션 (assumed-role)
arn:aws:sts::ACCOUNT_ID:assumed-role/ROLE_NAME/SESSION_NAME

# 서비스 연결 역할
arn:aws:iam::ACCOUNT_ID:role/aws-service-role/SERVICE.amazonaws.com/ROLE_NAME
```

---

## 8) Permissions Boundary 핵심 함정 (시험 출제 포인트)

| 함정 | 설명 |
|---|---|
| **Boundary ≠ 권한 부여** | Boundary만 붙이면 아무것도 못 함. Identity Policy도 필요 |
| **Resource-based policy 우회** | 같은 계정 내 Resource-based policy는 Boundary의 implicit deny를 우회함 (단, IAM Role ARN 대상은 제한됨) |
| **Boundary 없이 CreateRole = 권한 상승** | Boundary 조건 없이 CreateRole 허용 시 공격자가 AdministratorAccess 역할 생성 가능 |
| **Boundary 삭제 차단 필수** | `iam:DeleteRolePermissionsBoundary` / `iam:DeleteUserPermissionsBoundary` Deny 필수 |
| **Boundary 정책 수정 차단 필수** | `iam:CreatePolicyVersion`, `iam:DeletePolicyVersion`, `iam:SetDefaultPolicyVersion` Deny 필수 |
| **Role Chaining 1시간 제한** | AssumeRole로 얻은 임시 자격증명으로 다시 AssumeRole 시 최대 1시간 (MaxSessionDuration 무시) |
| **PutRolePolicy = 인라인 정책 = 상승 가능** | Boundary 없이 PutRolePolicy 허용 시 기존 역할에 AdministratorAccess 인라인 추가 가능 |

---

## 9) 권한 상승(Privilege Escalation) 21가지 벡터 요약

> 아래 권한 중 하나라도 과도하게 부여하면 전체 계정 탈취 가능.

**정책 직접 조작:**
- `iam:CreatePolicyVersion` + `--set-as-default` → 기존 정책을 AdministratorAccess로 교체
- `iam:SetDefaultPolicyVersion` → 비활성 버전 중 고권한 버전으로 전환

**정책 부착:**
- `iam:AttachUserPolicy` / `iam:AttachGroupPolicy` / `iam:AttachRolePolicy` → AdministratorAccess 부착
- `iam:PutUserPolicy` / `iam:PutGroupPolicy` / `iam:PutRolePolicy` → 인라인 정책으로 전체 허용

**자격증명 탈취:**
- `iam:CreateAccessKey` (타 사용자 대상) → 고권한 사용자 키 발급
- `iam:CreateLoginProfile` / `iam:UpdateLoginProfile` → 콘솔 비밀번호 설정/변경

**그룹/역할 조작:**
- `iam:AddUserToGroup` → 고권한 그룹에 자신 추가
- `iam:UpdateAssumeRolePolicy` + `sts:AssumeRole` → 신뢰 정책 수정 후 고권한 역할 가정

**PassRole 악용 (서비스 통해 간접 실행):**
- `iam:PassRole` + `ec2:RunInstances` → EC2 인스턴스 메타데이터로 역할 자격증명 획득
- `iam:PassRole` + `lambda:CreateFunction` + `lambda:InvokeFunction` → Lambda로 고권한 작업 실행
- `iam:PassRole` + `glue:CreateDevEndpoint` → Glue 엔드포인트 SSH로 역할 자격증명 획득
- `iam:PassRole` + `cloudformation:CreateStack` → CloudFormation으로 고권한 리소스 생성
- `iam:PassRole` + `datapipeline:CreatePipeline` + `datapipeline:PutPipelineDefinition` → 파이프라인으로 임의 명령 실행

---

## 10) 위임 관리 설계 체크리스트

```
[ ] Boundary 정책 생성 (최대 허용 범위 정의)
[ ] CreateRole/CreateUser에 iam:PermissionsBoundary 조건 추가
[ ] PutRolePolicy/AttachRolePolicy에도 Boundary 조건 추가 (인라인 우회 차단)
[ ] DeleteRolePermissionsBoundary Deny 추가
[ ] Boundary 정책 자체 수정 Deny (CreatePolicyVersion, SetDefaultPolicyVersion)
[ ] PassRole을 iam:PassedToService로 서비스 제한
[ ] PassRole Resource를 ARN 패턴으로 좁히기 (role/PATH/*)
[ ] 관리자 자신의 ARN을 NotResource 또는 Condition으로 보호
[ ] 고권한 AWS 관리형 정책(AdministratorAccess, PowerUserAccess) 부착 Deny
```
