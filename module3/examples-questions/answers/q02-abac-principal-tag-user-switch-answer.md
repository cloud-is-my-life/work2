# [정답] 예시 과제 2 — ABAC PrincipalTag + 사용자 전환

## 목표

- 동일 정책 1개를 사용자 2명에 공통 적용
- `aws:PrincipalTag/Team` 값으로 접근 Prefix 자동 분기
- 사용자 프로파일 전환으로 허용/거부를 교차 검증

---

## 1) CloudShell 준비

```bash
export AWS_REGION="ap-northeast-2"
export ACCOUNT_ID="123456789012"
export DATA_BUCKET="YOUR_DATA_BUCKET"

export POLICY_NAME="MOD3_Q02_ABAC_POLICY"
export USER_ANALYTICS="MOD3_Q02_USER_ANALYTICS"
export USER_OPS="MOD3_Q02_USER_OPS"

export PROFILE_ANALYTICS="mod3-q02-analytics"
export PROFILE_OPS="mod3-q02-ops"
```

---

## 2) ABAC 정책 JSON 작성

```bash
cp module3/policies/q02-abac-principal-tag-team.json /tmp/mod3-q02-abac-policy.json
sed -i "s/YOUR_DATA_BUCKET/$DATA_BUCKET/g" /tmp/mod3-q02-abac-policy.json
```

---

## 3) 사용자 생성(태그 포함) + 정책 연결

```bash
aws iam create-user \
  --user-name "$USER_ANALYTICS" \
  --tags Key=Team,Value=analytics

aws iam create-user \
  --user-name "$USER_OPS" \
  --tags Key=Team,Value=ops

aws iam create-policy \
  --policy-name "$POLICY_NAME" \
  --policy-document file:///tmp/mod3-q02-abac-policy.json

aws iam attach-user-policy \
  --user-name "$USER_ANALYTICS" \
  --policy-arn "arn:aws:iam::$ACCOUNT_ID:policy/$POLICY_NAME"

aws iam attach-user-policy \
  --user-name "$USER_OPS" \
  --policy-arn "arn:aws:iam::$ACCOUNT_ID:policy/$POLICY_NAME"
```

---

## 4) 액세스 키 생성 + 프로파일 설정

```bash
aws iam create-access-key --user-name "$USER_ANALYTICS"
aws configure --profile "$PROFILE_ANALYTICS"

aws iam create-access-key --user-name "$USER_OPS"
aws configure --profile "$PROFILE_OPS"
```

신분 확인:

```bash
aws sts get-caller-identity --profile "$PROFILE_ANALYTICS"
aws sts get-caller-identity --profile "$PROFILE_OPS"
```

---

## 5) 검증 (사용자 전환)

### analytics 사용자

```bash
# 성공 기대
aws s3 ls "s3://$DATA_BUCKET/home/analytics/" --profile "$PROFILE_ANALYTICS"

# 실패 기대 (교차 접근)
aws s3 ls "s3://$DATA_BUCKET/home/ops/" --profile "$PROFILE_ANALYTICS"
```

### ops 사용자

```bash
# 성공 기대
aws s3 ls "s3://$DATA_BUCKET/home/ops/" --profile "$PROFILE_OPS"

# 실패 기대 (교차 접근)
aws s3 ls "s3://$DATA_BUCKET/home/analytics/" --profile "$PROFILE_OPS"
```

실패 케이스는 `AccessDenied`가 나와야 정답.

---

## 6) 시뮬레이터 (선택)

```bash
aws iam simulate-principal-policy \
  --policy-source-arn "arn:aws:iam::$ACCOUNT_ID:user/$USER_ANALYTICS" \
  --action-names s3:ListBucket s3:GetObject \
  --resource-arns "arn:aws:s3:::$DATA_BUCKET" "arn:aws:s3:::$DATA_BUCKET/home/analytics/sample.txt"
```

---

## 7) Console 경로

- IAM Console → Users → 각 사용자의 Tags/Permissions 확인
- IAM Console → Policies → `MOD3_Q02_ABAC_POLICY` JSON 확인
- S3 Console → `home/analytics/`, `home/ops/` 경로 테스트

---

## 8) 감점 방지 포인트

- `create-user`에서 태그 누락하면 정책이 의도대로 동작하지 않음
- `${aws:PrincipalTag/Team}` 오탈자(대소문자 포함) 매우 빈번
- 교차 접근 실패 증빙(AccessDenied)까지 제출해야 ABAC 검증 점수 확보 가능
