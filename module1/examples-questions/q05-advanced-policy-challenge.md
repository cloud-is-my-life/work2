
# [예시 과제 5] 고급 정책 챌린지 (난이도: ★★★★)

## 시나리오

대기업의 보안팀은 EFS 파일 시스템에 대해 다층 보안 정책을 요구합니다.
시간 기반 접근 제어, IP 기반 제한, 태그 기반 ABAC, Access Point 강제를 모두 조합한
복합 File System Policy를 작성하시오.

---

## 요구사항

### [A] 네트워크

- `wsi-sec-vpc` (10.100.0.0/16) 생성
- `wsi-sec-sub-a` (10.100.1.0/24) — ap-northeast-2a
- `wsi-sec-sub-c` (10.100.2.0/24) — ap-northeast-2c
- Bastion 서브넷: `wsi-sec-bastion-sub` (10.100.0.0/24) — ap-northeast-2a

### [B] EC2

- `wsi-bastion` (10.100.0.100) — Bastion 서버 (EFS 접근 거부 대상)
- `wsi-app-a` (10.100.1.100) — 앱 서버 A
- `wsi-app-c` (10.100.2.100) — 앱 서버 C

### [C] IAM

- `wsi-app-role`:
  - 태그: `Team=engineering`, `Environment=production`
- `wsi-bastion-role`:
  - 태그: `Team=ops`, `Environment=production`

### [D] EFS + Access Point

- `wsi-sec-efs`: KMS CMK 암호화
- `wsi-sec-ap`: 루트 `/app-data`, UID/GID 1500, 권한 0755
- Mount Target: 2AZ

### [E] File System Policy (핵심!)

다음 조건을 **모두** 포함하는 단일 정책 작성:

1. **TLS 강제**: `aws:SecureTransport=false` → 전체 Deny
2. **루트 접근 거부**: `ClientRootAccess` → Deny
3. **Bastion IP 차단**: `10.100.0.0/24` 대역 → 전체 Deny
4. **앱 서버 허용**: `wsi-app-role`에 대해 Mount + Write 허용
   - 조건: TLS 사용 + Mount Target 경유 + Access Point 경유
5. **태그 기반 제어**: `Team=engineering` 태그를 가진 주체만 허용
6. **시간 기반 제어**: 2026년 6월 1일 ~ 6월 30일 사이에만 접근 허용

### [F] 마운트 및 검증

- 앱 서버 2대: `/mnt/app-data`에 TLS + AP 마운트 → 성공
- Bastion 서버: 마운트 시도 → 실패 확인
- fstab 등록

---

## 채점 기준

| 항목 | 배점 |
|------|------|
| VPC + 서브넷 3개 | 1점 |
| EC2 3대 (고정 IP) | 2점 |
| IAM Role 2개 + 태그 | 2점 |
| EFS + KMS 암호화 | 2점 |
| Access Point 구성 | 2점 |
| Mount Target 2AZ | 1점 |
| 정책 — TLS 강제 | 2점 |
| 정책 — 루트 거부 | 2점 |
| 정책 — Bastion IP 차단 | 3점 |
| 정책 — Role 기반 Allow | 2점 |
| 정책 — AP 경유 강제 | 2점 |
| 정책 — 태그 기반 (ABAC) | 3점 |
| 정책 — 시간 기반 제어 | 3점 |
| 앱 서버 마운트 성공 | 2점 |
| Bastion 마운트 거부 확인 | 2점 |
| fstab 자동 마운트 | 1점 |
| **합계** | **32점** |

---

## 힌트: 정책 구조

```json
{
    "Version": "2012-10-17",
    "Statement": [
        { "Sid": "EnforceTLS", "Effect": "Deny", ... },
        { "Sid": "DenyRootAccess", "Effect": "Deny", ... },
        { "Sid": "DenyBastionSubnet", "Effect": "Deny", ... },
        { "Sid": "AllowAppWithConditions", "Effect": "Allow", ... }
    ]
}
```

> Allow Statement의 Condition 블록에 여러 조건을 AND로 결합하는 것이 핵심.
> 같은 Condition 블록 내의 서로 다른 연산자(Bool, StringEquals, ArnEquals, DateGreaterThan 등)는 자동으로 AND 처리됨.
