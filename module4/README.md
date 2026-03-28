# Module 4: MySQL with Lambda

> 지방기능경기대회 1시간 실기 기준 — Lambda + MySQL 아키텍처 출제 분석 및 대비

---

## 디렉토리 구조

```
module4/
├── README.md                  ← 이 파일 (개요 + 비교표)
├── cheatsheet.md              ← 빠른 참조 (CLI, 패키징, 핵심 패턴)
├── troubleshooting.md         ← 오류 패턴 + 디버깅 명령어 모음
├── scenarios/                 ← 시나리오별 상세 분석 (8개)
│   ├── s01-apigw-lambda-vpc-rds.md
│   ├── s02-lambda-secrets-manager.md
│   ├── s03-lambda-rds-proxy-iam.md
│   ├── s04-s3-etl-lambda.md
│   ├── s05-sqs-worker-lambda.md
│   ├── s06-eventbridge-scheduler.md
│   ├── s07-multi-az-failover.md
│   └── s08-sam-cfn-stack.md
├── examples-questions/        ← 모의 문제 (문제지)
│   ├── README.md
│   ├── q01-apigw-vpc-rds.md  (난이도: 중)
│   ├── q02-secrets-proxy-iam.md (난이도: 중상)
│   ├── q03-s3-etl-pipeline.md (난이도: 상)
│   └── answers/               ← 풀이 힌트 + 검증 방법
│       ├── README.md
│       ├── q01-answer.md
│       ├── q02-answer.md
│       └── q03-answer.md
├── code-templates/            ← Lambda Python 코드 + 패키징 스크립트
│   ├── layer-packaging.sh
│   ├── conn-basic.py
│   ├── conn-secrets-manager.py
│   ├── conn-iam-proxy.py
│   ├── conn-s3-etl.py
│   ├── conn-sqs-worker.py
│   ├── conn-scheduler-sns.py
│   └── conn-failover.py
└── cfn-templates/             ← SAM/CloudFormation 전체 스택 템플릿
    └── lambda-rds-full-stack.yaml
```

---

## 시나리오 총괄 비교표

| # | 시나리오 | 핵심 서비스 | 난이도 | 출제 가능성 | 핵심 함정 |
|---|---------|-----------|--------|-----------|----------|
| 1 | API GW + Lambda(VPC) + RDS Private | API GW, Lambda, RDS, VPC | 중 | **매우 높음** | SG 인바운드, Lambda VPC 서브넷 선택 |
| 2 | Lambda + Secrets Manager + RDS | Lambda, Secrets Manager, RDS | 중 | **높음** | VPC Endpoint 누락, private DNS 비활성화 |
| 3 | Lambda + RDS Proxy + IAM Auth | Lambda, RDS Proxy, IAM | 중상 | **높음** | rds-db:connect ARN 형식, SSL 필수 |
| 4 | S3 Event + Lambda + MySQL ETL | S3, Lambda, RDS, Layer | 중 | **높음** | Layer 디렉토리 구조, 멱등성, 타임아웃 |
| 5 | API GW + Lambda + SQS + Worker Lambda | API GW, SQS, Lambda×2, RDS | 중상 | 중간 | 가시성 타임아웃, DLQ, ReportBatchItemFailures |
| 6 | EventBridge + Lambda + MySQL + SNS | EventBridge, Lambda, RDS, SNS | 중 | 중간 | cron UTC 기준, EventBridge->Lambda 권한 |
| 7 | Multi-AZ RDS + Lambda Failover | Lambda, RDS Multi-AZ | 중상 | 중간 | DNS 캐싱, 커넥션 재시도, ping(reconnect) |
| 8 | CloudFormation/SAM 전체 스택 | SAM, Lambda, RDS, VPC | 상 | 중간 | SG 순환 참조, DependsOn, DBSubnetGroup |

---

## 출제 가능성 분석

### 최우선 대비 (매우 높음 / 높음)

**시나리오 1, 2, 3, 4** 는 1시간 실기에서 단독 또는 조합으로 출제될 가능성이 가장 높다.

- 시나리오 1은 기본기 검증으로 단독 출제 가능
- 시나리오 2, 3은 시나리오 1에 "보안 강화" 요구사항을 추가하는 형태로 변형 출제 가능
- 시나리오 4는 시나리오 1과 독립적인 "이벤트 기반 ETL" 문제로 출제 가능

### 보조 대비 (중간)

**시나리오 5~8** 은 시간이 허용하면 대비하되, 5번(SQS)과 6번(EventBridge)은 1~4번 이해 후 자연스럽게 익힐 수 있다.

---

## 빠른 체크리스트

Lambda + RDS 연결 전 반드시 확인:

- [ ] Lambda를 **private subnet** 에 배치했는가?
- [ ] Lambda 실행 역할에 **AWSLambdaVPCAccessExecutionRole** 이 있는가?
- [ ] RDS SG 인바운드에 **Lambda SG → 3306** 허용 규칙이 있는가?
- [ ] **pymysql** 을 Layer에 패키징했는가? (`python/` 디렉토리 구조)
- [ ] Lambda 환경변수에 **DB_HOST, DB_USER, DB_PASS, DB_NAME** 이 있는가?
- [ ] 커넥션을 **모듈 레벨** 에서 관리하는가? (핸들러 내부 생성 금지)
