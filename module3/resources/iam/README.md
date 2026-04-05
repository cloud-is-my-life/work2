# IAM (Delegated Administration) Fine-grained 실전 케이스

## 핵심 요약

> **⚠️ Permissions Boundary 없이 CreateRole/CreateUser 허용 = 권한 상승** — 위임 관리자가 자기보다 높은 권한의 역할을 만들 수 있음. 반드시 Boundary 강제.

> **⚠️ Boundary는 Identity-based Policy와 교집합** — Boundary에 없는 권한은 Identity Policy에서 Allow해도 거부됨.

> **⚠️ Boundary는 Resource-based Policy를 제한하지 않음** — S3 버킷 정책 등에서 직접 허용하면 Boundary 우회 가능 (시험 함정).

> **⚠️ `iam:PassRole`은 가장 위험한 Action** — 고권한 Role을 서비스에 전달하면 간접 권한 상승. Resource ARN + `iam:PassedToService` 조건 필수.

> **⚠️ 자기 자신의 Boundary 제거 차단 필수** — `iam:DeleteUserPermissionsBoundary`, `iam:DeleteRolePermissionsBoundary` Deny 누락 시 Boundary 우회.

---

## 전용 Condition Key

| Condition Key | 타입 | 설명 | 주요 사용처 |
|---|---|---|---|
| `iam:PermissionsBoundary` | ARN | 생성되는 User/Role에 연결할 Boundary 정책 ARN | CreateUser, CreateRole, PutUserPermissionsBoundary |
| `iam:PassedToService` | String | PassRole 대상 서비스 | PassRole |
| `iam:OrganizationsPolicyId` | String | SCP 정책 ID | Organizations 관련 |
| `iam:PolicyARN` | ARN | 연결하려는 정책 ARN | AttachUserPolicy, AttachRolePolicy |
| `iam:ResourceTag/KEY` | String | 대상 IAM 리소스의 태그 | 태그 기반 제어 |
| `iam:AWSServiceName` | String | 서비스 연결 역할 대상 서비스 | CreateServiceLinkedRole |

### 글로벌 Condition Key (IAM에서 자주 사용)

| Condition Key | 설명 |
|---|---|
| `aws:PrincipalTag/KEY` | 호출자 태그 기반 ABAC |
| `aws:RequestTag/KEY` | 생성 시 태그 강제 |
| `aws:TagKeys` | 허용 태그 키 제한 |
| `aws:PrincipalOrgID` | Organization 내부만 허용 |

---

## ARN 패턴

```
# 사용자
arn:aws:iam::ACCOUNT_ID:user/PATH/USER_NAME

# 역할
arn:aws:iam::ACCOUNT_ID:role/PATH/ROLE_NAME

# 정책 (관리형)
arn:aws:iam::ACCOUNT_ID:policy/PATH/POLICY_NAME

# AWS 관리형 정책
arn:aws:iam::aws:policy/POLICY_NAME

# 인스턴스 프로파일
arn:aws:iam::ACCOUNT_ID:instance-profile/PROFILE_NAME

# 경로 기반 와일드카드
arn:aws:iam::ACCOUNT_ID:user/dev-team/*
arn:aws:iam::ACCOUNT_ID:role/app-roles/*
```

---

## 위임 관리 핵심 Action 분리

| 역할 | 필수 Actions |
|---|---|
| 위임 관리자 (User 생성) | `iam:CreateUser`, `iam:DeleteUser`, `iam:PutUserPermissionsBoundary`, `iam:AttachUserPolicy`, `iam:CreateAccessKey` |
| 위임 관리자 (Role 생성) | `iam:CreateRole`, `iam:DeleteRole`, `iam:PutRolePermissionsBoundary`, `iam:AttachRolePolicy`, `iam:PassRole` |
| 자기 관리 (Self-Service) | `iam:ChangePassword`, `iam:CreateAccessKey` (자기 자신), `iam:EnableMFADevice`, `iam:ListMFADevices` |
| 조회 전용 | `iam:GetUser`, `iam:GetRole`, `iam:GetPolicy`, `iam:ListUsers`, `iam:ListRoles`, `iam:ListPolicies` |
| 정책 관리 | `iam:CreatePolicy`, `iam:CreatePolicyVersion`, `iam:DeletePolicy`, `iam:SetDefaultPolicyVersion` |

---

## 정책 파일

