# Q02: Secrets Manager 연동 보안 API 구축

**난이도: 중상** | 관련 시나리오: S02, S03

---

## 문제 설명

다음 환경이 사전 구성되어 있습니다:
- VPC: private subnet 2개 (**NAT Gateway 없음**)
- RDS MySQL 인스턴스: private subnet에서 실행 중
- RDS Proxy: 생성되어 있으며 엔드포인트 제공

보안 강화를 위해 DB 자격증명을 Secrets Manager로 관리하고, RDS Proxy를 통한 IAM 인증 방식으로 연결하는 API를 구축하세요.

---

## 요구사항

1. DB 자격증명을 Secrets Manager에 JSON 형식(`{"username":..., "password":...}`)으로 저장할 것
2. NAT Gateway 없는 환경에서 Secrets Manager 접근을 위한 **VPC Interface Endpoint** 생성 (private DNS 활성화 필수)
3. Lambda는 **RDS Proxy를 통해 IAM 인증**으로 MySQL에 연결할 것
4. Lambda 실행 역할에 `rds-db:connect` 권한 부여 (올바른 ARN 형식 사용 필수)
5. SSL을 활성화하여 RDS Proxy에 연결할 것
6. Lambda 코드에서 시크릿 캐싱 패턴 구현 (매 호출마다 GetSecretValue 호출 금지)
7. API Gateway를 통해 외부에서 접근 가능하도록 구성

---

## 필요한 AWS 서비스

VPC, VPC Interface Endpoint, Lambda, API Gateway, RDS, RDS Proxy, Secrets Manager, IAM, KMS(선택)

---

## 예상 함정

- VPC Endpoint 생성 시 `--private-dns-enabled` 없으면 Lambda에서 퍼블릭 엔드포인트로 라우팅되어 타임아웃
- VPC Endpoint에 연결된 SG가 Lambda SG로부터 **443 인바운드**를 허용해야 함
- `rds-db:connect` ARN 형식: `arn:aws:rds-db:REGION:ACCOUNT_ID:dbuser:prx-RESOURCE_ID/DB_USERNAME` — 인스턴스 식별자가 아닌 **Proxy Resource ID** 사용
- `generate_db_auth_token` 호출 시 hostname은 **Proxy 엔드포인트** 사용 (RDS 엔드포인트 사용 시 토큰 검증 실패)
- IAM 인증은 **SSL 필수** (`ssl={"use": True}` 없으면 연결 거부)
- RDS DB에 `IDENTIFIED WITH AWSAuthenticationPlugin AS 'RDS'` 사용자가 생성되어 있어야 함
