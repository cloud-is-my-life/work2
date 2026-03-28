# 시나리오 5: API GW + Lambda + SQS + Worker Lambda

> 출제 가능성: **중간** | 난이도: **중상**

---

## 아키텍처 구성

```
Client
  |
  v
API Gateway
  |
  v
Lambda (API Handler) -- 즉시 응답 반환
  |
  | SQS SendMessage
  v
SQS Queue
  [VisibilityTimeout >= Lambda Timeout × 6, DLQ 연결]
  |
  | Event Source Mapping
  v
Lambda (Worker) -- 비동기 DB 쓰기
  [VPC: Private Subnet]
  |
  v
RDS MySQL
  [VPC: Private Subnet]
```

---

## 출제 의도

- 동기/비동기 처리 분리 패턴 이해도 측정
- SQS 가시성 타임아웃, DLQ, 배치 처리 등 SQS 심화 설정 평가
- 멱등성 설계와 부분 실패 처리(ReportBatchItemFailures) 이해

---

## 왜 현실적인 문제인가

- API 응답 지연 없이 DB 쓰기를 처리하는 실무 패턴
- SQS + Lambda 조합은 AWS 서버리스 아키텍처의 핵심
- 장애 격리(DLQ)와 재처리 로직은 프로덕션 필수 요소

---

## 참가자가 자주 틀리는 포인트

1. **가시성 타임아웃 설정 오류** — SQS 가시성 타임아웃은 Worker Lambda 타임아웃의 최소 6배로 설정해야 함. Lambda가 30초 타임아웃이면 SQS는 최소 180초. 짧으면 처리 중인 메시지가 다시 큐에 나타나 중복 처리 발생.

2. **DLQ 미설정** — 처리 실패 메시지가 무한 재시도되어 큐를 막음. SQS 큐에 DLQ(Dead Letter Queue) 연결 필수. `maxReceiveCount`는 보통 3~5로 설정.

3. **Worker Lambda에 VPC 설정 누락** — Worker Lambda가 RDS에 접근하려면 VPC private subnet에 배치해야 함. API Handler Lambda는 VPC 불필요(SQS는 퍼블릭 엔드포인트 사용).

4. **멱등성 미구현** — 동일 메시지가 두 번 처리될 경우(at-least-once) DB에 중복 데이터 삽입. SQS 메시지 ID 또는 비즈니스 키로 중복 체크 필요.

5. **ReportBatchItemFailures 미설정** — 배치 처리 시 일부 메시지만 실패해도 전체 배치가 재처리됨. Lambda 이벤트 소스 매핑에서 `FunctionResponseTypes: [ReportBatchItemFailures]` 설정 필요.

6. **API Handler Lambda에 sqs:SendMessage 권한 누락** — API Handler가 SQS에 메시지를 보내려면 해당 권한이 실행 역할에 있어야 함.

---

## 디버깅 포인트

**SQS 큐 설정 확인:**
```bash
aws sqs get-queue-attributes \
  --queue-url https://sqs.ap-northeast-2.amazonaws.com/ACCOUNT_ID/my-queue \
  --attribute-names VisibilityTimeout RedrivePolicy
```

**DLQ 메시지 수 확인:**
```bash
aws sqs get-queue-attributes \
  --queue-url https://sqs.ap-northeast-2.amazonaws.com/ACCOUNT_ID/my-dlq \
  --attribute-names ApproximateNumberOfMessages
```

**Event Source Mapping 확인:**
```bash
aws lambda list-event-source-mappings \
  --function-name worker-lambda \
  --query "EventSourceMappings[*].{State:State,BatchSize:BatchSize,FunctionResponseTypes:FunctionResponseTypes}"
```

**SQS 큐 생성 CLI:**
```bash
# DLQ 먼저 생성
DLQ_URL=$(aws sqs create-queue --queue-name my-dlq \
  --query QueueUrl --output text)
DLQ_ARN=$(aws sqs get-queue-attributes --queue-url $DLQ_URL \
  --attribute-names QueueArn --query Attributes.QueueArn --output text)

# 메인 큐 생성 (가시성 타임아웃 180초, DLQ 연결)
aws sqs create-queue --queue-name my-queue \
  --attributes VisibilityTimeout=180,RedrivePolicy='{"deadLetterTargetArn":"'$DLQ_ARN'","maxReceiveCount":"3"}'
```

**CloudWatch Logs 패턴:**
- `Task timed out` (Worker) → 가시성 타임아웃 증가 필요
- DLQ에 메시지 쌓임 → Worker Lambda 오류 확인
- 중복 데이터 → 멱등성 처리 필요

---

## 풀이 우선순위

1. **(5분) SQS DLQ + 메인 큐 생성** — 가시성 타임아웃 계산, DLQ 연결, maxReceiveCount 설정
2. **(5분) API Handler Lambda 생성** — SQS SendMessage 코드, `sqs:SendMessage` 권한
3. **(5분) Worker Lambda 생성** — VPC 설정, pymysql Layer 연결
4. **(5분) Event Source Mapping 생성** — SQS → Worker Lambda, `ReportBatchItemFailures` 활성화
5. **(10분) Worker Lambda 코드 작성** — 멱등성(`INSERT IGNORE`), 부분 실패 처리
6. **(5분) API Gateway 연결 및 테스트**

→ 참고 코드: `code-templates/conn-sqs-worker.py`