| 케이스 | 파일 | 의도 |
|---|---|---|
| Case 01 | `policies/case01-delegated-create-role-with-boundary.json` | Role 생성 시 Boundary 강제 |
| Case 02 | `policies/case02-delegated-create-user-with-boundary.json` | User 생성 시 Boundary 강제 |
| Case 03 | `policies/case03-self-manage-password-mfa.json` | 자기 비밀번호/MFA만 관리 |
| Case 04 | `policies/case04-path-based-delegation.json` | 경로 기반 위임 (특정 경로 하위만 관리) |
| Case 05 | `policies/case05-deny-privilege-escalation.json` | 권한 상승 차단 (Boundary 제거, 고권한 정책 연결 금지) |
| Case 06 | `policies/case06-passrole-scoped.json` | PassRole을 특정 서비스·역할로만 제한 |
| Case 07 | `policies/case07-deny-attach-admin-policy.json` | AdministratorAccess 등 고권한 정책 연결 차단 |

---

## CloudShell 준비

```bash
export AWS_REGION="ap-northeast-2"
export ACCOUNT_ID="123456789012"
export BOUNDARY_POLICY_ARN="arn:aws:iam::$ACCOUNT_ID:policy/DeveloperBoundary"
export DELEGATED_ADMIN="mod3-iam-admin"
export PROFILE_NAME="mod3-iam-admin"
```

---

## 검증 예시

```bash
# 1) Boundary 포함 Role 생성 — 성공
aws iam create-role \
  --role-name "test-app-role" \
  --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}' \
  --permissions-boundary "$BOUNDARY_POLICY_ARN" \
  --profile "$PROFILE_NAME"

# 2) Boundary 없이 Role 생성 — AccessDenied
aws iam create-role \
  --role-name "test-no-boundary" \
  --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}' \
  --profile "$PROFILE_NAME"

# 3) Boundary 제거 시도 — AccessDenied
aws iam delete-role-permissions-boundary \
  --role-name "test-app-role" \
  --profile "$PROFILE_NAME"

# 4) AdministratorAccess 연결 시도 — AccessDenied
aws iam attach-role-policy \
  --role-name "test-app-role" \
  --policy-arn "arn:aws:iam::aws:policy/AdministratorAccess" \
  --profile "$PROFILE_NAME"

# 5) 시뮬레이터
aws iam simulate-principal-policy \
  --policy-source-arn "arn:aws:iam::$ACCOUNT_ID:user/$DELEGATED_ADMIN" \
  --action-names iam:CreateRole iam:DeleteRolePermissionsBoundary iam:AttachRolePolicy \
  --resource-arns "arn:aws:iam::$ACCOUNT_ID:role/test-app-role"
```

---

## 권한 상승 경로 (시험 함정)

| 경로 | 설명 | 차단 방법 |
|---|---|---|
| Boundary 제거 | 자기 또는 생성한 역할의 Boundary 삭제 | `Deny` DeleteUser/RolePermissionsBoundary |
| 고권한 정책 연결 | AdministratorAccess 등 직접 연결 | `Deny` AttachRolePolicy + `iam:PolicyARN` 조건 |
| PassRole 남용 | 고권한 Role을 Lambda/EC2에 전달 | PassRole Resource를 특정 Role ARN으로 제한 |
| 새 정책 생성 | `iam:CreatePolicy`로 `*:*` 정책 생성 후 연결 | CreatePolicy 자체를 Deny하거나 Boundary로 제한 |
| Boundary 변경 | 더 넓은 Boundary로 교체 | `Deny` PutUser/RolePermissionsBoundary + `iam:PermissionsBoundary` 조건 |

---

## 감점 방지 포인트

- `iam:CreateRole`에 `iam:PermissionsBoundary` 조건 누락 = 권한 상승 허용 → 감점
- Boundary 제거 Deny를 빠뜨리면 생성 후 Boundary 삭제로 우회 가능
- `iam:PassRole`의 Resource는 **전달 대상 Role ARN**이지 호출자 ARN이 아님
- `iam:PolicyARN` 조건으로 연결 가능한 정책을 제한할 때, AWS 관리형 정책은 `arn:aws:iam::aws:policy/*` 패턴
- 경로 기반 위임 시 `arn:aws:iam::ACCOUNT_ID:user/dev-team/*`처럼 경로를 포함해야 함 — 경로 없는 사용자는 매칭 안 됨
- `iam:ListUsers`, `iam:ListRoles`는 `Resource: "*"` 필수
- Permissions Boundary는 STS AssumeRole로 얻은 임시 자격증명에도 적용됨
