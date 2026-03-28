# 시나리오 3: Lambda + RDS Proxy + IAM Auth

> 출제 가능성: **높음** | 난이도: **중상**

---

## 아키텍처 구성

```
Lambda Function
  [VPC: Private Subnet]
  |
  | generate_db_auth_token() → IAM 토큰 생성 (15분 유효)
  |
  v (port 3306, SSL 필수)
RDS Proxy
  [VPC: Private Subnet, 최소 2개 AZ 서브넷]
  |
  | (Secrets Manager에서 실제 자격증명 조회)
  v
RDS MySQL
  [VPC: Private Subnet]
```

---

## 출제 의도

- 가장 정교한 인증 패턴으로 IAM 기반 DB 접근 제어 이해도 측정
- RDS Proxy의 커넥션 풀링 이점과 설정 복잡도 동시 평가
- SSL/TLS 강제 적용 등 보안 심화 지식 검증

---

## 왜 현실적인 문제인가

- 대규모 서버리스 환경에서 커넥션 풀 고갈 방지를 위해 RDS Proxy는 필수
- IAM 인증은 자격증명 로테이션 없이 보안 유지 가능한 현대적 패턴
- 실무 아키텍처 설계 능력을 종합적으로 평가

---

## 참가자가 자주 틀리는 포인트

1. **`rds-db:connect` vs `rds:connect` 혼동** — IAM 정책에서 반드시 `rds-db:connect` (하이픈 포함)를 사용해야 함. `rds:connect`는 존재하지 않는 권한.

2. **Resource ARN에 인스턴스 ID 사용** — `rds-db:connect`의 Resource ARN 형식:
   ```
   arn:aws:rds-db:REGION:ACCOUNT_ID:dbuser:RESOURCE_ID/USERNAME
   ```
   `RESOURCE_ID`는 `prx-xxxxxxxxxx` (Proxy의 경우) 또는 `db-XXXXXXXXXX` (인스턴스)이며, 인스턴스 식별자(my-db)가 아님.
   ```bash
   # Proxy Resource ID 확인 (ARN 마지막 부분 prx-xxxx)
   aws rds describe-db-proxies --db-proxy-name my-proxy \
     --query "DBProxies[0].DBProxyArn"
   ```

3. **SSL 미설정** — IAM 인증은 SSL이 필수. pymysql에서 `ssl={"use": True}` 없이 연결하면 인증 실패.

4. **generate_db_auth_token 호스트명 불일치** — 토큰 생성 시 사용한 hostname이 실제 연결 hostname과 정확히 일치해야 함. Proxy 엔드포인트를 사용해야 하는데 RDS 엔드포인트를 사용하면 토큰 검증 실패.

5. **Connection Pinning 발생** — `SET` 명령, 임시 테이블(`CREATE TEMPORARY TABLE`), `LOCK TABLE` 사용 시 Proxy의 멀티플렉싱이 비활성화되어 커넥션 풀링 효과 없어짐.

6. **RDS Proxy 서브넷 1개만 지정** — Proxy는 최소 2개의 서로 다른 AZ에 있는 서브넷이 필요. 1개만 지정하면 생성 실패.

---

## 디버깅 포인트

**Proxy 상태 확인:**
```bash
aws rds describe-db-proxies --db-proxy-name my-proxy \
  --query "DBProxies[0].{Status:Status,Endpoint:Endpoint,RequireTLS:RequireTLS}"
```

**IAM 토큰 생성 테스트:**
```bash
aws rds generate-db-auth-token \
  --hostname my-proxy.proxy-xxxx.ap-northeast-2.rds.amazonaws.com \
  --port 3306 \
  --region ap-northeast-2 \
  --username lambda_user
```

**DB 사용자 생성 (RDS에 직접 접속 후):**
```sql
CREATE USER 'lambda_user'@'%' IDENTIFIED WITH AWSAuthenticationPlugin AS 'RDS';
GRANT SELECT, INSERT, UPDATE, DELETE ON mydb.* TO 'lambda_user'@'%';
FLUSH PRIVILEGES;
```

**IAM 정책 예시:**
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": "rds-db:connect",
    "Resource": "arn:aws:rds-db:ap-northeast-2:ACCOUNT_ID:dbuser:prx-PROXY_RESOURCE_ID/lambda_user"
  }]
}
```

**CloudWatch Logs 패턴:**
- `SSL connection error` → ssl 파라미터 누락
- `Access denied for user` → rds-db:connect ARN 오류 또는 DB 사용자 미생성
- `Proxy is not available` → Proxy 상태가 available이 아님
- `IAM authentication failed` → 토큰 만료(15분) 또는 ARN 불일치

---

## 풀이 우선순위

1. **(5분) RDS Proxy 확인** — 상태(available), 엔드포인트, Resource ID 메모
2. **(8분) DB 사용자 생성** — RDS에 직접 접속하여 AWSAuthenticationPlugin 사용자 생성
3. **(7분) Lambda 역할에 rds-db:connect 정책 추가** — ARN 형식 정확히 입력
4. **(5분) Lambda 코드 작성** — IAM 토큰 생성 + SSL 연결
5. **(5분) 테스트** — 토큰 생성 CLI 테스트 후 Lambda 실행

→ 참고 코드: `code-templates/conn-iam-proxy.py`
