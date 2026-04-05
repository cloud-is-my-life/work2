# Module 3 정책 JSON 모음

CloudShell에서 바로 쓰기 위한 fine-grained IAM 정책 템플릿.

## 기존 템플릿 (S3 / ABAC / 기본 Boundary)

| 파일 | 용도 |
|---|---|
| `q01-s3-prefix-readonly-with-explicit-deny.json` | reports Prefix 읽기 + 삭제 Deny + TLS 강제 |
| `q02-abac-principal-tag-team.json` | PrincipalTag `Team` 기반 ABAC |
| `q03-boundary-readonly-s3.json` | Delegated IAM 과제용 Permissions Boundary |
| `q03-delegate-policy-template.json` | Boundary 강제 + Admin 정책 부착 차단 |

---

## IAM 위임 관리 / 권한 상승 방지 템플릿

| 파일 | 용도 | 주요 조건 키 |
|---|---|---|
| `iam-01-permissions-boundary-enforcement.json` | Boundary 정책 본체 — 최대 권한 상한선 정의 | (없음, Boundary 자체) |
| `iam-02-delegated-admin-create-role-with-boundary.json` | 위임 관리자 정책 — CreateRole/CreateUser 시 Boundary 강제 | `iam:PermissionsBoundary`, `iam:PolicyARN` |
| `iam-03-self-service-password-mfa.json` | 사용자 자기 비밀번호/MFA/액세스키 셀프 관리 | `aws:MultiFactorAuthPresent`, `${aws:username}` |
| `iam-04-path-based-delegation.json` | IAM Path 기반 팀별 역할/정책 위임 | `iam:PolicyARN` + Resource ARN 패턴 |
| `iam-05-tag-based-role-assumption.json` | 태그 기반 역할 가정 (ABAC AssumeRole) | `iam:ResourceTag/*`, `aws:PrincipalTag/*` |
| `iam-06-prevent-privilege-escalation.json` | 21가지 권한 상승 벡터 차단 | `iam:PolicyARN`, `iam:PassedToService` |
| `iam-07-passrole-fine-grained.json` | PassRole 세밀 제어 (서비스/리소스 범위 제한) | `iam:PassedToService`, `iam:AssociatedResourceARN` |

---

## 플레이스홀더 치환 방법

```bash
export ACCOUNT_ID="123456789012"
export BOUNDARY_POLICY_NAME="MyBoundaryPolicy"
export ADMIN_ROLE_NAME="AdminRole"
export TEAM_PATH="teamA"
export EC2_ROLE_PREFIX="ec2-app-"
export LAMBDA_ROLE_PREFIX="lambda-fn-"

# 복사 후 치환
cp policies/iam-02-delegated-admin-create-role-with-boundary.json /tmp/policy.json
sed -i "s/ACCOUNT_ID/$ACCOUNT_ID/g" /tmp/policy.json
sed -i "s/BOUNDARY_POLICY_NAME/$BOUNDARY_POLICY_NAME/g" /tmp/policy.json
sed -i "s/ADMIN_ROLE_NAME/$ADMIN_ROLE_NAME/g" /tmp/policy.json
```

---

## 조합 패턴 (실전 시나리오)

### 시나리오 A: 개발팀 위임 관리자 설정
1. `iam-01` → Boundary 정책으로 생성 (최대 권한 상한)
2. `iam-02` → 위임 관리자 사용자에 연결 (Boundary 강제 + 고권한 차단)
3. 위임 관리자가 CreateRole 시 `iam-01` Boundary 자동 첨부

### 시나리오 B: 팀별 IAM Path 분리
1. `iam-04` → 팀별 CI/CD 역할에 연결 (`TEAM_PATH=teamA`)
2. 각 팀은 `/teamA/*` 경로 내에서만 역할/정책 생성 가능
3. `/security/*`, `/admin/*` 경로는 접근 불가

### 시나리오 C: 사용자 MFA 강제
1. `iam-03` → 모든 IAM 사용자에 연결
2. MFA 미등록 시 MFA 등록 외 모든 작업 차단
3. MFA 등록 후 정상 작업 가능

### 시나리오 D: PassRole 최소 권한
1. `iam-07` → EC2/Lambda/ECS 역할만 PassRole 허용
2. CloudFormation/Glue/DataPipeline 등 고위험 서비스 PassRole 차단
3. `iam-06`과 조합하여 권한 상승 벡터 전체 차단
