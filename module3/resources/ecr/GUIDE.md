# ECR Fine-grained IAM 실전 가이드

AWS ECR에서 IAM 정책을 잘못 짜면 `docker login`부터 막힌다. 이 가이드는 경쟁 현장에서 바로 쓸 수 있는 케이스 10개와, 반드시 알아야 할 함정 세 가지를 정리한다.

---

## Push/Pull 필수 Action 완전 정리

ECR은 Push와 Pull에 필요한 Action이 완전히 다르다. 하나라도 빠지면 조용히 실패한다.

### Pull (읽기)

| Action | 역할 |
|---|---|
| `ecr:GetDownloadUrlForLayer` | 레이어 다운로드 URL 발급 |
| `ecr:BatchGetImage` | 이미지 매니페스트 조회 |
| `ecr:BatchCheckLayerAvailability` | 레이어 존재 여부 확인 |

세 개 모두 필수다. `BatchCheckLayerAvailability`를 Pull에서 빼는 실수가 많다.

### Push (쓰기)

| Action | 역할 |
|---|---|
| `ecr:PutImage` | 이미지 매니페스트 저장 |
| `ecr:InitiateLayerUpload` | 레이어 업로드 세션 시작 |
| `ecr:UploadLayerPart` | 레이어 청크 업로드 |
| `ecr:CompleteLayerUpload` | 레이어 업로드 완료 |
| `ecr:BatchCheckLayerAvailability` | 중복 레이어 체크 (Push에도 필요) |

### 공통 필수

```
ecr:GetAuthorizationToken  →  Resource: "*"  (리포지토리 ARN 아님)
```

---

## GetAuthorizationToken 함정

경쟁에서 가장 많이 틀리는 부분이다.

`ecr:GetAuthorizationToken`은 **계정 수준 API**다. 특정 리포지토리에 묶이지 않는다. 그래서 `Resource`를 리포지토리 ARN으로 지정하면 **항상 실패**한다.

```json
// 틀린 예
{
  "Action": "ecr:GetAuthorizationToken",
  "Resource": "arn:aws:ecr:ap-northeast-2:123456789012:repository/my-app"
}

// 올바른 예
{
  "Action": "ecr:GetAuthorizationToken",
  "Resource": "*"
}
```

`docker login`이 실패하면 Push도 Pull도 전부 막힌다. 정책에서 이 Action이 빠졌거나 Resource가 잘못됐는지 먼저 확인한다.

ABAC(태그 기반) 정책을 쓸 때도 마찬가지다. `GetAuthorizationToken`은 리포지토리 수준이 아니라서 태그 조건을 붙일 수 없다. 반드시 별도 Statement로 `Resource: "*"` 처리해야 한다.

---

## Repository Policy vs IAM Policy

| 구분 | IAM Policy (Identity-based) | Repository Policy (Resource-based) |
|---|---|---|
| 적용 대상 | IAM User / Role | ECR 리포지토리 자체 |
| `Principal` 필드 | 없음 | 필수 |
| 크로스 계정 | 양쪽 모두 설정 필요 | Repository Policy만으로 가능 |
| 주요 용도 | 내부 계정 권한 제어 | 외부 계정 Pull, ECS 역할 허용 |

크로스 계정 Pull 시나리오에서 자주 헷갈린다. 외부 계정이 Pull하려면:

1. 소유 계정의 리포지토리에 Repository Policy 설정 (외부 계정 Principal 허용)
2. 외부 계정의 IAM Policy에도 해당 리포지토리 ARN에 대한 Pull 권한 추가

두 조건의 교집합이 실제 허용 범위다. 어느 한쪽만 있으면 `AccessDenied`가 난다.

`GetAuthorizationToken`은 외부 계정이 **자기 계정**에서 발급한다. 소유 계정의 IAM 설정과 무관하다.

---

## 케이스별 정리

### Case 01: Pull 전용

파일: `policies/case01-pull-only.json`

CI/CD 배포 단계처럼 이미지를 읽기만 해야 하는 역할에 부여한다. Pull 3개 Action + `GetAuthorizationToken`만 허용. Push, 삭제, 설정 변경은 전부 묵시적 Deny 상태다.

```bash
# 검증: Pull 성공
docker pull ACCOUNT.dkr.ecr.REGION.amazonaws.com/my-app:latest

# 검증: Push 실패 (AccessDenied 기대)
docker push ACCOUNT.dkr.ecr.REGION.amazonaws.com/my-app:test
```

---

### Case 02: 특정 리포지토리 Push+Pull

파일: `policies/case02-push-pull-specific-repo.json`

`team-a/*` prefix 리포지토리에만 Push+Pull 허용. 다른 팀 리포지토리는 `AccessDenied`. 와일드카드 `team-a/*`는 `team-a/app`, `team-a/api` 등 모두 매칭한다.

Push에 `BatchCheckLayerAvailability`를 빠뜨리면 레이어 중복 체크 실패로 push가 안 된다. Push Action 5개 모두 챙겨야 한다.

---

### Case 03: 이미지 삭제 차단

파일: `policies/case03-deny-image-delete.json`

