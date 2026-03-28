# 시나리오 1: API GW + Lambda(VPC) + RDS Private

> 출제 가능성: **매우 높음** | 난이도: **중**

---

## 아키텍처 구성

```
Client
  |
  v
API Gateway (REST API)
  |
  v
Lambda Function
  [VPC: Private Subnet, SG: sg-lambda]
  |
  v (port 3306)
RDS MySQL
  [VPC: Private Subnet, SG: sg-rds]
```

---

## 출제 의도

- VPC 내 Lambda 배치와 보안 그룹 연동의 이해도 측정
- 네트워크 레이어(서브넷, SG, 라우팅)와 Lambda 실행 역할의 통합 구성 능력 평가
- 가장 기본적인 서버리스 + 관계형 DB 패턴으로 실무 직결

---

## 왜 현실적인 문제인가

- 1시간 내 완성 가능한 최소 구성
- API Gateway + Lambda + RDS는 실무에서 가장 흔한 서버리스 패턴
- Associate 수준에서 반드시 알아야 할 VPC 네트워킹 기초 포함

---

## 참가자가 자주 틀리는 포인트

1. **Lambda를 public subnet에 배치** — Lambda는 VPC 연결 시 public IP를 받지 않음. public subnet에 넣어도 인터넷 접근 불가, RDS 접근도 SG 설정에 따라 달라짐. Lambda는 반드시 **private subnet**에 배치.

2. **RDS SG 인바운드 규칙 누락** — RDS 보안 그룹에 Lambda SG로부터 3306 포트 인바운드를 허용하지 않으면 연결 타임아웃 발생. IP 범위(0.0.0.0/0)로 열면 보안 감점.

3. **Lambda 실행 역할에 VPC 권한 누락** — `AWSLambdaVPCAccessExecutionRole` 관리형 정책 또는 `ec2:CreateNetworkInterface`, `ec2:DescribeNetworkInterfaces`, `ec2:DeleteNetworkInterface` 권한이 없으면 Lambda가 ENI를 생성하지 못해 배포 실패.

4. **VPC DNS 설정 미확인** — `enableDnsSupport=true`, `enableDnsHostnames=true` 가 비활성화된 VPC에서는 RDS 엔드포인트 DNS 해석 실패. 기본값은 활성화지만 커스텀 VPC에서 꺼져 있을 수 있음.

5. **pymysql 미패키징** — Lambda 기본 런타임에는 pymysql이 없음. Layer 또는 배포 패키지에 포함하지 않으면 `ModuleNotFoundError` 발생.

---

## 디버깅 포인트

**Lambda 배포 실패 시:**
```bash
aws lambda get-function-configuration --function-name my-function \
  --query "{State:State,StateReason:StateReason,VpcConfig:VpcConfig}"
```

**RDS SG 인바운드 확인:**
```bash
aws ec2 describe-security-groups --group-ids sg-RDS_SG_ID \
  --query "SecurityGroups[0].IpPermissions"
```

**CloudWatch Logs 패턴:**
- `Task timed out after X seconds` → SG 인바운드 규칙 또는 서브넷 라우팅 문제
- `[Errno 110] Connection timed out` → RDS SG에서 Lambda SG 허용 안 됨
- `ModuleNotFoundError: No module named pymysql` → Layer 미설치

---

## 풀이 우선순위

1. **(5분) 보안 그룹 생성** — Lambda용 SG(아웃바운드 3306 → RDS SG), RDS용 SG(인바운드 3306 from Lambda SG)
2. **(5분) Lambda 실행 역할 생성** — `AWSLambdaVPCAccessExecutionRole` + `AWSLambdaBasicExecutionRole`
3. **(10분) Lambda Layer 생성** — pymysql 패키징 후 Layer 등록
4. **(10분) Lambda 함수 생성** — VPC/서브넷/SG 설정, 환경변수(DB_HOST, DB_USER, DB_PASS, DB_NAME)
5. **(5분) SELECT 1 테스트** — 연결 확인 후 비즈니스 로직 작성
6. **(10분) API Gateway 생성** — REST API, 리소스/메서드 생성, Lambda 프록시 통합
7. **(5분) 검증** — curl 또는 콘솔에서 API 호출 테스트

→ 참고 코드: `code-templates/conn-basic.py`
