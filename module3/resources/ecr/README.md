# ECR Fine-grained IAM 실전 케이스

## 핵심 요약

> **⚠️ `ecr:GetAuthorizationToken`은 계정 수준** — 리포지토리 ARN이 아닌 `"Resource": "*"` 필수. 빠뜨리면 push/pull 전부 실패.

> **⚠️ Push와 Pull 권한은 완전히 다른 Action 세트** — Pull은 3개, Push는 4~5개 Action 필요.

> **⚠️ Repository Policy(Resource-based)로 크로스 계정 pull 가능** — IAM Policy 없이도 동작.

> **⚠️ 이미지 삭제 차단은 `ecr:BatchDeleteImage` Deny** — `DeleteRepository`와 별도.

---

## Push / Pull 필수 Action 분리

| 역할 | 필수 Actions |
|---|---|
| Pull (읽기) | `ecr:GetDownloadUrlForLayer`, `ecr:BatchGetImage`, `ecr:BatchCheckLayerAvailability` |
| Push (쓰기) | `ecr:PutImage`, `ecr:InitiateLayerUpload`, `ecr:UploadLayerPart`, `ecr:CompleteLayerUpload`, `ecr:BatchCheckLayerAvailability` |
| 공통 필수 | `ecr:GetAuthorizationToken` (Resource: `*`) |

---

## ARN 패턴

```
# 특정 리포지토리
arn:aws:ecr:REGION:ACCOUNT_ID:repository/REPO_NAME

# 와일드카드
arn:aws:ecr:REGION:ACCOUNT_ID:repository/team-a/*
arn:aws:ecr:REGION:ACCOUNT_ID:repository/*
```

---

## 정책 파일

| 케이스 | 파일 | 의도 |
|---|---|---|
| Case 01 | `policies/case01-pull-only.json` | Pull 전용 (읽기만) |
| Case 02 | `policies/case02-push-pull-specific-repo.json` | 특정 리포지토리 Push+Pull |
| Case 03 | `policies/case03-deny-image-delete.json` | 이미지 삭제 차단 |
| Case 04 | `policies/case04-repo-policy-cross-account.json` | Repository Policy 크로스 계정 pull |
| Case 05 | `policies/case05-abac-tag-based.json` | 태그 기반 리포지토리 접근 |

---

## 케이스별 상세 설명

### Case 01 — Pull 전용 (읽기만)

**시나리오**: CI/CD 파이프라인의 배포 단계에서 이미지를 Pull만 허용. Push, 삭제 등 쓰기 작업 불가.

**핵심 메커니즘**:
- Allow: `ecr:GetDownloadUrlForLayer`, `ecr:BatchGetImage`, `ecr:BatchCheckLayerAvailability` → 특정 리포지토리 ARN
- Allow: `ecr:GetAuthorizationToken` → Resource `*` (계정 수준, 리포지토리 무관)

**허용**: `docker pull ACCOUNT.dkr.ecr.REGION.amazonaws.com/REPO:tag`
**거부**: `docker push`, 이미지 삭제, 리포지토리 설정 변경

**주의사항**:
- `GetAuthorizationToken` 빠뜨리면 `docker login` 자체가 실패 → Pull 전에 반드시 필요
- `BatchCheckLayerAvailability`는 Pull에도 필요 — 빠뜨리면 레이어 다운로드 실패
- `DescribeImages`, `DescribeRepositories`는 메타데이터 조회용 — Pull 자체에는 불필요하지만 CI/CD에서 태그 확인 시 필요할 수 있음

---

### Case 02 — 특정 리포지토리 Push+Pull

**시나리오**: 개발팀이 자기 팀 리포지토리(`team-a/*`)에만 Push+Pull 가능. 다른 팀 리포지토리는 접근 불가.

**핵심 메커니즘**:
- Allow: Pull 3개 Action + Push 4개 Action → Resource `arn:aws:ecr:REGION:ACCOUNT:repository/team-a/*`
- Allow: `ecr:GetAuthorizationToken` → Resource `*`
- Push Actions: `ecr:PutImage`, `ecr:InitiateLayerUpload`, `ecr:UploadLayerPart`, `ecr:CompleteLayerUpload`

**허용**: `team-a/` prefix 리포지토리에 Push+Pull
**거부**: `team-b/` 리포지토리 접근 시 `AccessDenied`

**주의사항**:
- Push에 `BatchCheckLayerAvailability` 빠뜨리면 레이어 중복 체크 실패로 push 불가
- `ecr:CreateRepository`는 별도 Action — 리포지토리 생성 권한은 이 정책에 미포함
- 리포지토리 와일드카드 `team-a/*`는 `team-a/app`, `team-a/api` 등 모두 매칭

---

### Case 03 — 이미지 삭제 차단

**시나리오**: 이미지 Push+Pull은 허용하되, 이미지 삭제와 리포지토리 삭제는 Explicit Deny로 차단.

