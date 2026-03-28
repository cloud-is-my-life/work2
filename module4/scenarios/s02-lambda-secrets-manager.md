# 시나리오 2: Lambda + Secrets Manager + RDS

> 출제 가능성: **높음** | 난이도: **중**

---

## 아키텍처 구성

```
Lambda Function
  [VPC: Private Subnet, NAT Gateway 없음]
  |
  |---(HTTPS 443)---> VPC Interface Endpoint
  |                   (com.amazonaws.REGION.secretsmanager)
  |                         |
  |                         v
  |                   Secrets Manager
  |                   (DB 자격증명 저장)
  |
  v (port 3306)
RDS MySQL
  [VPC: Private Subnet]
```

---

## 출제 의도

- 하드코딩된 자격증명 대신 Secrets Manager를 통한 보안 강화 패턴 이해
- VPC 내 프라이빗 서비스 접근을 위한 VPC Interface Endpoint 구성 능력 평가
- 실무에서 필수인 시크릿 관리 패턴 검증

---

## 왜 현실적인 문제인가

- 보안 감사에서 하드코딩 자격증명은 즉시 지적 사항
- VPC Endpoint는 비용 절감 + 보안 강화로 실무 필수 지식
- 1시간 내 구성 가능한 적절한 복잡도

---

## 참가자가 자주 틀리는 포인트

1. **VPC Endpoint 미생성** — NAT Gateway 없는 private subnet의 Lambda는 퍼블릭 Secrets Manager 엔드포인트에 접근 불가. `com.amazonaws.REGION.secretsmanager` Interface Endpoint 필수.

2. **Private DNS 미활성화** — VPC Endpoint 생성 시 `--private-dns-enabled` 를 빠뜨리면 Lambda 코드에서 `secretsmanager.REGION.amazonaws.com` 호출이 퍼블릭 IP로 라우팅되어 타임아웃 발생.

3. **VPC Endpoint SG에 HTTPS 미허용** — Endpoint에 연결된 SG가 Lambda SG로부터 443 포트 인바운드를 허용하지 않으면 연결 거부.

4. **Secret JSON 형식 오류** — Secrets Manager에 저장된 값이 `{"username":"admin","password":"pass123"}` 형식이어야 하는데 단순 문자열로 저장하거나 키 이름이 다르면 코드에서 파싱 실패.

5. **매 호출마다 GetSecretValue 호출** — Lambda 핸들러 내부에서 매번 시크릿을 조회하면 불필요한 API 호출과 지연 발생. 모듈 레벨에서 캐싱 필수.

6. **KMS CMK 사용 시 kms:Decrypt 누락** — 시크릿을 고객 관리형 KMS 키로 암호화한 경우 Lambda 역할에 `kms:Decrypt` 권한도 필요.

---

## 디버깅 포인트

**VPC Endpoint 확인:**
```bash
aws ec2 describe-vpc-endpoints \
  --filters "Name=service-name,Values=com.amazonaws.ap-northeast-2.secretsmanager" \
  --query "VpcEndpoints[*].{State:State,PrivateDns:PrivateDnsEnabled,SGs:Groups}"
```

**CloudWatch Logs 패턴:**
- `EndpointConnectionError` → VPC Endpoint 없거나 SG 문제
- `AccessDeniedException` → Lambda 역할에 `secretsmanager:GetSecretValue` 권한 없음
- `ResourceNotFoundException` → 시크릿 이름 오타
- `Could not connect to the endpoint URL` → Private DNS 비활성화

**VPC Endpoint 생성 CLI:**
```bash
# Endpoint SG 먼저 생성 (Lambda SG로부터 443 허용)
aws ec2 create-security-group \
  --group-name sg-vpce-secretsmanager \
  --description "VPC Endpoint for Secrets Manager" \
  --vpc-id VPC_ID

aws ec2 authorize-security-group-ingress \
  --group-id sg-VPCE_SG_ID \
  --protocol tcp --port 443 \
  --source-group sg-LAMBDA_SG_ID

# Interface Endpoint 생성
aws ec2 create-vpc-endpoint \
  --vpc-id VPC_ID \
  --vpc-endpoint-type Interface \
  --service-name com.amazonaws.ap-northeast-2.secretsmanager \
  --subnet-ids subnet-PRIVATE1 subnet-PRIVATE2 \
  --security-group-ids sg-VPCE_SG_ID \
  --private-dns-enabled
```

---

## 풀이 우선순위

1. **(5분) Secrets Manager 시크릿 생성** — JSON 형식으로 DB 자격증명 저장
2. **(8분) VPC Interface Endpoint 생성** — secretsmanager 서비스, private DNS 활성화, 적절한 SG 연결
3. **(5분) Endpoint SG 규칙 설정** — Lambda SG로부터 443 인바운드 허용
4. **(5분) Lambda 역할에 권한 추가** — `secretsmanager:GetSecretValue`, 필요 시 `kms:Decrypt`
5. **(10분) Lambda 코드 작성** — 캐싱 패턴 적용, 시크릿 조회 후 DB 연결
6. **(7분) 테스트 및 검증** — CloudWatch Logs 확인

→ 참고 코드: `code-templates/conn-secrets-manager.py`
