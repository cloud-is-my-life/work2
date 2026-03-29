# Lambda Packaging — AWS Console 기준 코드 배포 가이드

---

## 전체 흐름

```
[로컬]                          [AWS Console]
pip install pymysql
  → python/ 디렉토리 생성
  → zip으로 압축            →  Lambda > Layers > Layer 생성 > zip 업로드

lambda_function.py 작성
  → zip으로 압축            →  Lambda > 함수 > 코드 > .zip 파일로 업로드
                                환경변수 설정
                                Layer 연결
```

---

## 가이드 문서

| 문서 | 내용 |
|------|------|
| `layer-guide.md` | pymysql Layer zip 만들기 + 콘솔 업로드 방법 |
| `function-guide.md` | 함수 코드 zip 만들기 + 콘솔 업로드 + 환경변수/Layer 연결 |

---

## 시나리오별 함수 코드

| 디렉토리 | 시나리오 | 연결 방식 |
|---------|---------|---------|
| `functions/api-basic/` | S1: API GW + Lambda + RDS | 환경변수 직접 사용 |
| `functions/api-secure/` | S2+S3: Secrets Manager + RDS Proxy | IAM 토큰 + SSL |
| `functions/etl-s3/` | S4: S3 이벤트 → MySQL ETL | 환경변수 + 트랜잭션 |
| `functions/sqs-worker/` | S5: SQS → MySQL Worker | 멱등성 처리 |
| `functions/scheduler/` | S6: EventBridge + SNS | 스케줄 + 알림 |

---

## 핵심 원칙

1. **핸들러 이름**: 모든 함수의 진입점은 `lambda_function.lambda_handler`
   - 파일명: `lambda_function.py`
   - 함수명: `lambda_handler(event, context)`
   - 콘솔 기본값과 일치시켜 헷갈리지 않도록

2. **Layer로 pymysql 관리**: 코드 zip에 pymysql 포함하지 않음
   - Layer 한 번 만들면 여러 함수에서 재사용

3. **환경변수로 설정값 분리**: DB 연결 정보는 코드에 하드코딩 금지
