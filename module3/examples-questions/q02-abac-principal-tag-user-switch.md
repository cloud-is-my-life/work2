# [예시 과제 2] ABAC PrincipalTag + 사용자 전환 검증 (난이도: ★★★)

## 시나리오

동일한 IAM 정책을 여러 사용자에 붙이되,
사용자 태그(`Team`)에 따라 접근 가능한 S3 Prefix를 자동으로 분기해야 한다.

---

## 요구사항

### [A] IAM 사용자 2명
- `MOD3_Q02_USER_ANALYTICS` (태그: `Team=analytics`)
- `MOD3_Q02_USER_OPS` (태그: `Team=ops`)
- 공통 정책: `MOD3_Q02_ABAC_POLICY`

### [B] 정책 요구
1. `s3:ListBucket`은 `home/${aws:PrincipalTag/Team}/*` Prefix만 허용
2. `s3:GetObject`, `s3:PutObject`는 `home/${aws:PrincipalTag/Team}/*`만 허용
3. `aws:PrincipalTag/Team`이 없는 주체는 Deny (`Null` 조건)

### [C] 검증 (사용자 전환)
1. analytics 사용자:
   - `home/analytics/` 성공
   - `home/ops/` 실패
2. ops 사용자:
   - `home/ops/` 성공
   - `home/analytics/` 실패

---

## 채점 기준

| 항목 | 배점 |
|------|------|
| 사용자 2명 + 태그 생성 | 3점 |
| 공통 ABAC 정책 작성 | 4점 |
| 태그 누락 차단(`Null`) | 2점 |
| analytics 사용자 검증 | 3점 |
| ops 사용자 검증 | 3점 |
| 교차 Prefix 접근 실패 확인 | 3점 |
| **합계** | **18점** |
