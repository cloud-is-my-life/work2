
# [예시 과제 5] 크로스계정 Athena + KMS (난이도: ★★★★)

## 시나리오

Account A의 분석팀이 Account B의 S3 로그 버킷을 Athena로 조회해야 한다.
데이터와 결과 버킷 모두 암호화되어 있으며, 최소 권한으로 구성하시오.

---

## 요구사항

### [A] Account B
- S3 버킷 정책으로 Account A 읽기 허용
- KMS 키 정책으로 Account A Role에 Decrypt 허용

### [B] Account A
- Athena Query Role 생성
- 데이터 버킷 읽기 + 결과 버킷 쓰기 권한
- WorkGroup은 SSE-KMS 강제

### [C] 검증
- CloudTrail 또는 ALB 로그 1개 테이블 생성
- 쿼리 1회 성공 확인

---

## 채점 기준

| 항목 | 배점 |
|------|------|
| Bucket Policy | 4점 |
| KMS Key Policy | 4점 |
| Account A IAM Role | 4점 |
| WorkGroup 암호화 설정 | 3점 |
| 쿼리 성공 | 3점 |
| **합계** | **18점** |
