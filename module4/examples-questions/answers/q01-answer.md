# Q01 풀이: 서버리스 REST API로 사원 정보 조회 시스템 구축

---

## 풀이 힌트

1. **SG 설정을 가장 먼저 완료** — Lambda SG(아웃바운드 3306 → RDS SG), RDS SG(인바운드 3306 from Lambda SG). SG ID 참조 방식 사용.

2. **Lambda 역할은 관리형 정책 2개** — `AWSLambdaBasicExecutionRole` + `AWSLambdaVPCAccessExecutionRole`. VPC 권한 없으면 Lambda 상태가 `Pending` 에서 `Failed`로 전환됨.

3. **Layer 패키징 전에 구조 확인** — `zip -r layer.zip python/` 명령 전에 `python/` 디렉토리가 맞는지 확인.

4. **Lambda 코드 작성 전 SELECT 1 테스트** — 연결 자체가 먼저 되는지 확인 후 비즈니스 로직 작성. 타임아웃이 발생하면 SG 문제일 확률이 높음.

5. **employees 테이블 DDL 먼저 실행** — Lambda 코드 작성 전 RDS에 접속하여 테이블 생성.
   ```sql
   CREATE TABLE employees (
     id INT AUTO_INCREMENT PRIMARY KEY,
     name VARCHAR(100) NOT NULL,
     email VARCHAR(100) UNIQUE NOT NULL,
     dept VARCHAR(50),
     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
   );
   ```

6. **API Gateway는 Lambda 프록시 통합** — 가장 빠른 방법. Lambda 응답 형식:
   ```python
   return {
       "statusCode": 200,
       "headers": {"Content-Type": "application/json"},
       "body": json.dumps(result, ensure_ascii=False, default=str)
   }
   ```

---

## 검증 방법

```bash
# API 엔드포인트 확인
API_ID=$(aws apigateway get-rest-apis \
  --query "items[?name=='employees-api'].id" --output text)
echo "https://${API_ID}.execute-api.ap-northeast-2.amazonaws.com/prod"

# GET /employees 테스트
curl -s https://${API_ID}.execute-api.ap-northeast-2.amazonaws.com/prod/employees

# POST /employees 테스트
curl -s -X POST \
  https://${API_ID}.execute-api.ap-northeast-2.amazonaws.com/prod/employees \
  -H 'Content-Type: application/json' \
  -d '{"name": "홍길동", "email": "hong@example.com", "dept": "개발팀"}'

# Lambda VPC 설정 확인
aws lambda get-function-configuration --function-name employees-function \
  --query "{VpcId:VpcConfig.VpcId,Subnets:VpcConfig.SubnetIds,SGs:VpcConfig.SecurityGroupIds}"

# RDS SG 인바운드 규칙 확인
aws ec2 describe-security-groups \
  --filters "Name=group-name,Values=sg-rds" \
  --query "SecurityGroups[0].IpPermissions"
```
