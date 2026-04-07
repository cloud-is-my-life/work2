# IAM 위임 관리 + 권한 상승 방어 실전 가이드

> AWS Skills Competition 2026 — Module 3 IAM (Delegated Administration) Fine-grained 심화

---

## 이 문서를 읽는 법

경기 중에 IAM 위임 관리 문제가 나오면 대부분 세 가지 중 하나다.

1. 위임 관리자가 Boundary 없이 User/Role을 만들 수 있는가?
2. 위임 관리자가 자기 권한보다 높은 권한을 얻을 수 있는가?
3. 특정 조건(MFA, 태그, 경로)을 만족해야만 작업이 가능한가?

이 세 질문에 "아니오"가 되도록 정책을 짜는 게 전부다. 아래 케이스들은 그 패턴을 유형별로 정리한 것이다.

---

## Permissions Boundary 동작 원리 시각화

IAM 권한 평가는 여러 레이어의 교집합이다. 아래 다이어그램을 머릿속에 새겨두면 시험 함정을 피할 수 있다.

```
요청 발생
    |
    v
+---------------------------+
|  SCP (Organizations)      |  <-- 계정 전체 상한선. SCP에 없으면 무조건 Deny.
+---------------------------+
    |  (SCP Allow 통과)
    v
+---------------------------+
|  Permissions Boundary     |  <-- 개별 User/Role 상한선. Boundary에 없으면 Deny.
+---------------------------+
    |  (Boundary Allow 통과)
    v
+---------------------------+
|  Identity-based Policy    |  <-- 실제 Allow/Deny 정책.
|  (인라인 + 관리형)         |
+---------------------------+
    |
    v
+---------------------------+
|  Resource-based Policy    |  <-- S3 버킷 정책, KMS 키 정책 등.
|  (해당하는 경우)           |  주의: Boundary가 Resource-based를 제한하지 않음.
+---------------------------+
    |
    v
  최종 결정: Allow / Deny

핵심 규칙:
  - Explicit Deny는 어느 레이어에서든 즉시 최종 Deny
  - SCP + Boundary + Identity Policy 모두 Allow여야 최종 Allow
  - Resource-based Policy는 Boundary 우회 가능 (시험 함정)
  - Session Policy (AssumeRole 시 전달)도 교집합 적용

Boundary 교집합 예시:
  Identity Policy: { s3:*, iam:CreateUser }
  Boundary:        { s3:GetObject, s3:PutObject }
  실제 유효 권한:  { s3:GetObject, s3:PutObject }  <-- 교집합만 허용
```

---

## 위임 관리 설계 순서

문제를 받으면 이 순서대로 설계하면 빠진 게 없다.

**1단계. 위임 범위 정의**
- 어떤 경로(path)의 User/Role을 관리하는가? (`dev-team/`, `app-roles/` 등)
- 어떤 Action이 필요한가? (CreateUser, CreateRole, AttachPolicy 등)

**2단계. Boundary 정책 ARN 확정**
- 위임 관리자가 생성하는 모든 User/Role에 강제할 Boundary ARN을 결정한다.
- 이 ARN이 `iam:PermissionsBoundary` 조건값으로 들어간다.

**3단계. Allow 문 작성**
- `iam:CreateRole` / `iam:CreateUser` + `iam:PermissionsBoundary` 조건 (StringEquals)
- 관리 Action (Attach, Detach, Delete, Get, List 등) + Resource 경로 범위
- List/Get 계열은 `Resource: "*"` 별도 허용

**4단계. Deny 문 작성 (권한 상승 차단)**
- `iam:DeleteUserPermissionsBoundary`, `iam:DeleteRolePermissionsBoundary` Deny
- `iam:PutUserPermissionsBoundary`, `iam:PutRolePermissionsBoundary` + StringNotEquals 조건 Deny
- 인라인 정책 우회 차단: `iam:PutUserPolicy`, `iam:PutRolePolicy` Deny (필요 시)
- 고권한 정책 연결 차단: `iam:AttachRolePolicy` + `iam:PolicyARN` 조건 Deny

**5단계. 검증**
- Boundary 포함 생성 -> 성공
- Boundary 없이 생성 -> AccessDenied
- Boundary 제거 시도 -> AccessDenied
- 고권한 정책 연결 시도 -> AccessDenied

---

## 기존 케이스 요약 (Case 01 ~ 07)

