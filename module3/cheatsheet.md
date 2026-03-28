# Module 3 Cheatsheet — Fine-grained IAM

## 1) 정책 평가 우선순위 (암기용)

1. 인증 성공(Principal 식별)
2. 명시적 Deny 탐색
3. Identity-based + Resource-based Allow 합집합 계산
4. Permissions Boundary / SCP / Session Policy 교집합 적용
5. 최종 Allow 아니면 Implicit Deny

---

## 2) 자주 쓰는 Condition Key / Operator

| 분류 | 키/연산자 | 실전 용도 |
|---|---|---|
| 전송 보안 | `aws:SecureTransport` + `Bool` | HTTP 차단 (TLS 강제) |
| 주체 태그 | `aws:PrincipalTag/KEY` + `StringEquals` | ABAC 분기 |
| 리소스 태그 | `aws:ResourceTag/KEY` + `StringEquals` | 리소스 라벨 기반 통제 |
| 시간 | `aws:CurrentTime` + `DateGreaterThan/DateLessThan` | 기간 제한 |
| CIDR | `aws:SourceIp` + `IpAddress/NotIpAddress` | 원천 IP 제한 |
| Null 체크 | `Null` | 컨텍스트 키 누락 차단 |
| 다중 값 | `ForAnyValue` / `ForAllValues` | 배열형 컨텍스트 검증 |

---

## 3) ABAC 패턴 (복붙 템플릿)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyIfTeamTagMissing",
      "Effect": "Deny",
      "Action": "s3:*",
      "Resource": "*",
      "Condition": {
        "Null": {
          "aws:PrincipalTag/Team": "true"
        }
      }
    },
    {
      "Sid": "AllowTeamHomePrefixOnly",
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket"
      ],
      "Resource": "arn:aws:s3:::DATA_BUCKET",
      "Condition": {
        "StringLike": {
          "s3:prefix": "home/${aws:PrincipalTag/Team}/*"
        }
      }
    },
    {
      "Sid": "AllowTeamObjects",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject"
      ],
      "Resource": "arn:aws:s3:::DATA_BUCKET/home/${aws:PrincipalTag/Team}/*"
    }
  ]
}
```

> `DATA_BUCKET`은 실제 버킷명으로 치환.

---

## 4) CloudShell 검증 루틴 (5분)

```bash
export AWS_REGION="ap-northeast-2"
export ACCOUNT_ID="123456789012"
export DATA_BUCKET="YOUR_DATA_BUCKET"
export USER_NAME="mod3-test-user"
export PROFILE_NAME="mod3-test-user"
```

### (1) 현재 신분 확인

```bash
aws sts get-caller-identity
```

### (2) 사용자 키 발급 후 프로파일 전환

```bash
aws iam create-access-key --user-name "$USER_NAME"
aws configure --profile "$PROFILE_NAME"
aws sts get-caller-identity --profile "$PROFILE_NAME"
```

### (3) Allow / Deny 동시 확인

```bash
# Allow 기대
aws s3 ls "s3://$DATA_BUCKET/home/analytics/" --profile "$PROFILE_NAME"

# Deny 기대
aws s3 ls "s3://$DATA_BUCKET/home/finance/" --profile "$PROFILE_NAME"
```

### (4) 정책 시뮬레이터

```bash
aws iam get-context-keys-for-principal-policy \
  --policy-source-arn "arn:aws:iam::$ACCOUNT_ID:user/$USER_NAME"

aws iam simulate-principal-policy \
  --policy-source-arn "arn:aws:iam::$ACCOUNT_ID:user/$USER_NAME" \
  --action-names s3:ListBucket s3:GetObject s3:DeleteObject \
  --resource-arns "arn:aws:s3:::$DATA_BUCKET" "arn:aws:s3:::$DATA_BUCKET/home/analytics/sample.txt"
```

---

## 5) 자주 터지는 실수

- `ListBucket`은 **버킷 ARN**(`arn:aws:s3:::BUCKET`)에 붙여야 함.
- `GetObject/PutObject/DeleteObject`는 **오브젝트 ARN**(`arn:aws:s3:::BUCKET/*`)에 붙여야 함.
- ABAC에 `${aws:PrincipalTag/...}` 넣고 사용자 태그를 안 달면 전부 Deny/ImplicitDeny 발생.
- `aws:SecureTransport` 강제 Deny 넣고 HTTP 엔드포인트 쓰면 무조건 실패.
- `iam:PassRole` 통제를 `ResourceTag`로만 설계하면 의도대로 안 막힐 수 있음(공식 문서 주의사항 확인).
