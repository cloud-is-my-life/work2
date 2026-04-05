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

## 케이스별 상세 설명

### Case 01 — Role 생성 시 Boundary 강제

**시나리오**: 위임 관리자가 `app-roles/` 경로 하위에 Role을 생성할 수 있지만, 반드시 `DeveloperBoundary` Permissions Boundary를 연결해야 함.

**핵심 메커니즘**:
- Allow: `iam:CreateRole` + `iam:PermissionsBoundary: "arn:aws:iam::ACCOUNT:policy/DeveloperBoundary"` → Resource `arn:aws:iam::ACCOUNT:role/app-roles/*`
- Allow: Role 관리 Action (AttachRolePolicy, PutRolePolicy 등) → 같은 경로
- Deny: `iam:DeleteRolePermissionsBoundary`, `iam:PutRolePermissionsBoundary` → Boundary 제거/변경 차단

**허용**: Boundary 포함 Role 생성, 생성된 Role에 정책 연결
**거부**: Boundary 없이 Role 생성, Boundary 제거/변경

**주의사항**:
- `iam:PermissionsBoundary` 조건 누락 = 권한 상승 허용 → **가장 빈출 감점 포인트**
- Boundary 제거 Deny를 빠뜨리면 생성 후 `DeleteRolePermissionsBoundary`로 Boundary 삭제 가능 → 우회
- `PutRolePermissionsBoundary`도 Deny해야 더 넓은 Boundary로 교체 방지
- 생성된 Role에 연결 가능한 정책도 제한하려면 Case 07과 병행

---

### Case 02 — User 생성 시 Boundary 강제

**시나리오**: 위임 관리자가 `dev-team/` 경로 하위에 User를 생성할 수 있지만, 반드시 Boundary 연결 필수.

**핵심 메커니즘**:
- Allow: `iam:CreateUser` + `iam:PermissionsBoundary` 조건 → Resource `arn:aws:iam::ACCOUNT:user/dev-team/*`
- Allow: User 관리 Action (AttachUserPolicy, CreateAccessKey, CreateLoginProfile 등)
- Deny: `iam:DeleteUserPermissionsBoundary`, `iam:PutUserPermissionsBoundary`

**허용**: Boundary 포함 User 생성, 액세스 키 발급, 정책 연결
**거부**: Boundary 없이 User 생성, Boundary 제거/변경

**주의사항**:
- Case 01과 동일한 Boundary 강제 패턴이지만 대상이 User
- `CreateLoginProfile`(콘솔 로그인), `CreateAccessKey`(프로그래밍 접근) 권한도 경로 범위 내로 제한
- `ListUsers`는 `Resource: "*"` 필수 — 경로 기반 제어 불가
- 생성된 User가 자기 Boundary를 제거하지 못하도록 Boundary 정책 자체에도 Deny 포함 권장

---

### Case 03 — 자기 비밀번호/MFA만 관리

**시나리오**: IAM 사용자가 자기 자신의 비밀번호 변경, 액세스 키 관리, MFA 설정만 가능. 다른 사용자 관리 불가.

**핵심 메커니즘**:
- Resource: `arn:aws:iam::ACCOUNT:user/${aws:username}` — 정책 변수로 자기 자신만 대상
- Allow: `iam:ChangePassword`, `iam:CreateAccessKey`, `iam:DeleteAccessKey`, `iam:EnableMFADevice`, `iam:CreateVirtualMFADevice` 등
- MFA Resource: `arn:aws:iam::ACCOUNT:mfa/${aws:username}`

**허용**: 자기 비밀번호 변경, 자기 액세스 키 관리, 자기 MFA 설정
**거부**: 다른 사용자의 비밀번호/키/MFA 관리

**주의사항**:
- `${aws:username}` 정책 변수는 IAM 사용자에만 동작 — Role(AssumeRole)에서는 빈 문자열
- MFA 디바이스 ARN은 `mfa/${aws:username}` — User ARN과 다른 리소스 타입
- `iam:GetAccountPasswordPolicy`, `iam:GetAccountSummary`는 `Resource: "*"` 필수 — 계정 수준 정보
- MFA 없이 민감 작업 차단하려면 `aws:MultiFactorAuthPresent` 조건 추가 (Deny + `BoolIfExists: "false"`)

---

### Case 04 — 경로 기반 위임 (특정 경로 하위만 관리)

**시나리오**: 위임 관리자가 `dev-team/` 경로 하위의 User, Role, Policy만 관리 가능. 다른 경로는 접근 불가.

**핵심 메커니즘**:
- Allow: User 관리 → `arn:aws:iam::ACCOUNT:user/dev-team/*`
- Allow: Role 관리 → `arn:aws:iam::ACCOUNT:role/dev-team/*`
- Allow: Policy 관리 → `arn:aws:iam::ACCOUNT:policy/dev-team/*`
- Deny: `NotResource`로 경로 외 리소스에 대한 관리 Action 차단

**허용**: `dev-team/` 경로 하위 User/Role/Policy 전체 관리
**거부**: 다른 경로(`admin/`, `prod/` 등) 리소스 관리