| 케이스 | 핵심 패턴 | 주의 포인트 |
|---|---|---|
| Case 01 | Role 생성 + Boundary 강제 | `iam:PermissionsBoundary` 조건 누락 = 즉시 감점 |
| Case 02 | User 생성 + Boundary 강제 | `CreateLoginProfile`, `CreateAccessKey`도 경로 범위 내로 제한 |
| Case 03 | 자기 자신만 관리 (Self-Service) | `${aws:username}` 변수는 Role에서 빈 문자열 |
| Case 04 | 경로 기반 위임 | `ListUsers`는 `Resource: "*"` 필수 |
| Case 05 | 권한 상승 종합 차단 | 5가지 경로 모두 막아야 완전 차단 |
| Case 06 | PassRole 서비스/역할 범위 제한 | Resource는 전달 대상 Role ARN (Lambda ARN 아님) |
| Case 07 | 고권한 관리형 정책 연결 차단 | 인라인 정책(`PutRolePolicy`)으로 우회 가능 -> Case 08과 병행 |

---

## 신규 케이스 (Case 08 ~ 12)

### Case 08 — 인라인 정책 우회 차단

**파일**: `policies/case08-deny-inline-policy.json`

**시나리오**: Case 07에서 `AttachRolePolicy`로 고권한 정책 연결을 막았지만, `PutRolePolicy`(인라인 정책)로 동일한 효과를 낼 수 있다. 이 우회 경로를 차단한다.

**핵심 메커니즘**:
- Deny: `iam:PutUserPolicy`, `iam:DeleteUserPolicy`
- Deny: `iam:PutRolePolicy`, `iam:DeleteRolePolicy`
- Deny: `iam:PutGroupPolicy`, `iam:DeleteGroupPolicy`

**허용**: 관리형 정책(Attach/Detach) 방식만 허용
**거부**: 인라인 정책 생성/수정/삭제 전면 차단

**주의사항**:
- 인라인 정책은 `iam:PolicyARN` 조건 키가 적용되지 않아 Case 07의 ARN 기반 차단을 우회한다.
- 인라인 정책을 완전히 금지하면 기존 인라인 정책도 삭제 불가 -> 사전에 인라인 정책 정리 필요.
- `GetUserPolicy`, `GetRolePolicy`, `ListUserPolicies`, `ListRolePolicies`는 조회 전용이므로 별도 허용 가능.

---

### Case 09 — 서비스 연결 역할 생성 제한

**파일**: `policies/case09-service-linked-role-restriction.json`

**시나리오**: `iam:CreateServiceLinkedRole`은 서비스가 자동으로 역할을 생성할 때 사용된다. 허용 서비스 목록 외에는 생성을 막고, 고위험 서비스(Organizations, SSO 등)는 명시적으로 차단한다.

**핵심 메커니즘**:
- Allow: `iam:CreateServiceLinkedRole` + `iam:AWSServiceName` 조건으로 허용 서비스 목록 지정
- Deny: `iam:CreateServiceLinkedRole` + `iam:AWSServiceName` 조건으로 고위험 서비스 명시 차단
- Deny: `iam:DeleteServiceLinkedRole` -> 서비스 연결 역할 삭제 차단

**허용**: autoscaling, ec2, ecs, lambda, rds 등 일반 서비스
**거부**: organizations, sso, controltower, config 등 관리 서비스

**주의사항**:
- `iam:AWSServiceName` 조건 키는 `CreateServiceLinkedRole`에만 적용된다.
- 서비스 연결 역할 ARN 패턴: `arn:aws:iam::*:role/aws-service-role/SERVICE/ROLE_NAME`
- Allow 목록에 없는 서비스는 암묵적 Deny -> 목록을 너무 좁히면 서비스 기능 장애 발생 가능.
- Deny 문이 Allow보다 우선 -> 고위험 서비스는 Allow 목록에 있어도 Deny 문으로 차단된다.

---

### Case 10 — MFA 강제 (BoolIfExists 패턴)

**파일**: `policies/case10-mfa-enforced-iam-actions.json`

**시나리오**: MFA 없이 로그인한 사용자는 IAM 관련 작업을 전혀 할 수 없다. MFA 등록/활성화 자체는 허용해야 닭이 먼저냐 달걀이 먼저냐 문제를 피할 수 있다.

**핵심 메커니즘**:
- Allow: MFA 등록에 필요한 최소 Action (EnableMFADevice, CreateVirtualMFADevice, ChangePassword 등) -> 자기 자신 Resource만
- Deny: IAM 관리 Action 전체 + `BoolIfExists: { "aws:MultiFactorAuthPresent": "false" }` 조건

