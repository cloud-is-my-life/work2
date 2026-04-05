# Module 3 확장 실전 케이스 (Fine-grained IAM)

기존 `examples-questions/`는 유지하고, 경기 변수 대응용으로 리소스별 케이스를 추가한 디렉토리입니다.

> 원칙: **CloudShell 복붙 가능** + **Console 재현 가능** + **Allow/AccessDenied 검증 명령 포함**

---

## 구성

| 리소스 | 디렉토리 | 핵심 포인트 |
|---|---|---|
| DynamoDB | [dynamodb/](./dynamodb/) | `LeadingKeys`, `Attributes`, Scan 우회 차단 |
| S3 | [s3/](./s3/) | Prefix 최소권한, Explicit Deny, TLS/ACL/IP 제어 |
| EC2 | [ec2/](./ec2/) | 태그 기반 제어, `RunInstances` 조건, EBS 암호화 강제 |
| Secrets Manager | [secrets-manager/](./secrets-manager/) | Secret ARN 범위, VersionStage, 삭제 차단, CMK 강제 |
| SSM Parameter Store | [ssm-parameter-store/](./ssm-parameter-store/) | 경로 기반 권한, Overwrite/Delete 차단, SecureString 제어 |
| KMS | [kms/](./kms/) | Key policy + IAM 조합, `kms:ViaService`, EncryptionContext |
| ECR | [ecr/](./ecr/) | Push/Pull 분리, 이미지 삭제 차단, repo policy |
| CloudWatch Logs | [cloudwatch-logs/](./cloudwatch-logs/) | LogGroup 범위 제어, 삭제/보존기간 변경 통제 |
| SQS | [sqs/](./sqs/) | Producer/Consumer 분리, Queue policy, KMS, DLQ |
| SNS | [sns/](./sns/) | Topic publish/subscribe 분리, Protocol 제한, cross-account topic policy |
| Lambda | [lambda/](./lambda/) | invoke 제한, PassRole 최소권한, VPC 제약, Resource-based Policy |
| IAM | [iam/](./iam/) | Delegated IAM, Permissions Boundary 강제, PassRole 제어, 권한 상승 차단 |

---

## 공통 CloudShell 변수

```bash
export AWS_REGION="ap-northeast-2"
export ACCOUNT_ID="123456789012"
export USER_NAME="mod3-lab-user"
export PROFILE_NAME="mod3-lab-user"
```

사용자 생성/정책 연결 공통 템플릿:

```bash
aws iam create-user --user-name "$USER_NAME"

aws iam create-policy \
  --policy-name "MOD3_LAB_POLICY" \
  --policy-document file://POLICY_FILE.json

aws iam attach-user-policy \
  --user-name "$USER_NAME" \
  --policy-arn "arn:aws:iam::$ACCOUNT_ID:policy/MOD3_LAB_POLICY"

aws iam create-access-key --user-name "$USER_NAME"
aws configure --profile "$PROFILE_NAME"
aws sts get-caller-identity --profile "$PROFILE_NAME"
```

---

## 권장 검증 루틴

1. `simulate-principal-policy`로 1차 확인
2. 같은 시나리오를 실제 API 호출로 재검증
3. 성공/실패(AccessDenied) 둘 다 증빙

```bash
aws iam simulate-principal-policy \
  --policy-source-arn "arn:aws:iam::$ACCOUNT_ID:user/$USER_NAME" \
  --action-names ACTION_1 ACTION_2 \
  --resource-arns RESOURCE_ARN_1 RESOURCE_ARN_2
```

---

## 감점 방지 공통 체크

- `List*` 계열은 `Resource:"*"`가 필요한 API가 많음(서비스별 차이 확인 필수)
- ABAC는 태그 누락 시 실패하므로 `Null` 기반 Deny를 함께 고려
- 리소스 ARN과 Condition key는 서비스별 대소문자/형식 정확히 맞춰야 함
- Deny를 넣었다면 실제 `AccessDenied`까지 검증해야 점수 안정적