**주의사항**:
- IAM 경로는 ARN에 포함됨 — `arn:aws:iam::ACCOUNT:user/dev-team/john` (경로 `/dev-team/`)
- 경로 없이 생성된 사용자(`arn:aws:iam::ACCOUNT:user/john`)는 매칭 안 됨
- `NotResource` 사용 시 의도치 않은 Deny 범위 확대 주의 — 다른 서비스 리소스도 매칭될 수 있음
- `ListUsers`, `ListRoles`, `ListPolicies`는 경로 필터링 불가 → `Resource: "*"` 별도 허용

---

### Case 05 — 권한 상승 차단 (종합)

**시나리오**: 위임 관리자의 모든 권한 상승 경로를 차단하는 종합 Deny 정책.

**핵심 메커니즘**:
- Deny: `iam:DeleteUserPermissionsBoundary`, `iam:DeleteRolePermissionsBoundary` → Boundary 제거 차단
- Deny: `iam:PutUserPermissionsBoundary`, `iam:PutRolePermissionsBoundary` + Boundary ≠ 지정 ARN → Boundary 변경 차단
- Deny: `iam:CreatePolicy`, `iam:CreatePolicyVersion` → 새 정책 생성 차단 (또는 Boundary로 제한)
- Deny: `iam:CreateUser`, `iam:CreateRole` + Boundary ≠ 지정 ARN → Boundary 없는 생성 차단
- Deny: `iam:PassRole` → 고권한 Role 전달 차단

**허용**: Boundary 포함 생성, 허용 범위 내 정책 연결
**거부**: 모든 권한 상승 경로

**주의사항**:
- 이 정책은 다른 Allow 정책과 **함께** 사용 — 단독으로는 아무것도 허용하지 않음
- 5가지 권한 상승 경로 모두 차단해야 완전 → 하나라도 빠지면 우회 가능
- `iam:CreatePolicy` Deny 시 위임 관리자가 커스텀 정책을 만들 수 없음 → 사전 생성된 정책만 연결 가능
- Boundary 정책 자체의 내용도 중요 — Boundary에 `iam:*` 포함되면 Boundary 의미 없음

---

### Case 06 — PassRole을 특정 서비스·역할로만 제한

**시나리오**: `iam:PassRole`을 Lambda, EC2, ECS 서비스에만, 그리고 `app-roles/` 경로 역할만 전달 가능.

**핵심 메커니즘**:
- Allow: `iam:PassRole` → Resource `arn:aws:iam::ACCOUNT:role/app-roles/*` + `iam:PassedToService` ∈ [`lambda.amazonaws.com`, `ec2.amazonaws.com`, `ecs-tasks.amazonaws.com`]
- Deny: `iam:PassRole` → `iam:PassedToService` ∈ [`iam.amazonaws.com`, `sts.amazonaws.com`] (IAM/STS에 전달 차단)
- Deny: `iam:PassRole` → 고권한 Role ARN 패턴

**허용**: `app-roles/` 경로 역할을 Lambda/EC2/ECS에 전달
**거부**: 고권한 역할 전달, IAM/STS 서비스에 전달

**주의사항**:
- `iam:PassedToService` 값은 서비스별 고정 — `lambda.amazonaws.com`, `ec2.amazonaws.com` 등
- PassRole의 Resource는 **전달 대상 Role ARN** — Lambda 함수 ARN이 아님
- IAM/STS에 PassRole 허용 시 Role chaining으로 권한 상승 가능 → 반드시 차단
- `iam:PassRole`은 `CreateFunction`, `RunInstances`, `CreateService` 등과 함께 호출됨 — 해당 Action 권한도 필요

---

### Case 07 — AdministratorAccess 등 고권한 정책 연결 차단

**시나리오**: `AttachRolePolicy`/`AttachUserPolicy` 시 AdministratorAccess, IAMFullAccess, PowerUserAccess 등 고권한 AWS 관리형 정책 연결 차단.

**핵심 메커니즘**:
- Allow: `iam:AttachRolePolicy`, `iam:DetachRolePolicy` → 특정 경로 리소스
- Deny: `iam:AttachRolePolicy`, `iam:AttachUserPolicy`, `iam:AttachGroupPolicy` + `iam:PolicyARN` ∈ [고권한 정책 ARN 목록]

**허용**: 비고권한 정책 연결 (ReadOnlyAccess, 커스텀 정책 등)
**거부**: AdministratorAccess, IAMFullAccess, PowerUserAccess 연결 → `AccessDenied`

**주의사항**:
- AWS 관리형 정책 ARN 형식: `arn:aws:iam::aws:policy/POLICY_NAME` — 계정 ID가 `aws`
- 커스텀 고권한 정책도 차단하려면 `arn:aws:iam::ACCOUNT:policy/FullAccess*` 패턴 추가
- `iam:PolicyARN` 조건은 `ArnEquals`/`ArnLike` 연산자 사용
- `PutRolePolicy`(인라인 정책)는 `iam:PolicyARN` 조건 적용 불가 → 인라인 정책으로 우회 가능하므로 `PutRolePolicy` 자체를 Deny하거나 Boundary로 제한
- `AttachGroupPolicy`도 함께 Deny — Group을 통한 우회 방지

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
