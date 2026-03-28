# Module 4 Cheatsheet — MySQL with Lambda

---

## Layer 패키징 (one-liner)

```bash
# pymysql Layer 생성 및 등록
mkdir -p /tmp/layer/python && \
pip install pymysql -t /tmp/layer/python/ -q && \
cd /tmp/layer && zip -r /tmp/pymysql-layer.zip python/ && \
aws lambda publish-layer-version \
  --layer-name pymysql-layer \
  --zip-file fileb:///tmp/pymysql-layer.zip \
  --compatible-runtimes python3.11 python3.12 \
  --query "LayerVersionArn" --output text
```

**필수: zip 내부 구조**
```
pymysql-layer.zip
└── python/           ← 이 디렉토리가 반드시 있어야 함
    └── pymysql/
        └── __init__.py ...
```

---

## 보안 그룹 패턴

### Lambda SG (sg-lambda)
| 방향 | 프로토콜 | 포트 | 소스/대상 |
|------|---------|------|---------|
| 아웃바운드 | TCP | 3306 | sg-rds (RDS SG ID) |
| 아웃바운드 | TCP | 443 | sg-vpce (Endpoint SG, Secrets Manager 사용 시) |

### RDS SG (sg-rds)
| 방향 | 프로토콜 | 포트 | 소스/대상 |
|------|---------|------|---------|
| 인바운드 | TCP | 3306 | sg-lambda (Lambda SG ID) |

### VPC Endpoint SG (sg-vpce)
| 방향 | 프로토콜 | 포트 | 소스/대상 |
|------|---------|------|---------|
| 인바운드 | TCP | 443 | sg-lambda (Lambda SG ID) |

---

## Lambda 필수 IAM 정책

| 정책 | 용도 |
|------|------|
| `AWSLambdaVPCAccessExecutionRole` | ENI 생성 (VPC 배치 필수) |
| `AWSLambdaBasicExecutionRole` | CloudWatch Logs |
| `secretsmanager:GetSecretValue` | Secrets Manager 조회 |
| `rds-db:connect` | RDS IAM 인증 (하이픈 주의) |
| `s3:GetObject` | S3 파일 읽기 (S3 트리거 시도 별도 필요) |
| `sqs:SendMessage` | SQS 메시지 전송 |
| `sns:Publish` | SNS 알림 발행 |

---

## 연결 코드 패턴 요약

### 기본 (VPC + 환경변수)
```python
import pymysql, os
_conn = None
def get_conn():
    global _conn
    if _conn is None or not _conn.open:
        _conn = pymysql.connect(host=os.environ['DB_HOST'],
            user=os.environ['DB_USER'], password=os.environ['DB_PASS'],
            database=os.environ['DB_NAME'], connect_timeout=5)
    return _conn
```

### Secrets Manager (캐싱)
```python
import boto3, json, os
_secret = None
def get_secret():
    global _secret
    if _secret is None:
        r = boto3.client('secretsmanager').get_secret_value(SecretId=os.environ['SECRET_ARN'])
        _secret = json.loads(r['SecretString'])
    return _secret
```

### RDS Proxy IAM 인증
```python
import boto3, pymysql, os
def get_conn():
    token = boto3.client('rds').generate_db_auth_token(
        DBHostname=os.environ['PROXY_ENDPOINT'], Port=3306,
        DBUsername=os.environ['DB_USER'], Region=os.environ['AWS_REGION'])
    return pymysql.connect(host=os.environ['PROXY_ENDPOINT'],
        user=os.environ['DB_USER'], password=token,
        database=os.environ['DB_NAME'], ssl={"use": True}, connect_timeout=10)
```

---

## 핵심 CLI 명령어

```bash
# Lambda VPC 설정 확인
aws lambda get-function-configuration --function-name FUNC \
  --query "{State:State,VpcConfig:VpcConfig}"

# Lambda 역할 정책 확인
aws iam list-attached-role-policies --role-name ROLE_NAME

# RDS 엔드포인트 확인
aws rds describe-db-instances --db-instance-identifier DB_ID \
  --query "DBInstances[0].Endpoint"

# RDS Proxy Resource ID 확인
aws rds describe-db-proxies --db-proxy-name PROXY_NAME \
  --query "DBProxies[0].DBProxyArn"

# VPC Endpoint 상태 확인
aws ec2 describe-vpc-endpoints \
  --filters "Name=service-name,Values=com.amazonaws.ap-northeast-2.secretsmanager" \
  --query "VpcEndpoints[0].{State:State,PrivateDns:PrivateDnsEnabled}"

# IAM 토큰 생성 테스트
aws rds generate-db-auth-token \
  --hostname PROXY_ENDPOINT --port 3306 \
  --username lambda_user --region ap-northeast-2

# SQS 큐 속성 확인
aws sqs get-queue-attributes --queue-url QUEUE_URL \
  --attribute-names VisibilityTimeout RedrivePolicy

# EventBridge 규칙 확인
aws events list-rules --query "Rules[*].{Name:Name,State:State,Schedule:ScheduleExpression}"

# Lambda 최근 로그 확인 (CloudShell)
aws logs filter-log-events \
  --log-group-name /aws/lambda/FUNC_NAME \
  --start-time $(date -d '5 minutes ago' +%s000) \
  --query "events[*].message" --output text
```

---

## EventBridge cron 표현식

| 표현식 | 의미 | 주의 |
|--------|------|------|
| `rate(5 minutes)` | 5분마다 | 단수형: `minute` |
| `rate(1 hour)` | 1시간마다 | 복수 `hours` 오류 |
| `cron(0 0 * * ? *)` | 매일 KST 09:00 (UTC 00:00) | UTC 기준 |
| `cron(0 15 * * ? *)` | 매일 KST 00:00 (UTC 15:00) | |
| `cron(0 9 ? * MON-FRI *)` | 평일 KST 18:00 | 일과 요일 동시 `*` 금지 → `?` 사용 |

---

## rds-db:connect ARN 형식

```
arn:aws:rds-db:REGION:ACCOUNT_ID:dbuser:RESOURCE_ID/DB_USERNAME
```

- `RESOURCE_ID`: `db-XXXXXXXX` (RDS 인스턴스) 또는 `prx-XXXXXXXX` (RDS Proxy)
- **인스턴스 식별자(my-db)가 아님**
- 와일드카드 가능: `arn:aws:rds-db:*:*:dbuser:*/lambda_user`

```bash
# RDS 인스턴스 Resource ID 확인
aws rds describe-db-instances --db-instance-identifier DB_ID \
  --query "DBInstances[0].DbiResourceId"
```

---

## SQS 가시성 타임아웃 계산

```
SQS VisibilityTimeout >= Lambda Timeout × 6
```

| Lambda Timeout | SQS VisibilityTimeout |
|---------------|----------------------|
| 30초 | 180초 이상 |
| 60초 | 360초 이상 |
| 300초 | 1800초 이상 |

---

## 빠른 멱등성 패턴

```sql
-- UNIQUE 제약 키에 중복 무시
INSERT IGNORE INTO table (unique_col, ...) VALUES (%s, ...);

-- 중복 시 UPDATE
INSERT INTO table (unique_col, val) VALUES (%s, %s)
ON DUPLICATE KEY UPDATE val = VALUES(val);
```
