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