**허용**: MFA 인증 후 IAM 작업 전체
**거부**: MFA 없이 IAM 작업 (CreateUser, CreateRole, AttachPolicy 등)

**주의사항**:
- `Bool` vs `BoolIfExists` 차이가 핵심이다.
  - `Bool: false` -> 키가 없으면(CLI 장기 자격증명) 조건 불일치 -> Deny 미적용 (우회 가능)
  - `BoolIfExists: false` -> 키가 없어도 조건 일치 -> Deny 적용 (CLI도 차단)
- MFA 없이 발급된 장기 액세스 키(CLI)도 차단하려면 반드시 `BoolIfExists` 사용.
- MFA 등록 Action을 Deny 목록에서 제외해야 신규 사용자가 MFA를 등록할 수 있다.
- `aws:MultiFactorAuthAge` 조건으로 MFA 인증 후 경과 시간도 제한 가능 (예: 1시간 이내).

---

### Case 11 — 태그 기반 역할 가정 (ABAC AssumeRole)

**파일**: `policies/case11-tag-based-assumerole.json`

**시나리오**: 사용자의 태그(`aws:PrincipalTag/Team`)와 역할의 태그(`iam:ResourceTag/Team`)가 일치할 때만 `sts:AssumeRole`을 허용한다. 하나의 정책으로 여러 팀을 관리하는 ABAC 패턴이다.

**핵심 메커니즘**:
- Allow: `sts:AssumeRole` + `StringEquals: { "iam:ResourceTag/Team": "${aws:PrincipalTag/Team}" }`
- Deny: `sts:AssumeRole` + `Null: { "aws:PrincipalTag/Team": "true" }` -> 태그 없는 주체 차단

**허용**: Team 태그가 일치하는 역할 가정
**거부**: Team 태그가 없는 주체, Team 태그가 다른 역할 가정

**주의사항**:
- `${aws:PrincipalTag/KEY}` 정책 변수는 IAM 사용자와 역할 모두에서 동작한다.
- `iam:ResourceTag/KEY`는 대상 IAM 리소스(역할)의 태그를 참조한다.
- 역할에 태그가 없으면 `iam:ResourceTag/Team`이 빈 문자열 -> StringEquals 불일치 -> Deny.
- Deny 문의 `Null` 조건으로 태그 없는 주체를 명시적으로 차단해야 우회를 막을 수 있다.
- Trust Policy(역할의 신뢰 정책)에도 `PrincipalTag` 조건을 추가하면 이중 검증 가능.

---

### Case 12 — Boundary 정책 자체 수정 차단

**파일**: `policies/case12-deny-boundary-policy-modification.json`

**시나리오**: 위임 관리자가 Boundary 정책 자체를 수정하거나 삭제하면 모든 Boundary 강제가 무력화된다. Boundary 정책 ARN을 직접 보호한다.

**핵심 메커니즘**:
- Deny: `iam:CreatePolicyVersion`, `iam:SetDefaultPolicyVersion`, `iam:DeletePolicy`, `iam:DeletePolicyVersion` -> Resource: `DeveloperBoundary` ARN
- Deny: 같은 Action -> Resource: `Boundary*` 패턴 (모든 Boundary 정책 보호)
- Deny: `iam:DeleteUserPermissionsBoundary`, `iam:DeleteRolePermissionsBoundary` -> 자기 자신 및 관리 역할

**허용**: Boundary 정책 조회 (GetPolicy, GetPolicyVersion)
**거부**: Boundary 정책 내용 변경, 버전 교체, 삭제

**주의사항**:
- `iam:CreatePolicyVersion`으로 새 버전을 만들고 `iam:SetDefaultPolicyVersion`으로 기본 버전을 교체하면 정책 내용을 사실상 변경할 수 있다. 두 Action 모두 차단해야 한다.
- 이 Deny 정책은 Boundary 정책 자체에도 포함시켜야 완전하다 -> Boundary 정책이 자기 자신을 보호.
- `iam:GetPolicy`, `iam:GetPolicyVersion`, `iam:ListPolicyVersions`는 조회 전용이므로 허용해도 무방하다.
- 관리자(Admin)가 Boundary를 업데이트해야 할 때는 이 Deny를 우회할 별도 역할이 필요하다.

---

## 권한 상승 21가지 벡터 실전 대응

AWS IAM에서 알려진 권한 상승 경로를 유형별로 정리했다. 각 벡터 옆에 차단 방법을 함께 적었다.

### 그룹 A. Boundary/정책 직접 조작

