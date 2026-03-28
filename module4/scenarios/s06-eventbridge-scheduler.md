# 시나리오 6: EventBridge + Lambda + MySQL + SNS

> 출제 가능성: **중간** | 난이도: **중**

---

## 아키텍처 구성

```
EventBridge Rule
  [Schedule: rate(1 hour) 또는 cron(0 9 * * ? *)]
  |
  v
Lambda Function
  [VPC: Private Subnet]
  |
  |--- (성공) --> SNS Topic --> 이메일/Slack 알림
  |
  |--- (실패) --> Lambda Destination (SNS) 또는 CloudWatch Alarm
  v
RDS MySQL
  [집계/정리 쿼리 실행]
```

---

## 출제 의도

- 스케줄 기반 자동화 작업 구성 능력 평가
- EventBridge 스케줄 표현식 문법 이해 (표준 cron과 다름)
- Lambda Destination 또는 SNS를 통한 알림 연동 패턴

---

## 왜 현실적인 문제인가

- 주기적 데이터 집계, 만료 데이터 정리, 헬스체크는 실무 필수
- EventBridge + Lambda는 cron job의 서버리스 대안
- 알림 연동은 운영 자동화의 기본

---

## 참가자가 자주 틀리는 포인트

1. **EventBridge cron 표현식 문법 오류** — AWS EventBridge cron은 6개 필드: `cron(분 시 일 월 요일 년)`. 요일과 일은 동시에 `*` 사용 불가 → 하나는 반드시 `?` 사용.
   ```
   cron(0 9 * * ? *)   ← 올바름 (매일 UTC 09:00)
   cron(0 9 * * * *)   ← 오류: 일과 요일 동시에 *
   rate(1 hour)        ← 올바름
   rate(1 hours)       ← 오류: 단수형 사용
   ```

2. **EventBridge → Lambda 호출 권한 누락** — EventBridge가 Lambda를 호출하려면 Lambda 리소스 기반 정책에 `events.amazonaws.com`의 `lambda:InvokeFunction` 허용 필요.
   ```bash
   aws lambda add-permission \
     --function-name my-scheduled-function \
     --statement-id EventBridgeInvoke \
     --action lambda:InvokeFunction \
     --principal events.amazonaws.com \
     --source-arn arn:aws:events:ap-northeast-2:ACCOUNT_ID:rule/my-rule
   ```

3. **SNS Publish 권한 누락** — Lambda 역할에 `sns:Publish` 권한이 없으면 알림 전송 실패. 에러가 CloudWatch Logs에만 남아 조용히 실패할 수 있음.

4. **UTC vs KST 시간대 혼동** — EventBridge 스케줄은 UTC 기준. KST 오전 9시 실행하려면 UTC 기준으로 `cron(0 0 * * ? *)` 사용. (KST = UTC+9)

5. **Lambda Destination 설정 위치 혼동** — Lambda Destination은 비동기 호출에만 적용됨. EventBridge → Lambda는 비동기 호출이므로 Destination 사용 가능. 동기 호출(API Gateway)에는 적용 안 됨.

---

## 디버깅 포인트

**EventBridge 규칙 확인:**
```bash
aws events list-rules \
  --query "Rules[*].{Name:Name,State:State,Schedule:ScheduleExpression}"

aws events list-targets-by-rule --rule my-rule
```

**Lambda 리소스 정책 확인:**
```bash
aws lambda get-policy --function-name my-scheduled-function \
  --query "Policy" | python3 -m json.tool
```

**SNS 구독 확인:**
```bash
aws sns list-subscriptions-by-topic \
  --topic-arn arn:aws:sns:ap-northeast-2:ACCOUNT_ID:my-topic
```

**EventBridge 규칙 생성 CLI:**
```bash
# 규칙 생성 (매일 KST 오전 9시 = UTC 0시)
aws events put-rule \
  --name daily-db-cleanup \
  --schedule-expression "cron(0 0 * * ? *)" \
  --state ENABLED

# Lambda 타겟 등록
aws events put-targets \
  --rule daily-db-cleanup \
  --targets "Id=1,Arn=arn:aws:lambda:ap-northeast-2:ACCOUNT_ID:function:my-scheduled-function"
```

**CloudWatch Logs 패턴:**
- `AuthorizationError` → `sns:Publish` 권한 없음
- Lambda가 실행 안 됨 → EventBridge 규칙 상태 DISABLED 또는 Lambda 리소스 정책 없음
- 잘못된 시간 실행 → UTC/KST 변환 확인

---

## 풀이 우선순위

1. **(5분) SNS 토픽 생성 및 구독** — 이메일 구독 확인 메일 승인
2. **(5분) Lambda 함수 생성** — VPC 설정, `SNS_TOPIC_ARN` 환경변수
3. **(5분) Lambda 역할 권한** — `sns:Publish` 추가
4. **(10분) Lambda 코드 작성** — DB 집계/정리 로직 + SNS 알림
5. **(5분) EventBridge 규칙 생성** — 스케줄 표현식, Lambda 타겟 등록
6. **(5분) Lambda 리소스 정책 추가** — EventBridge 호출 허용
7. **(5분) 수동 테스트** — EventBridge 콘솔에서 즉시 실행 버튼 활용

→ 참고 코드: `code-templates/conn-scheduler-sns.py`
