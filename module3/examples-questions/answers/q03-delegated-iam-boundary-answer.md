# [정답] 예시 과제 3 — Delegated IAM + Permissions Boundary

## 목표

- 위임 운영자(`MOD3_Q03_DELEGATE_USER`)가 제한된 IAM 작업만 수행하도록 설계
- 새 사용자 생성 시 Boundary 필수 강제
- `AdministratorAccess` 부착 시도를 명시적으로 차단

---

## 1) CloudShell 준비

```bash
export AWS_REGION="ap-northeast-2"
export ACCOUNT_ID="123456789012"
export DATA_BUCKET="YOUR_DATA_BUCKET"

export DELEGATE_USER="MOD3_Q03_DELEGATE_USER"
export DELEGATE_POLICY_NAME="MOD3_Q03_DELEGATE_POLICY"
export BOUNDARY_POLICY_NAME="MOD3_Q03_BOUNDARY_POLICY"
export DELEGATE_PROFILE="mod3-q03-delegate"

export CHILD_OK="MOD3_Q03_CHILD_OK"
export CHILD_FAIL="MOD3_Q03_CHILD_NO_BOUNDARY"
```

---

## 2) Boundary 정책 생성

```bash
cp module3/policies/q03-boundary-readonly-s3.json /tmp/mod3-q03-boundary-policy.json
sed -i "s/YOUR_DATA_BUCKET/$DATA_BUCKET/g" /tmp/mod3-q03-boundary-policy.json

aws iam create-policy \
  --policy-name "$BOUNDARY_POLICY_NAME" \
  --policy-document file:///tmp/mod3-q03-boundary-policy.json
```

Boundary ARN:

```bash
export BOUNDARY_ARN="arn:aws:iam::$ACCOUNT_ID:policy/$BOUNDARY_POLICY_NAME"
```

---

## 3) Delegate 정책 생성

```bash
cp module3/policies/q03-delegate-policy-template.json /tmp/mod3-q03-delegate-policy.json
sed -i "s/ACCOUNT_ID/$ACCOUNT_ID/g" /tmp/mod3-q03-delegate-policy.json
sed -i "s|BOUNDARY_ARN|$BOUNDARY_ARN|g" /tmp/mod3-q03-delegate-policy.json

aws iam create-policy \
  --policy-name "$DELEGATE_POLICY_NAME" \
  --policy-document file:///tmp/mod3-q03-delegate-policy.json
```

---

## 4) Delegate 사용자 생성 및 정책 연결

```bash
aws iam create-user --user-name "$DELEGATE_USER"

aws iam attach-user-policy \
  --user-name "$DELEGATE_USER" \
  --policy-arn "arn:aws:iam::$ACCOUNT_ID:policy/$DELEGATE_POLICY_NAME"
```

액세스 키 발급 + 프로파일:

```bash
aws iam create-access-key --user-name "$DELEGATE_USER"
aws configure --profile "$DELEGATE_PROFILE"
aws sts get-caller-identity --profile "$DELEGATE_PROFILE"
```

---

## 5) 검증

### (1) Boundary 없이 CreateUser 시도 → 실패 기대

```bash
aws iam create-user \
  --user-name "$CHILD_FAIL" \
  --profile "$DELEGATE_PROFILE"
```

`AccessDenied`면 정답.

### (2) Boundary 포함 CreateUser 시도 → 성공 기대

```bash
aws iam create-user \
  --user-name "$CHILD_OK" \
  --permissions-boundary "$BOUNDARY_ARN" \
  --profile "$DELEGATE_PROFILE"
```

### (3) AdministratorAccess 부착 시도 → 실패 기대

```bash
aws iam attach-user-policy \
  --user-name "$CHILD_OK" \
  --policy-arn "arn:aws:iam::aws:policy/AdministratorAccess" \
  --profile "$DELEGATE_PROFILE"
```

### (4) ReadOnly 정책 부착 시도 → 성공 기대

```bash
aws iam attach-user-policy \
  --user-name "$CHILD_OK" \
  --policy-arn "arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess" \
  --profile "$DELEGATE_PROFILE"
```

---

## 6) Console 경로

- IAM Console → Policies → Boundary/Delegate 정책 JSON 확인
- IAM Console → Users → `MOD3_Q03_DELEGATE_USER` 권한 확인
- IAM Console → Users → `MOD3_Q03_CHILD_OK`의 Permissions boundary 확인

---

## 7) 감점 방지 포인트

- `iam:PermissionsBoundary` Condition ARN 오타가 가장 흔한 실패 원인
- `AttachUserPolicy` 허용문만 두고 Deny를 안 넣으면 Admin 정책 차단 실패 가능
- `iam:PassRole`이 필요한 과제라면 Resource 범위를 Role ARN으로 좁혀서 설계(공식 권고)