Push+Pull은 허용하되 이미지 삭제와 리포지토리 삭제를 Explicit Deny로 막는다. `BatchDeleteImage`와 `DeleteRepository`는 별도 Action이라 둘 다 Deny해야 한다.

Lifecycle Policy로 인한 자동 삭제는 ECR 서비스가 수행하므로 이 Deny와 무관하게 동작한다.

---

### Case 04: Repository Policy 크로스 계정 Pull

파일: `policies/case04-repo-policy-cross-account.json`

외부 계정이 이 리포지토리에서 Pull할 수 있도록 Resource-based Policy를 설정한다. `Principal` 필드에 외부 계정 ARN을 지정한다. IAM Policy와 달리 `Principal`이 없으면 정책 자체가 유효하지 않다.

---

### Case 05: 태그 기반 ABAC

파일: `policies/case05-abac-tag-based.json`

리포지토리의 `Team` 태그와 IAM 사용자의 `PrincipalTag/Team`이 일치할 때만 접근 허용. 태그 없는 사용자는 `Null` 조건으로 전면 차단한다.

`ecr:TagResource` / `ecr:UntagResource` 권한도 제어해야 태그 변경으로 우회하는 걸 막을 수 있다.

---

### Case 06: 이미지 태그 Immutability 설정 변경 차단

파일: `policies/case06-deny-tag-mutability-change.json`

리포지토리의 `imageTagMutability` 설정을 `IMMUTABLE`로 고정한 뒤, 이 설정을 다시 바꾸지 못하도록 IAM으로 차단하는 패턴이다.

`ecr:PutImageTagMutability`를 Deny하면 콘솔이나 CLI에서 설정 변경 시도 시 `AccessDenied`가 난다. `ecr:PutImageScanningConfiguration`도 함께 Deny해서 스캔 설정 변경도 막는다.

```bash
# 검증: 설정 변경 시도 (AccessDenied 기대)
aws ecr put-image-tag-mutability \
  --repository-name my-app \
  --image-tag-mutability MUTABLE \
  --profile restricted-user
```

주의: `imageTagMutability` 자체는 IAM이 아닌 리포지토리 설정(`ecr:CreateRepository` 또는 `ecr:PutImageTagMutability`)으로 제어한다. IAM Deny는 이미 설정된 값을 변경하지 못하게 막는 용도다.

---

### Case 07: Lifecycle Policy 변경 차단

파일: `policies/case07-deny-lifecycle-policy-change.json`

이미지 자동 삭제 규칙(Lifecycle Policy)을 보호하는 패턴이다. 운영팀이 실수로 Lifecycle Policy를 삭제하거나 덮어쓰는 걸 방지한다.

`ecr:PutLifecyclePolicy`와 `ecr:DeleteLifecyclePolicy` 둘 다 Deny해야 한다. 하나만 막으면 삭제 후 재생성으로 우회할 수 있다.

```bash
# 검증: Lifecycle Policy 변경 시도 (AccessDenied 기대)
aws ecr put-lifecycle-policy \
  --repository-name my-app \
  --lifecycle-policy-text file://lifecycle.json \
  --profile restricted-user

# 검증: Lifecycle Policy 삭제 시도 (AccessDenied 기대)
aws ecr delete-lifecycle-policy \
  --repository-name my-app \
  --profile restricted-user
```

---

### Case 08: 특정 태그 이미지만 Pull 허용 (ECR 한계와 대안)

파일: `policies/case08-tag-based-pull-limitation.json`

**ECR은 이미지 태그(`imageTag`) 기반 IAM 조건을 지원하지 않는다.**

`docker pull my-app:prod`처럼 특정 태그만 허용하는 IAM 조건은 존재하지 않는다. ECR의 IAM 권한 범위는 리포지토리 ARN 수준까지다.

대안은 두 가지다.

**대안 1: 리포지토리 분리**
`prod-app`, `dev-app`처럼 리포지토리를 환경별로 나누고, IAM에서 `prod-*` ARN만 허용한다. 이 케이스의 JSON이 이 방식을 구현한다.

```
arn:aws:ecr:REGION:ACCOUNT:repository/prod-*  →  Pull 허용
arn:aws:ecr:REGION:ACCOUNT:repository/dev-*   →  Deny
```

**대안 2: 이미지 서명 검증**
Notation 또는 Cosign으로 이미지에 서명하고, ECS/EKS 레벨에서 서명 없는 이미지 실행을 차단한다. IAM 레이어가 아닌 런타임 레이어에서 제어하는 방식이다.

경쟁 시나리오에서 "특정 태그만 Pull 허용"이 나오면 리포지토리 분리 방식으로 답하는 게 현실적이다.

---

### Case 09: Repository Policy로 ECS Task 실행 역할 Pull 허용

파일: `policies/case09-repo-policy-ecs-task-pull.json`

ECS Task가 ECR에서 이미지를 Pull하려면 `ecsTaskExecutionRole`에 Pull 권한이 있어야 한다. IAM Policy로 역할에 직접 붙이는 방법도 있지만, Repository Policy로 리포지토리 쪽에서 허용하는 방법도 있다.