| # | 벡터 | 차단 방법 |
|---|---|---|
| 1 | `DeleteUserPermissionsBoundary` | Deny Action |
| 2 | `DeleteRolePermissionsBoundary` | Deny Action |
| 3 | `PutUserPermissionsBoundary` (더 넓은 Boundary로 교체) | Deny + `StringNotEquals iam:PermissionsBoundary` |
| 4 | `PutRolePermissionsBoundary` (더 넓은 Boundary로 교체) | Deny + `StringNotEquals iam:PermissionsBoundary` |
| 5 | `CreatePolicyVersion` + `SetDefaultPolicyVersion` (Boundary 정책 내용 교체) | Deny on Boundary ARN (Case 12) |
| 6 | `DeletePolicy` (Boundary 정책 삭제) | Deny on Boundary ARN (Case 12) |

### 그룹 B. 새 User/Role 생성

| # | 벡터 | 차단 방법 |
|---|---|---|
| 7 | `CreateUser` without Boundary | Deny + `StringNotEquals iam:PermissionsBoundary` |
| 8 | `CreateRole` without Boundary | Deny + `StringNotEquals iam:PermissionsBoundary` |
| 9 | `CreateUser` + `CreateAccessKey` (고권한 User 생성 후 키 발급) | Boundary 강제 + 고권한 정책 연결 차단 |

### 그룹 C. 정책 연결/생성

| # | 벡터 | 차단 방법 |
|---|---|---|
| 10 | `AttachUserPolicy` (AdministratorAccess 등) | Deny + `iam:PolicyARN` 조건 (Case 07) |
| 11 | `AttachRolePolicy` (고권한 정책) | Deny + `iam:PolicyARN` 조건 (Case 07) |
| 12 | `AttachGroupPolicy` (Group 경유 우회) | Deny + `iam:PolicyARN` 조건 (Case 07) |
| 13 | `PutUserPolicy` (인라인 정책으로 우회) | Deny Action (Case 08) |
| 14 | `PutRolePolicy` (인라인 정책으로 우회) | Deny Action (Case 08) |
| 15 | `CreatePolicy` + `AttachUserPolicy` (커스텀 고권한 정책 생성) | `CreatePolicy` Deny 또는 Boundary로 제한 |

### 그룹 D. 역할 전달/가정

| # | 벡터 | 차단 방법 |
|---|---|---|
| 16 | `PassRole` (고권한 역할을 Lambda/EC2에 전달) | PassRole Resource를 특정 ARN으로 제한 (Case 06) |
| 17 | `PassRole` to `iam.amazonaws.com` / `sts.amazonaws.com` (Role chaining) | `iam:PassedToService` 조건으로 IAM/STS 차단 |
| 18 | `AssumeRole` (태그 불일치 역할 가정) | ABAC 조건 + Null 조건 Deny (Case 11) |

### 그룹 E. 서비스 연결/기타

| # | 벡터 | 차단 방법 |
|---|---|---|
| 19 | `CreateServiceLinkedRole` (고위험 서비스용) | `iam:AWSServiceName` 조건으로 허용 목록 제한 (Case 09) |
| 20 | MFA 없이 IAM 작업 (장기 키 남용) | `BoolIfExists: aws:MultiFactorAuthPresent: false` Deny (Case 10) |
| 21 | Resource-based Policy 직접 수정 (S3 버킷 정책, KMS 키 정책) | Boundary는 Resource-based Policy를 제한하지 않음 -> 별도 SCP 또는 서비스별 정책으로 차단 |

---

## 자주 나오는 조건 키 조합 패턴

```json
// 패턴 1: Boundary 강제 (생성 시)
"Condition": {
  "StringEquals": {
    "iam:PermissionsBoundary": "arn:aws:iam::ACCOUNT_ID:policy/DeveloperBoundary"
  }
}

// 패턴 2: Boundary 변경 차단 (Put 시)
"Condition": {
  "StringNotEquals": {
    "iam:PermissionsBoundary": "arn:aws:iam::ACCOUNT_ID:policy/DeveloperBoundary"
  }
}

// 패턴 3: MFA 강제 (BoolIfExists)
"Condition": {
  "BoolIfExists": {
    "aws:MultiFactorAuthPresent": "false"
  }
}

// 패턴 4: ABAC 태그 매칭
"Condition": {
  "StringEquals": {
    "iam:ResourceTag/Team": "${aws:PrincipalTag/Team}"
  }
}

// 패턴 5: 태그 없는 주체 차단
"Condition": {
  "Null": {
    "aws:PrincipalTag/Team": "true"
  }
}

// 패턴 6: PassRole 서비스 제한
"Condition": {
  "StringEquals": {
    "iam:PassedToService": [
      "lambda.amazonaws.com",
      "ec2.amazonaws.com"
    ]
  }
}

// 패턴 7: 고권한 정책 ARN 차단
"Condition": {
  "ArnEquals": {
    "iam:PolicyARN": [
      "arn:aws:iam::aws:policy/AdministratorAccess",
      "arn:aws:iam::aws:policy/IAMFullAccess"
    ]
  }
}
```

