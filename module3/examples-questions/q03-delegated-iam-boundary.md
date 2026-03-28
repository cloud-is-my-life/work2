# [예시 과제 3] Delegated IAM + Permissions Boundary (난이도: ★★★★)

## 시나리오

중앙 보안팀은 "제한된 IAM 운영자"를 두고 싶다.
이 운영자는 사용자/정책을 생성할 수 있지만, 반드시 Permissions Boundary를 걸어야 하며
고권한 정책 연결은 금지되어야 한다.

---

## 요구사항

### [A] IAM 객체
- 위임 운영자 사용자: `MOD3_Q03_DELEGATE_USER`
- 위임 정책: `MOD3_Q03_DELEGATE_POLICY`
- 경계 정책(Boundary): `MOD3_Q03_BOUNDARY_POLICY`

### [B] 위임 정책 제약
1. `iam:CreateUser` 허용, 단 `iam:PermissionsBoundary`가 `MOD3_Q03_BOUNDARY_POLICY`일 때만
2. `iam:AttachUserPolicy` 허용, 단 `AdministratorAccess` 연결은 Deny
3. (권장) `iam:PassRole`이 필요하다면 특정 Role ARN만 허용

### [C] 검증
1. 위임 사용자 자격으로 경계 정책 포함 `CreateUser` 성공
2. 경계 정책 없이 `CreateUser` 시도 시 실패
3. `AdministratorAccess` 부착 시도 실패

---

## 채점 기준

| 항목 | 배점 |
|------|------|
| 위임 사용자/정책 생성 | 3점 |
| Boundary 정책 생성 | 3점 |
| CreateUser + Boundary 강제 | 4점 |
| Admin 정책 부착 차단 | 3점 |
| 사용자 전환 검증 | 3점 |
| **합계** | **16점** |