Repository Policy 방식의 장점은 역할 정책을 건드리지 않고 리포지토리 단위로 접근을 제어할 수 있다는 점이다. 여러 계정의 ECS 역할을 한 리포지토리에서 관리할 때 유용하다.

`aws:SourceAccount` 조건을 추가하면 서비스 주체(`ecs-tasks.amazonaws.com`)를 통한 접근을 자기 계정으로 한정할 수 있다. Confused Deputy 공격을 방어하는 패턴이다.

```bash
# Repository Policy 적용
aws ecr set-repository-policy \
  --repository-name my-app \
  --policy-text file://case09-repo-policy-ecs-task-pull.json
```

주의: `GetAuthorizationToken`은 Repository Policy로 제어할 수 없다. ECS Task 실행 역할의 IAM Policy에 별도로 추가해야 한다.

---

### Case 10: 스캔 결과 조회 전용

파일: `policies/case10-scan-findings-readonly.json`

보안팀이나 감사 역할처럼 이미지 취약점 스캔 결과만 볼 수 있어야 하는 경우에 쓴다. Pull, Push, 삭제는 전혀 허용하지 않는다.

`ecr:DescribeImageScanFindings`가 핵심 Action이다. 스캔 결과를 보려면 어떤 이미지가 있는지도 알아야 하므로 `ecr:DescribeImages`, `ecr:ListImages`, `ecr:DescribeRepositories`도 함께 허용한다.

```bash
# 검증: 스캔 결과 조회 (성공 기대)
aws ecr describe-image-scan-findings \
  --repository-name my-app \
  --image-id imageTag=latest \
  --profile security-auditor

# 검증: Pull 시도 (AccessDenied 기대)
docker pull ACCOUNT.dkr.ecr.REGION.amazonaws.com/my-app:latest
```

스캔을 직접 시작하려면 `ecr:StartImageScan`도 추가해야 한다. 이 정책은 결과 조회만 허용하고 스캔 트리거는 막는다.

---

## 정책 파일 전체 목록

| 케이스 | 파일 | 의도 |
|---|---|---|
| Case 01 | `policies/case01-pull-only.json` | Pull 전용 |
| Case 02 | `policies/case02-push-pull-specific-repo.json` | 특정 리포지토리 Push+Pull |
| Case 03 | `policies/case03-deny-image-delete.json` | 이미지 삭제 차단 |
| Case 04 | `policies/case04-repo-policy-cross-account.json` | Repository Policy 크로스 계정 Pull |
| Case 05 | `policies/case05-abac-tag-based.json` | 태그 기반 ABAC |
| Case 06 | `policies/case06-deny-tag-mutability-change.json` | 태그 Immutability 설정 변경 차단 |
| Case 07 | `policies/case07-deny-lifecycle-policy-change.json` | Lifecycle Policy 변경 차단 |
| Case 08 | `policies/case08-tag-based-pull-limitation.json` | 이미지 태그 기반 제어 한계와 대안 |
| Case 09 | `policies/case09-repo-policy-ecs-task-pull.json` | ECS Task 실행 역할 Pull 허용 |
| Case 10 | `policies/case10-scan-findings-readonly.json` | 스캔 결과 조회 전용 |

---

## 빠른 검증 루틴

```bash
export AWS_REGION="ap-northeast-2"
export ACCOUNT_ID="123456789012"
export REPO_NAME="my-app"
export PROFILE_NAME="mod3-ecr-user"

# 1. 인증 토큰 발급 (GetAuthorizationToken 확인)
aws ecr get-login-password \
  --region "$AWS_REGION" \
  --profile "$PROFILE_NAME"

# 2. docker login
aws ecr get-login-password --region "$AWS_REGION" --profile "$PROFILE_NAME" \
  | docker login \
    --username AWS \
    --password-stdin \
    "$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

# 3. Pull 테스트
docker pull "$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$REPO_NAME:latest"

# 4. 이미지 목록 조회
aws ecr describe-images \
  --repository-name "$REPO_NAME" \
  --region "$AWS_REGION" \
  --profile "$PROFILE_NAME"

# 5. 삭제 시도 (Deny 케이스 검증)
aws ecr batch-delete-image \
  --repository-name "$REPO_NAME" \
  --image-ids imageTag=latest \
  --region "$AWS_REGION" \
  --profile "$PROFILE_NAME"
```

---

## 감점 방지 포인트 요약

- `GetAuthorizationToken`은 `Resource: "*"` 필수. 리포지토리 ARN으로 지정하면 `docker login` 자체가 실패한다.
- Push에 `BatchCheckLayerAvailability` 빠뜨리면 레이어 중복 체크 실패로 push가 안 된다.
- Repository Policy는 `Principal` 필수. IAM Policy와 구조가 다르다.
- 이미지 태그 기반 IAM 조건은 ECR에서 지원하지 않는다. 리포지토리 분리로 대응한다.
- `BatchDeleteImage`와 `DeleteRepository`는 별도 Action이다. 이미지 삭제 차단 시 둘 다 Deny해야 한다.
- Lifecycle Policy 보호는 `PutLifecyclePolicy`와 `DeleteLifecyclePolicy` 둘 다 막아야 한다.
