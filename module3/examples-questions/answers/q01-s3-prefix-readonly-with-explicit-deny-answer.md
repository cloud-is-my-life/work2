# [정답] 예시 과제 1 — Prefix 기반 ReadOnly + Explicit Deny

## 목표

- 사용자 `MOD3_Q01_USER`에 Fine-grained S3 정책 적용
- `reports/` 경로 읽기 허용 + 삭제 명시적 거부 + TLS 강제
- 사용자 프로파일로 실제 호출 성공/실패를 모두 검증

---

## 1) CloudShell 준비

```bash
export AWS_REGION="ap-northeast-2"
export ACCOUNT_ID="123456789012"
export DATA_BUCKET="YOUR_DATA_BUCKET"
export SAMPLE_FILE="sample.txt"

export USER_NAME="MOD3_Q01_USER"
export POLICY_NAME="MOD3_Q01_POLICY"
export PROFILE_NAME="mod3-q01-user"
```

---

## 2) 정책 JSON 작성

```bash
cp module3/policies/q01-s3-prefix-readonly-with-explicit-deny.json /tmp/mod3-q01-policy.json
sed -i "s/YOUR_DATA_BUCKET/$DATA_BUCKET/g" /tmp/mod3-q01-policy.json
```

---

## 3) IAM 생성 및 정책 연결

```bash
aws iam create-user --user-name "$USER_NAME"

aws iam create-policy \
  --policy-name "$POLICY_NAME" \
  --policy-document file:///tmp/mod3-q01-policy.json

aws iam attach-user-policy \
  --user-name "$USER_NAME" \
  --policy-arn "arn:aws:iam::$ACCOUNT_ID:policy/$POLICY_NAME"
```

---

## 4) 액세스 키 + 프로파일 전환

```bash
aws iam create-access-key --user-name "$USER_NAME"
```

반환된 `AccessKeyId`, `SecretAccessKey`로 프로파일 구성:

```bash
aws configure --profile "$PROFILE_NAME"
```

신분 확인:

```bash
aws sts get-caller-identity --profile "$PROFILE_NAME"
```

---

## 5) 검증 (핵심)

```bash
# 성공 기대: reports prefix listing
aws s3 ls "s3://$DATA_BUCKET/reports/" --profile "$PROFILE_NAME"

# 성공 기대: reports object read
aws s3 cp "s3://$DATA_BUCKET/reports/$SAMPLE_FILE" - --profile "$PROFILE_NAME"

# 실패 기대: explicit deny delete
aws s3 rm "s3://$DATA_BUCKET/reports/$SAMPLE_FILE" --profile "$PROFILE_NAME"
```

마지막 명령은 `AccessDenied`가 나와야 정답.

---

## 6) 시뮬레이터 교차검증 (선택)

```bash
aws iam simulate-principal-policy \
  --policy-source-arn "arn:aws:iam::$ACCOUNT_ID:user/$USER_NAME" \
  --action-names s3:ListBucket s3:GetObject s3:DeleteObject \
  --resource-arns "arn:aws:s3:::$DATA_BUCKET" "arn:aws:s3:::$DATA_BUCKET/reports/$SAMPLE_FILE"
```

---

## 7) Console 경로

- IAM Console → Users → `MOD3_Q01_USER` → Permissions
- IAM Console → Policies → `MOD3_Q01_POLICY` JSON 검토
- S3 Console → `DATA_BUCKET/reports/`에서 read/delete 결과 확인

---

## 8) 감점 방지 포인트

- `ListBucket` 리소스를 오브젝트 ARN으로 쓰면 오답
- `s3:prefix` 조건 누락 시 버킷 전체 리스트 가능해져 감점
- Delete Deny는 Allow보다 우선이므로, 실검증에서 반드시 `rm` 실패를 보여줘야 안전
