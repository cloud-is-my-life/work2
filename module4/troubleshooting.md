# Module 4 Troubleshooting — MySQL with Lambda

> CloudWatch Logs 오류 패턴, 원인, 해결책 모음

---

## CloudWatch Logs 오류 패턴

| 오류 메시지 | 원인 | 해결책 |
|-----------|------|--------|
| `Task timed out after X seconds` | SG 인바운드 차단, 서브넷 라우팅 문제, 또는 타임아웃이 너무 짧음 | RDS SG 인바운드 3306 확인, Lambda 타임아웃 증가 |
| `[Errno 110] Connection timed out` | RDS SG에서 Lambda SG 허용 안 됨 | RDS SG 인바운드 → Lambda SG 3306 허용 |
| `ModuleNotFoundError: No module named 'pymysql'` | Layer 미연결 또는 zip 구조 오류 | Layer 재패키징(`python/` 디렉토리), Lambda에 Layer 연결 |
| `Could not connect to the endpoint URL` | VPC Endpoint 없거나 private DNS 비활성화 | Endpoint 생성 시 `--private-dns-enabled` |
| `EndpointConnectionError` | VPC Endpoint 없음 또는 Endpoint SG에 443 미허용 | sg-vpce에 Lambda SG → 443 인바운드 허용 |
| `AccessDeniedException: secretsmanager` | Lambda 역할에 `secretsmanager:GetSecretValue` 없음 | IAM 정책 추가 |
| `ResourceNotFoundException` | 시크릿 이름 또는 ARN 오타 | `aws secretsmanager list-secrets` 로 이름 확인 |
| `SSL connection error` | IAM 인증 시 `ssl={"use": True}` 누락 | pymysql 연결 시 ssl 파라미터 추가 |
| `Access denied for user` | rds-db:connect ARN 오류 또는 DB 사용자 미생성 | ARN의 Resource ID 확인, DB에서 사용자 생성 |
| `Proxy is not available` | RDS Proxy 상태가 available 아님 | Proxy 상태가 available 될 때까지 대기 |
| `IAM authentication failed` | 토큰 만료(15분) 또는 hostname 불일치 | 토큰 생성 hostname = 연결 hostname 동일해야 함 |
| `UnicodeDecodeError` | CSV 파일 인코딩 문제 (BOM 포함 UTF-8, EUC-KR) | `.decode('utf-8-sig')` 또는 `encoding='euc-kr'` |
| `Duplicate entry` | 멱등성 처리 없이 중복 데이터 삽입 | `INSERT IGNORE` 또는 `ON DUPLICATE KEY UPDATE` |
| `AuthorizationError: sns:Publish` | Lambda 역할에 `sns:Publish` 없음 | IAM 정책에 SNS Publish 추가 |
| `Lost connection to MySQL server` | RDS Multi-AZ 장애 조치 중 연결 끊김 | `ping(reconnect=True)` 재연결 로직 추가 |

---

## Lambda 배포/실행 상태 진단

```bash
# Lambda 함수 상태 확인 (VPC 배치 시 Pending 될 수 있음)
aws lambda get-function-configuration --function-name FUNC_NAME \
  --query "{State:State,StateReason:StateReason,VpcConfig:VpcConfig}"

# Lambda 최근 실행 로그
aws logs filter-log-events \
  --log-group-name /aws/lambda/FUNC_NAME \
  --start-time $(date -d '5 minutes ago' +%s000) \
  --query "events[*].message" --output text

# Lambda 리소스 기반 정책 확인 (S3/EventBridge 호출 권한)
aws lambda get-policy --function-name FUNC_NAME \
  --query "Policy" | python3 -m json.tool
```

---

## 보안 그룹 진단

```bash
# Lambda SG 아웃바운드 규칙 확인
aws ec2 describe-security-groups --group-ids sg-LAMBDA_ID \
  --query "SecurityGroups[0].IpPermissionsEgress"

# RDS SG 인바운드 규칙 확인
aws ec2 describe-security-groups --group-ids sg-RDS_ID \
  --query "SecurityGroups[0].IpPermissions"

# VPC Endpoint SG 인바운드 확인
aws ec2 describe-security-groups --group-ids sg-VPCE_ID \
  --query "SecurityGroups[0].IpPermissions"
```

---

## IAM 권한 진단

```bash
# Lambda 역할 부착된 정책 목록
aws iam list-attached-role-policies --role-name ROLE_NAME

# 인라인 정책 확인
aws iam list-role-policies --role-name ROLE_NAME
aws iam get-role-policy --role-name ROLE_NAME --policy-name POLICY_NAME

# rds-db:connect 정책 확인
aws iam get-role-policy --role-name ROLE_NAME --policy-name rds-connect-policy
```

---

## RDS / RDS Proxy 진단

