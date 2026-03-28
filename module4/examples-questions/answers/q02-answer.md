# Q02 풀이: Secrets Manager 연동 보안 API 구축

---

## 풀이 힌트

1. **VPC Endpoint 생성 후 접근 테스트** — CloudShell(VPC 외부)에서 `aws secretsmanager list-secrets` 로 접근은 되지만, Lambda(VPC 내부 NAT 없음)에서는 Endpoint 없으면 타임아웃. Endpoint 생성 후 Lambda에서 테스트.

2. **Proxy Resource ID 추출 방법**:
   ```bash
   aws rds describe-db-proxies --db-proxy-name my-proxy \
     --query "DBProxies[0].DBProxyArn" --output text
   # 출력: arn:aws:rds:ap-northeast-2:123456789012:db-proxy:prx-0a1b2c3d4e5f
   # Resource ID = prx-0a1b2c3d4e5f (ARN 마지막 부분)
   ```

3. **IAM 토큰 생성 CLI로 먼저 테스트** — Lambda 코드 작성 전 CLI에서 토큰이 생성되는지 확인:
   ```bash
   aws rds generate-db-auth-token \
     --hostname PROXY_ENDPOINT --port 3306 \
     --username lambda_user --region ap-northeast-2
   ```

4. **DB에 AWSAuthenticationPlugin 사용자 확인** — RDS에 접속하여:
   ```sql
   SELECT user, plugin FROM mysql.user WHERE user = 'lambda_user';
   -- plugin이 AWSAuthenticationPlugin 이어야 함
   ```

5. **rds-db:connect 정책 작성 시 와일드카드 활용** (시간 절약):
   ```json
   {
     "Effect": "Allow",
     "Action": "rds-db:connect",
     "Resource": "arn:aws:rds-db:ap-northeast-2:ACCOUNT_ID:dbuser:prx-RESOURCE_ID/lambda_user"
   }
   ```

---

## 검증 방법

```bash
# VPC Endpoint 상태 확인
aws ec2 describe-vpc-endpoints \
  --filters "Name=service-name,Values=com.amazonaws.ap-northeast-2.secretsmanager" \
  --query "VpcEndpoints[0].{State:State,PrivateDns:PrivateDnsEnabled}"

# Proxy Resource ID 확인
aws rds describe-db-proxies --db-proxy-name my-proxy \
  --query "DBProxies[0].DBProxyArn"

# IAM 토큰 생성 테스트
aws rds generate-db-auth-token \
  --hostname PROXY_ENDPOINT \
  --port 3306 \
  --username lambda_user \
  --region ap-northeast-2

# Lambda 역할 정책 확인
aws iam list-attached-role-policies --role-name lambda-execution-role

# Lambda 실행 테스트
aws lambda invoke \
  --function-name secure-api-function \
  --payload '{"httpMethod": "GET", "path": "/employees"}' \
  --cli-binary-format raw-in-base64-out \
  /tmp/response.json && cat /tmp/response.json
```
