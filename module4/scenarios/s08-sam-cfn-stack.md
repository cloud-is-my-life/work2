# 시나리오 8: CloudFormation/SAM 전체 스택 배포

> 출제 가능성: **중간** | 난이도: **상**

---

## 아키텍처 구성

```
SAM Template (template.yaml)
  |
  |-- AWS::Serverless::Function (Lambda)
  |     [VpcConfig, Layers, Environment]
  |
  |-- AWS::Serverless::LayerVersion (pymysql)
  |
  |-- AWS::RDS::DBInstance (MySQL)
  |     [DBSubnetGroup, VPCSecurityGroups]
  |
  |-- AWS::EC2::SecurityGroup (Lambda SG, RDS SG)
  |     + AWS::EC2::SecurityGroupIngress (순환 참조 방지)
  |
  |-- AWS::SecretsManager::Secret (DB 자격증명)
  |
  v
sam deploy → CloudFormation Stack
```

---

## 출제 의도

- IaC(Infrastructure as Code) 전체 스택 구성 능력 평가
- SAM 템플릿 문법과 CloudFormation 리소스 간 참조 이해
- 순환 참조, 의존성 순서, 출력값 등 IaC 심화 개념 검증

---

## 왜 현실적인 문제인가

- DevOps/클라우드 엔지니어링에서 IaC는 필수 역량
- 반복 배포와 환경 재현성을 위해 SAM/CloudFormation 사용
- 전체 아키텍처를 코드로 표현하는 능력 종합 평가

---

## 참가자가 자주 틀리는 포인트

1. **Lambda SG와 RDS SG 간 순환 참조** — Lambda SG의 아웃바운드 규칙이 RDS SG를 참조하고, RDS SG의 인바운드 규칙이 Lambda SG를 참조하면 순환 참조 발생.
   - **해결**: 별도 `AWS::EC2::SecurityGroupIngress` / `AWS::EC2::SecurityGroupEgress` 리소스로 분리.

2. **RDS 생성 전 Lambda 배포 시도** — Lambda가 RDS 엔드포인트를 환경변수로 참조하면 RDS가 먼저 생성되어야 함. `DependsOn: MyRDSInstance` 명시 필요.

3. **SAM Globals 섹션 미활용** — 여러 Lambda 함수에 공통 설정(Runtime, VpcConfig, Layers)을 반복 작성. `Globals: Function:` 섹션으로 공통화 가능.

4. **Outputs 섹션 누락** — API 엔드포인트 URL, RDS 엔드포인트 등을 Outputs로 내보내지 않으면 배포 후 값 확인이 어려움.

5. **SAM 빌드 없이 배포** — `sam deploy` 전에 `sam build` 필수. Layer 포함 시 빌드 단계에서 의존성 패키징.

6. **DBSubnetGroup 누락** — RDS를 VPC private subnet에 배치하려면 `AWS::RDS::DBSubnetGroup` 리소스 정의 필수.

7. **VPC/서브넷을 SAM이 자동 생성한다는 오해** — SAM은 VPC를 자동으로 만들지 않음. 기존 VPC를 `Parameters`로 받거나 별도로 정의해야 함.

---

## 디버깅 포인트

**스택 상태 확인:**
```bash
aws cloudformation describe-stacks --stack-name my-stack \
  --query "Stacks[0].{Status:StackStatus,Reason:StackStatusReason}"
```

**스택 이벤트 확인 (실패 원인):**
```bash
aws cloudformation describe-stack-events --stack-name my-stack \
  --query "StackEvents[?ResourceStatus=='CREATE_FAILED'].{Resource:LogicalResourceId,Reason:ResourceStatusReason}"
```

**스택 출력값 확인:**
```bash
aws cloudformation describe-stacks --stack-name my-stack \
  --query "Stacks[0].Outputs"
```

**SAM 배포 명령:**
```bash
sam build
sam deploy \
  --stack-name my-lambda-rds-stack \
  --capabilities CAPABILITY_IAM \
  --region ap-northeast-2 \
  --resolve-s3
```

---

## 풀이 우선순위

1. **(5분) 템플릿 기본 구조 작성** — AWSTemplateFormatVersion, Transform, Globals
2. **(10분) 네트워크 리소스 정의** — SG 2개, SG Ingress 별도 리소스, DBSubnetGroup
3. **(10분) RDS 리소스 정의** — DBInstance, Secrets Manager 참조
4. **(10분) Lambda 리소스 정의** — Function, Layer, DependsOn, 환경변수
5. **(5분) Outputs 정의** — API URL, RDS 엔드포인트
6. **(10분) sam build && sam deploy** — 오류 수정 반복
7. **(5분) 스택 출력값 확인 및 테스트**

→ 참고 템플릿: `cfn-templates/lambda-rds-full-stack.yaml`
