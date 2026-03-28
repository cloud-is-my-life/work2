# Q03 풀이: 이벤트 기반 데이터 파이프라인 + 비동기 처리 + 모니터링

---

## 풀이 힌트

1. **MySQL 테이블에 UNIQUE 제약 추가** — 멱등성의 기반. email 등 자연 키에 UNIQUE 제약 설정.
   ```sql
   CREATE TABLE employees (
     id INT AUTO_INCREMENT PRIMARY KEY,
     name VARCHAR(100),
     email VARCHAR(100) UNIQUE NOT NULL,
     dept VARCHAR(50)
   );
   ```

2. **Lambda 예약 동시성을 1로 설정** (선택) — 테스트 중 커넥션 고갈 방지. 검증 후 해제.

3. **5행짜리 소형 CSV로 먼저 테스트** 후 대용량 테스트:
   ```bash
   cat > /tmp/test.csv << 'EOF'
   name,email,dept
   홍길동,hong@example.com,개발팀
   김철수,kim@example.com,영업팀
   EOF
   aws s3 cp /tmp/test.csv s3://MY_BUCKET/data/test.csv
   ```

4. **DLQ 설정 위치**: Lambda 콘솔 > 구성 > 비동기 호출 탭 (S3는 비동기 호출). SQS 큐 ARN 입력.

5. **CloudWatch Alarm 설정**:
   - 네임스페이스: `AWS/Lambda`
   - 지표명: `Errors`
   - 함수명: 해당 Lambda 함수
   - 통계: `Sum`
   - 기간: 60초
   - 임계값: 0 초과 시 알람

6. **CloudWatch Logs Insights로 오류 빠르게 분석**:
   ```
   fields @timestamp, @message
   | filter @message like /ERROR/
   | sort @timestamp desc
   | limit 20
   ```

---

## 검증 방법

```bash
# 테스트 CSV 업로드
aws s3 cp /tmp/test.csv s3://MY_BUCKET/data/test.csv

# Lambda 실행 로그 확인 (최근 5분)
aws logs filter-log-events \
  --log-group-name /aws/lambda/etl-function \
  --start-time $(date -d '5 minutes ago' +%s000) \
  --query "events[*].message" --output text

# DLQ 메시지 수 확인
aws sqs get-queue-attributes \
  --queue-url https://sqs.ap-northeast-2.amazonaws.com/ACCOUNT_ID/etl-dlq \
  --attribute-names ApproximateNumberOfMessages

# SNS 구독 확인
aws sns list-subscriptions-by-topic \
  --topic-arn arn:aws:sns:ap-northeast-2:ACCOUNT_ID:etl-notifications

# CloudWatch Alarm 상태 확인
aws cloudwatch describe-alarms \
  --alarm-names etl-lambda-errors \
  --query "MetricAlarms[0].{State:StateValue,Reason:StateReason}"

# 멱등성 테스트: 동일 파일 재업로드 후 DB COUNT 동일해야 함
aws s3 cp /tmp/test.csv s3://MY_BUCKET/data/test.csv

# Lambda 비동기 호출 설정 확인 (DLQ)
aws lambda get-function-event-invoke-config \
  --function-name etl-function \
  --query "{MaxRetry:MaximumRetryAttempts,DLQ:DestinationConfig}"
```