```bash
# RDS 인스턴스 상태 및 엔드포인트
aws rds describe-db-instances --db-instance-identifier DB_ID \
  --query "DBInstances[0].{Status:DBInstanceStatus,Endpoint:Endpoint,MultiAZ:MultiAZ}"

# RDS Proxy 상태 및 엔드포인트
aws rds describe-db-proxies --db-proxy-name PROXY_NAME \
  --query "DBProxies[0].{Status:Status,Endpoint:Endpoint,TLS:RequireTLS}"

# RDS Proxy Resource ID (rds-db:connect ARN 작성에 필요)
aws rds describe-db-proxies --db-proxy-name PROXY_NAME \
  --query "DBProxies[0].DBProxyArn"
# ARN 마지막 부분: prx-xxxxxxxxxx

# RDS 이벤트 확인 (장애 조치 등)
aws rds describe-events \
  --source-identifier DB_ID --source-type db-instance --duration 60
```

---

## VPC Endpoint 진단

```bash
# Secrets Manager Endpoint 확인
aws ec2 describe-vpc-endpoints \
  --filters "Name=service-name,Values=com.amazonaws.ap-northeast-2.secretsmanager" \
  --query "VpcEndpoints[*].{State:State,PrivateDns:PrivateDnsEnabled,SGs:Groups}"

# Endpoint 생성 (누락 시)
aws ec2 create-vpc-endpoint \
  --vpc-id VPC_ID \
  --vpc-endpoint-type Interface \
  --service-name com.amazonaws.ap-northeast-2.secretsmanager \
  --subnet-ids subnet-PRIVATE1 subnet-PRIVATE2 \
  --security-group-ids sg-VPCE_ID \
  --private-dns-enabled
```

---

## S3 이벤트 / Lambda 트리거 진단

```bash
# S3 이벤트 알림 설정 확인
aws s3api get-bucket-notification-configuration --bucket BUCKET_NAME

# Lambda Event Source Mapping (SQS 트리거) 확인
aws lambda list-event-source-mappings --function-name FUNC_NAME \
  --query "EventSourceMappings[*].{State:State,BatchSize:BatchSize,FunctionResponseTypes:FunctionResponseTypes}"
```

---

## SQS 진단

```bash
# SQS 큐 설정 확인 (가시성 타임아웃, DLQ)
aws sqs get-queue-attributes \
  --queue-url QUEUE_URL \
  --attribute-names VisibilityTimeout RedrivePolicy

# DLQ 메시지 수 확인
aws sqs get-queue-attributes \
  --queue-url DLQ_URL \
  --attribute-names ApproximateNumberOfMessages
```

---

## CloudFormation/SAM 진단

```bash
# 스택 상태 및 실패 원인
aws cloudformation describe-stacks --stack-name STACK_NAME \
  --query "Stacks[0].{Status:StackStatus,Reason:StackStatusReason}"

# CREATE_FAILED 이벤트만 필터
aws cloudformation describe-stack-events --stack-name STACK_NAME \
  --query "StackEvents[?ResourceStatus=='CREATE_FAILED'].{Resource:LogicalResourceId,Reason:ResourceStatusReason}"

# 스택 출력값 확인
aws cloudformation describe-stacks --stack-name STACK_NAME \
  --query "Stacks[0].Outputs"
```

---

## 자주 발생하는 복합 문제

### 증상: Lambda가 실행은 되는데 DB 연결 타임아웃
체크 순서:
1. Lambda가 private subnet에 있는가?
2. Lambda 실행 역할에 `AWSLambdaVPCAccessExecutionRole` 있는가?
3. RDS SG 인바운드에 Lambda SG → 3306 있는가?
4. Lambda SG 아웃바운드가 막혀 있지 않은가? (기본값은 열려 있음)
5. Lambda와 RDS가 같은 VPC에 있는가?

### 증상: Secrets Manager 접근 타임아웃
체크 순서:
1. VPC Interface Endpoint 생성되어 있는가?
2. Endpoint에 private DNS 활성화되어 있는가?
3. Endpoint SG에 Lambda SG → 443 인바운드 있는가?
4. Lambda 역할에 `secretsmanager:GetSecretValue` 있는가?

### 증상: IAM 인증 실패 (RDS Proxy)
체크 순서:
1. `rds-db:connect` (하이픈) vs `rds:connect` 오타 없는가?
2. ARN의 Resource ID가 `prx-xxxx` 형식인가? (인스턴스 ID 아님)
3. ARN의 DB_USERNAME이 DB에 실제 생성된 사용자와 일치하는가?
4. SSL 설정(`ssl={"use": True}`) 있는가?
5. 토큰 생성 hostname과 연결 hostname이 동일한가?
6. DB에 `IDENTIFIED WITH AWSAuthenticationPlugin` 사용자가 생성되어 있는가?
