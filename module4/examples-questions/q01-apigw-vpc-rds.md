# Q01: 서버리스 REST API로 사원 정보 조회 시스템 구축

**난이도: 중** | 관련 시나리오: S01

---

## 문제 설명

다음 환경이 사전 구성되어 있습니다:
- VPC: public subnet 2개, private subnet 2개
- RDS MySQL 인스턴스: private subnet에서 실행 중 (엔드포인트, 사용자명, 비밀번호 제공)

위 환경을 활용하여 API Gateway + Lambda + RDS MySQL 기반의 사원 정보 REST API를 구축하세요.

---

## 요구사항

1. Lambda 함수는 VPC private subnet에 배치할 것
2. Lambda는 pymysql을 사용하여 RDS MySQL에 연결할 것 (Layer 패키징 필요)
3. API Gateway REST API를 생성하고 다음 엔드포인트를 구현할 것:
   - `GET /employees` — 전체 사원 목록 조회
   - `POST /employees` — 신규 사원 등록
4. 보안 그룹을 최소 권한 원칙으로 구성할 것 (소스로 `0.0.0.0/0` 사용 금지)
5. Lambda 실행 역할에 필요한 최소 권한만 부여할 것
6. Lambda 코드에서 모듈 레벨 커넥션 재사용 패턴을 적용할 것
7. DB 연결 정보는 환경변수로 관리할 것

---

## 필요한 AWS 서비스

VPC, EC2 Security Group, Lambda, Lambda Layer, API Gateway, RDS, IAM

---

## 예상 함정

- Lambda SG 아웃바운드와 RDS SG 인바운드 규칙이 SG ID 참조로 연결되어야 함 (IP 범위 사용 감점)
- `AWSLambdaVPCAccessExecutionRole` 관리형 정책 없으면 ENI 생성 실패로 Lambda 배포 불가
- pymysql Layer 패키징 시 zip 내부 `python/` 디렉토리 구조 필수
- 커넥션을 핸들러 내부에 생성하면 매 호출마다 새 연결 생성 → 모듈 레벨에 선언하여 재사용
- API Gateway Lambda 프록시 통합 사용 시 응답 형식이 `{statusCode, headers, body}` 구조여야 함
