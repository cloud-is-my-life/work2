# [예시 과제 1] Prefix 기반 ReadOnly + Explicit Deny (난이도: ★★☆)

## 시나리오

보안팀은 운영 로그 버킷에서 `reports/` 경로만 읽도록 허용하고,
오브젝트 삭제는 어떤 경우에도 금지하려고 한다.

---

## 요구사항

### [A] IAM
- 사용자: `MOD3_Q01_USER`
- 정책: `MOD3_Q01_POLICY`

### [B] 권한 조건
1. `s3://DATA_BUCKET/reports/` 경로 조회(`ListBucket`) 허용
2. `s3://DATA_BUCKET/reports/*` 오브젝트 읽기(`GetObject`) 허용
3. `s3://DATA_BUCKET/reports/*` 삭제(`DeleteObject`)는 명시적 Deny
4. TLS 미사용(`aws:SecureTransport=false`) 요청은 전체 Deny

### [C] 검증
- 사용자 프로파일로 `aws s3 ls s3://DATA_BUCKET/reports/` 성공
- 사용자 프로파일로 `aws s3 cp s3://DATA_BUCKET/reports/SAMPLE_FILE -` 성공
- 사용자 프로파일로 `aws s3 rm s3://DATA_BUCKET/reports/SAMPLE_FILE` 실패(AccessDenied)

---

## 채점 기준

| 항목 | 배점 |
|------|------|
| 사용자 생성 | 2점 |
| 정책 생성/연결 | 3점 |
| Prefix 제한 정확성 | 3점 |
| 삭제 Deny 적용 | 3점 |
| TLS 강제 Deny | 2점 |
| 사용자 전환 검증 | 3점 |
| **합계** | **16점** |
