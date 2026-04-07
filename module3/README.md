# Module 3: Fine-grained IAM Policy

---

## 핵심 요약 (경기장에서 이것만 기억)

> **⚠️ IAM은 Deny 우선**: Allow가 여러 군데 있어도, Explicit Deny 하나면 끝.

> **⚠️ 권한 평가는 "합집합 + 교집합"**: Identity/Resource는 합집합, Boundary/SCP는 교집합.

> **⚠️ ABAC 강제는 Allow만으로 부족**: 태그 없는 주체를 막으려면 Deny(`StringNotEquals`, `Null`)를 같이 둬야 우회가 줄어든다.

> **⚠️ 시뮬레이터 결과만 맹신 금지**: IAM Policy Simulator는 실제 호출 결과와 차이날 수 있으므로 `aws sts get-caller-identity` + 실제 API 호출로 최종 확인.

> **⚠️ PassRole 제어 함정**: `iam:PassRole`은 `ResourceTag` 기반 제어가 신뢰되지 않으니 `Resource` ARN 범위를 좁혀서 통제.

- 과제는 보통 **정책 작성 → User/Role에 연결 → 자격증명 전환(profile) → Allow/AccessDenied 검증** 흐름으로 나온다.
- `simulate-principal-policy`는 빠른 1차 검증용, 채점 대응은 실제 호출 결과 증빙이 더 안전하다.
- CloudShell 채점 기준에서 재현성을 위해 명령은 변수(`ACCOUNT_ID`, `DATA_BUCKET`, `AWS_REGION`) 기반으로 작성.

---

## 목차

| # | 주제 | 바로가기 |
|---|------|----------|
| 1 | IAM 평가 로직/조건 키 도우미 | [cheatsheet.md](./cheatsheet.md) |
| 2 | 예시 과제 (예상 출제형) | [examples-questions/](./examples-questions/) |
| 3 | 예시 과제 정답 풀이 | [examples-questions/answers/](./examples-questions/answers/) |
| 4 | 정책 JSON 템플릿 | [policies/](./policies/) |
| 5 | 리소스별 확장 실전 케이스 | [resources/](./resources/) |

---

## 예상 출제 형태 (module3)

### 타입 A — 기본 Fine-grained S3 권한
- 특정 Prefix만 `List/Get` 허용
- 삭제(`DeleteObject`)는 Explicit Deny
- TLS 미사용(`aws:SecureTransport=false`) Deny

### 타입 B — ABAC (PrincipalTag 기반)
- 동일 정책을 여러 사용자에 붙이고, `aws:PrincipalTag/Team` 값으로 접근 범위 분기
- 검증은 사용자 전환(profile)으로 `home/analytics/*` 성공 vs `home/ops/*` 실패 확인

### 타입 C — Delegated IAM + Permissions Boundary
- 위임 관리자(User)가 새 User를 만들되 Boundary 없이 생성 못 하게 제한
- 고권한 정책(예: AdministratorAccess) 부착 금지

### 타입 D — 조건식 해석 함정
- `ForAllValues`/`ForAnyValue`, `IfExists`, `Null` 조합
- "허용이 안 되는 이유"를 논리식으로 설명하도록 요구

### 타입 E — 정책 시뮬레이션 + 실호출 교차검증
- `simulate-principal-policy` 결과 제출
- 같은 시나리오를 실제 AWS CLI 호출로 재검증

### 타입 F — 멀티 리소스 복합 시나리오
- SQS + KMS + SNS/S3/EventBridge 조합처럼 Resource-based policy와 Identity-based policy를 동시에 설계
- IAM policy만으로 해결 안 되는 케이스(Queue policy, Key policy, Secret resource policy) 분리 설계 요구

---

## 권한 전환 검증 루틴 (CloudShell 기준)

> 아래는 채점/실전에서 반복 가능한 공통 패턴.

```bash
export AWS_REGION="ap-northeast-2"
export ACCOUNT_ID="123456789012"
export DATA_BUCKET="YOUR_DATA_BUCKET"
export USER_NAME="mod3-user-a"
export PROFILE_NAME="mod3-user-a"
```

1) 사용자/정책 생성 및 연결

```bash
aws iam create-user --user-name "$USER_NAME"
aws iam create-policy \
  --policy-name "MOD3_SAMPLE_POLICY" \
  --policy-document file://policy.json
aws iam attach-user-policy \
  --user-name "$USER_NAME" \
  --policy-arn "arn:aws:iam::$ACCOUNT_ID:policy/MOD3_SAMPLE_POLICY"
```

2) 액세스 키 발급 후 프로파일 구성

```bash
aws iam create-access-key --user-name "$USER_NAME"
aws configure --profile "$PROFILE_NAME"
```

3) 신분 확인

```bash
aws sts get-caller-identity --profile "$PROFILE_NAME"
```

4) Allow/Denied 동시 검증

```bash
# 기대: 성공
aws s3 ls "s3://$DATA_BUCKET/allowed/" --profile "$PROFILE_NAME"

# 기대: AccessDenied
aws s3 rm "s3://$DATA_BUCKET/allowed/sample.txt" --profile "$PROFILE_NAME"
```

5) (선택) 시뮬레이터로 원인 추적

```bash
aws iam simulate-principal-policy \
  --policy-source-arn "arn:aws:iam::$ACCOUNT_ID:user/$USER_NAME" \
  --action-names s3:GetObject s3:DeleteObject \
  --resource-arns "arn:aws:s3:::$DATA_BUCKET/allowed/sample.txt"
```

---

## 공식 문서 레퍼런스

- IAM 평가 로직: https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_evaluation-logic.html
- 조건 연산자: https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements_condition_operators.html
- 다중 condition key/value 로직: https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_condition-logic-multiple-context-keys-or-values.html
- Policy variables: https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_variables.html
- Policy simulator: https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_testing-policies.html
- CLI `simulate-principal-policy`: https://docs.aws.amazon.com/cli/latest/reference/iam/simulate-principal-policy.html
- CLI `get-context-keys-for-principal-policy`: https://docs.aws.amazon.com/cli/latest/reference/iam/get-context-keys-for-principal-policy.html
- Permissions boundary: https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_boundaries.html
- PassRole 주의사항: https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_use_passrole.html