**핵심 메커니즘**:
- Deny: `ecr:BatchDeleteImage` → 이미지 삭제 차단
- Deny: `ecr:DeleteRepository` → 리포지토리 삭제 차단
- Allow: Push+Pull 전체 Action

**허용**: 이미지 Push, Pull, 메타데이터 조회
**거부**: 이미지 삭제, 리포지토리 삭제 → `AccessDenied`

**주의사항**:
- `BatchDeleteImage`와 `DeleteRepository`는 별도 Action — 둘 다 Deny 필요
- 이미지 태그 immutability는 IAM이 아닌 리포지토리 설정(`imageTagMutability: IMMUTABLE`)으로 제어
- Lifecycle Policy로 자동 삭제는 ECR 서비스가 수행 → IAM Deny와 무관하게 동작
- `DeleteRepositoryPolicy`도 Deny 고려 — Repository Policy 삭제로 크로스 계정 접근 차단 방지

---

### Case 04 — Repository Policy 크로스 계정 Pull

**시나리오**: 외부 계정이 이 리포지토리에서 이미지를 Pull할 수 있도록 Repository Policy(Resource-based) 설정.

**핵심 메커니즘**:
- Repository Policy: `Principal: {"AWS": "arn:aws:iam::EXTERNAL_ACCOUNT:root"}` 또는 특정 역할
- Allow: Pull 3개 Action
- Condition: `aws:PrincipalOrgID`로 Organization 내부만 허용 (선택)

**허용**: 외부 계정에서 `docker pull` 성공
**거부**: 비허용 계정에서 Pull 시도 → `AccessDenied`

**주의사항**:
- Repository Policy는 `Principal` 필수 — IAM Policy와 혼동 금지
- 크로스 계정 Pull 시 외부 계정에서 `GetAuthorizationToken`은 **자기 계정**에서 발급 → 소유 계정의 IAM 불필요
- `ecr:SetRepositoryPolicy`로 설정 — Console에서도 가능
- 외부 계정의 IAM Policy에도 해당 리포지토리 ARN에 대한 Pull 권한 필요 (교집합)

---

### Case 05 — 태그 기반 ABAC

**시나리오**: 리포지토리의 `Team` 태그와 IAM 사용자의 `PrincipalTag/Team`이 일치할 때만 접근 허용.

**핵심 메커니즘**:
- `aws:ResourceTag/Team` + `StringEquals` + `${aws:PrincipalTag/Team}` 동적 매칭
- Deny: `aws:PrincipalTag/Team` `Null: "true"` → 태그 없는 사용자 전면 차단

**허용**: `PrincipalTag/Team = backend` → `ResourceTag/Team = backend` 리포지토리만
**거부**: 태그 불일치 또는 태그 미설정 시 `AccessDenied`

**주의사항**:
- `GetAuthorizationToken`은 리포지토리 수준이 아닌 계정 수준 → 태그 조건 적용 불가, 별도 `Resource: "*"` Statement 필요
- `ecr:DescribeRepositories`도 태그 조건 적용 가능하지만, `ecr:DescribeImages`는 리포지토리 ARN 기반
- 리포지토리 생성 시 태그 강제는 `aws:RequestTag/Team` + `Null` 조건으로 별도 구현
- `ecr:TagResource`/`ecr:UntagResource` 권한도 제어해야 태그 변경으로 우회 방지

---

## CloudShell 준비

```bash
export AWS_REGION="ap-northeast-2"
export ACCOUNT_ID="123456789012"
export REPO_NAME="my-app"
export USER_NAME="mod3-ecr-user"
export PROFILE_NAME="mod3-ecr-user"
```

---

## 검증 예시

```bash
# 인증 토큰 발급 — 성공 기대
aws ecr get-login-password --region "$AWS_REGION" --profile "$PROFILE_NAME"

# 이미지 목록 조회 — 성공 기대
aws ecr describe-images \
  --repository-name "$REPO_NAME" \
  --profile "$PROFILE_NAME"

# 이미지 삭제 시도 — AccessDenied 기대
aws ecr batch-delete-image \
  --repository-name "$REPO_NAME" \
  --image-ids imageTag=latest \
  --profile "$PROFILE_NAME"
```

---

## 감점 방지 포인트

- `GetAuthorizationToken` 빠뜨리면 `docker login` 자체가 실패
- Push에 `BatchCheckLayerAvailability` 빠뜨리면 레이어 중복 체크 실패로 push 불가
- Repository Policy는 `Principal` 필수 — IAM Policy와 혼동 금지
- `ecr:DescribeRepositories`는 리포지토리 수준 권한이지만 `ecr:DescribeImages`도 별도 필요
- 이미지 태그 immutability는 IAM이 아닌 리포지토리 설정(`imageTagMutability`)으로 제어
