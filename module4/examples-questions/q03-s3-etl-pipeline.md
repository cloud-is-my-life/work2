# Q03: 이벤트 기반 데이터 파이프라인 + 비동기 처리 + 모니터링

**난이도: 상** | 관련 시나리오: S04, S05, S06

---

## 문제 설명

다음 환경이 사전 구성되어 있습니다:
- S3 버킷: 데이터 업로드용
- VPC: private subnet 2개
- RDS MySQL + RDS Proxy: private subnet에서 실행 중

S3에 CSV 파일이 업로드되면 자동으로 MySQL에 데이터를 적재하고, 실패 시 DLQ로 전송하며, 완료 시 SNS로 알림을 보내는 **완전한 이벤트 기반 파이프라인**을 구축하세요.

---

## 요구사항

1. S3 이벤트 알림: `data/` prefix, `.csv` suffix 파일 업로드 시 Lambda 트리거
2. Lambda Layer에 pymysql 패키징 (올바른 디렉토리 구조 사용)
3. Lambda는 CSV를 파싱하여 RDS Proxy를 통해 MySQL에 **배치 삽입** (executemany)
4. 처리 실패 시 SQS Dead Letter Queue로 메시지 전송
5. 처리 성공 시 SNS 토픽에 완료 알림 발행
6. CloudWatch Alarm: Lambda `Errors` 지표가 0 초과 시 알람 발생
7. Lambda 타임아웃을 ETL 작업에 적합하게 설정 (기본값 3초 사용 금지)
8. 동일 파일 재처리 시 중복 데이터가 생기지 않도록 **멱등성** 구현
9. 부분 실패 시 **트랜잭션 롤백** 처리

---

## 필요한 AWS 서비스

S3, Lambda, Lambda Layer, RDS Proxy, RDS, SQS, SNS, CloudWatch, IAM, VPC

---

## 예상 함정

- **S3 at-least-once**: S3 이벤트는 동일 파일에 대해 Lambda를 여러 번 호출 가능 → `INSERT IGNORE` 또는 `ON DUPLICATE KEY UPDATE` 로 멱등성 보장
- **Lambda DLQ 위치**: DLQ는 Lambda 함수 자체에 설정 (비동기 호출 실패 시 Lambda → DLQ). SQS 이벤트 소스의 DLQ와 다름
- **s3:GetObject 권한**: S3 트리거로 호출되어도 파일 읽기에는 별도 `s3:GetObject` 권한 필요
- **CSV 인코딩**: 한글 포함 CSV는 `utf-8-sig` (BOM 포함) 또는 `euc-kr` 인코딩일 수 있음 → `decode('utf-8-sig')` 사용
- **Lambda 타임아웃**: 기본 3초는 ETL에 부족 → 최소 60초, 대용량은 300초 설정
- **SNS Publish 권한**: Lambda 역할에 `sns:Publish` 권한 필요
- **CloudWatch Alarm 설정**: 네임스페이스 `AWS/Lambda`, 지표명 `Errors`, 통계 `Sum`, 기간 60초
- **트랜잭션**: `autocommit=False` 후 `conn.begin()` / `conn.commit()` / `conn.rollback()` 명시적 사용