---

## 검증 명령어 모음

```bash
export ACCOUNT_ID="123456789012"
export BOUNDARY_ARN="arn:aws:iam::$ACCOUNT_ID:policy/DeveloperBoundary"
export ADMIN_PROFILE="admin"
export DELEGATED_PROFILE="delegated-admin"

# Case 08: 인라인 정책 차단 검증
aws iam put-role-policy \
  --role-name "test-app-role" \
  --policy-name "InlineTest" \
  --policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":"s3:*","Resource":"*"}]}' \
  --profile "$DELEGATED_PROFILE"
# 기대: AccessDenied

# Case 09: 서비스 연결 역할 생성 검증
aws iam create-service-linked-role \
  --aws-service-name "organizations.amazonaws.com" \
  --profile "$DELEGATED_PROFILE"
# 기대: AccessDenied

aws iam create-service-linked-role \
  --aws-service-name "autoscaling.amazonaws.com" \
  --profile "$DELEGATED_PROFILE"
# 기대: 성공 (허용 목록)

# Case 10: MFA 강제 검증 (MFA 없는 프로파일로 시도)
aws iam create-user \
  --user-name "test-no-mfa" \
  --profile "$DELEGATED_PROFILE"
# 기대: AccessDenied (MFA 없는 경우)

# Case 11: 태그 기반 AssumeRole 검증
aws sts assume-role \
  --role-arn "arn:aws:iam::$ACCOUNT_ID:role/team-roles/dev-role" \
  --role-session-name "test" \
  --profile "$DELEGATED_PROFILE"
# 기대: Team 태그 일치 시 성공, 불일치 시 AccessDenied

# Case 12: Boundary 정책 수정 차단 검증
aws iam create-policy-version \
  --policy-arn "$BOUNDARY_ARN" \
  --policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":"*","Resource":"*"}]}' \
  --set-as-default \
  --profile "$DELEGATED_PROFILE"
# 기대: AccessDenied

# 시뮬레이터로 일괄 검증
aws iam simulate-principal-policy \
  --policy-source-arn "arn:aws:iam::$ACCOUNT_ID:user/delegated-admin" \
  --action-names \
    iam:PutRolePolicy \
    iam:CreateServiceLinkedRole \
    iam:CreateUser \
    iam:CreatePolicyVersion \
  --resource-arns \
    "arn:aws:iam::$ACCOUNT_ID:role/test-role" \
    "arn:aws:iam::*:role/aws-service-role/*" \
    "arn:aws:iam::$ACCOUNT_ID:user/test-user" \
    "$BOUNDARY_ARN"
```

---

## 감점 방지 체크리스트

경기 제출 전 이 목록을 한 번 더 확인한다.

- [ ] `iam:CreateRole` / `iam:CreateUser`에 `iam:PermissionsBoundary` 조건 포함
- [ ] `iam:DeleteUserPermissionsBoundary`, `iam:DeleteRolePermissionsBoundary` Deny 포함
- [ ] `iam:PutUserPermissionsBoundary`, `iam:PutRolePermissionsBoundary` + StringNotEquals Deny 포함
- [ ] `iam:PutRolePolicy`, `iam:PutUserPolicy` Deny 포함 (인라인 우회 차단)
- [ ] `iam:PassRole` Resource가 전달 대상 Role ARN (Lambda ARN 아님)
- [ ] `iam:PassedToService` 조건으로 허용 서비스 제한
- [ ] `BoolIfExists` 사용 (Bool 아님) -> CLI 장기 키도 MFA 강제
- [ ] ABAC 패턴에서 태그 없는 주체 Deny (`Null` 조건) 포함
- [ ] Boundary 정책 ARN 자체에 대한 수정 Deny 포함
- [ ] `ListUsers`, `ListRoles`, `ListPolicies`는 `Resource: "*"` 별도 허용
- [ ] AWS 관리형 정책 ARN 형식: `arn:aws:iam::aws:policy/POLICY_NAME` (계정 ID가 `aws`)
