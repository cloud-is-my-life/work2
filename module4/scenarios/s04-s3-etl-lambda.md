# 시나리오 4: S3 Event + Lambda + MySQL ETL

> 출제 가능성: **높음** | 난이도: **중** (멱등성 요구 시 중상)

---

## 아키텍처 구성

```
S3 Bucket
  [CSV 파일 업로드 → prefix: uploads/, suffix: .csv]
  |
  | S3 Event Notification
  v
Lambda Function (ETL)
  [VPC: Private Subnet, Timeout: 300s, Layer: pymysql]
  |
  | batch INSERT (executemany)
  v
RDS MySQL
  [VPC: Private Subnet]
```

---

## 출제 의도

- 이벤트 기반 데이터 파이프라인 구성 능력 평가
- Lambda Layer 패키징 실습 (pymysql 의존성 관리)
- 트랜잭션 처리, 에러 핸들링, 멱등성 설계 이해도 측정

---

## 왜 현실적인 문제인가

- 데이터 수집/적재 파이프라인은 실무에서 매우 흔한 패턴
- S3 → Lambda → RDS는 배치 처리의 서버리스 대안
- Layer 패키징은 Lambda 실무에서 반드시 알아야 할 기술

---

## 참가자가 자주 틀리는 포인트

1. **Layer zip 디렉토리 구조 오류** — Python Layer는 반드시 `python/` 디렉토리 하위에 패키지가 있어야 함.
   ```
   # 올바른 구조
   pymysql-layer.zip
   └── python/
       └── pymysql/
           └── __init__.py ...

   # 잘못된 구조 (인식 안 됨)
   pymysql-layer.zip
   └── pymysql/
       └── __init__.py ...
   ```

2. **Lambda 기본 타임아웃(3초) 미변경** — ETL 작업은 수십~수백 행 처리 시 3초를 초과. 최소 60~300초로 설정 필요.

3. **S3 이벤트 필터 미설정** — suffix `.csv` 필터 없이 모든 PUT 이벤트에 트리거되면, Lambda 결과물 파일 업로드 시 무한 루프 가능.

4. **at-least-once 전달 미고려** — S3 이벤트는 동일 파일에 대해 Lambda를 여러 번 호출할 수 있음. 멱등성 없이 단순 INSERT하면 중복 데이터 발생.

5. **트랜잭션 미사용** — 1000행 중 500행 삽입 후 Lambda 타임아웃 시 부분 삽입 상태가 됨. `conn.begin()` / `conn.commit()` / `conn.rollback()` 패턴 필수.

6. **Lambda에 s3:GetObject 권한 누락** — S3 이벤트로 트리거되어도 파일 내용을 읽으려면 `s3:GetObject` 권한이 Lambda 역할에 있어야 함.

---

## 디버깅 포인트

**S3 이벤트 알림 확인:**
```bash
aws s3api get-bucket-notification-configuration --bucket MY_BUCKET
```

**Lambda 리소스 기반 정책 확인 (S3 트리거 권한):**
```bash
aws lambda get-policy --function-name my-etl-function \
  --query "Policy" | python3 -m json.tool
```

**CloudWatch Logs 패턴:**
- `Task timed out` → 타임아웃 증가 필요
- `ModuleNotFoundError` → Layer 미연결 또는 구조 오류
- `UnicodeDecodeError` → CSV 인코딩 문제 (`decode('utf-8-sig')` 사용)
- `Duplicate entry` → 멱등성 처리 필요 (`INSERT IGNORE` 또는 `ON DUPLICATE KEY UPDATE`)

**Layer 패키징 및 등록:**
```bash
mkdir -p /tmp/layer/python
pip install pymysql -t /tmp/layer/python/ --quiet
cd /tmp/layer && zip -r /tmp/pymysql-layer.zip python/
aws lambda publish-layer-version \
  --layer-name pymysql-layer \
  --zip-file fileb:///tmp/pymysql-layer.zip \
  --compatible-runtimes python3.11 python3.12 \
  --query "LayerVersionArn"
```

---

## 풀이 우선순위

1. **(10분) Lambda Layer 생성** — pymysql 패키징, 올바른 디렉토리 구조 확인
2. **(5분) Lambda 함수 생성** — VPC 설정, Layer 연결, 타임아웃 300초, 환경변수
3. **(5분) Lambda 역할 권한** — `s3:GetObject` + `AWSLambdaVPCAccessExecutionRole`
4. **(10분) Lambda 코드 작성** — CSV 파싱, 트랜잭션, 멱등성 처리
5. **(5분) S3 이벤트 알림 설정** — prefix/suffix 필터 포함
6. **(5분) 테스트** — 샘플 CSV 업로드 후 CloudWatch Logs 확인

→ 참고 코드: `code-templates/conn-s3-etl.py`
