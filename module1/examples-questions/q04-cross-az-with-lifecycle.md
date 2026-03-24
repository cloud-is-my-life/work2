
# [예시 과제 4] Cross-AZ 고가용성 + 라이프사이클 (난이도: ★★☆)

## 시나리오

미디어 스트리밍 회사는 대용량 미디어 파일을 여러 트랜스코딩 서버에서 공유합니다.
비용 최적화를 위해 자주 접근하지 않는 파일은 자동으로 저비용 스토리지로 이동해야 하며,
모든 가용 영역에서 고가용성을 보장해야 합니다.

---

## 요구사항

### [A] 네트워크

- `wsi-media-vpc` (172.16.0.0/16) 생성
- 3개 AZ에 프라이빗 서브넷 구성:
  - `wsi-media-sub-a` (172.16.1.0/24) — ap-northeast-2a
  - `wsi-media-sub-b` (172.16.2.0/24) — ap-northeast-2b
  - `wsi-media-sub-c` (172.16.3.0/24) — ap-northeast-2c
- 퍼블릭 서브넷 1개 + NAT Gateway (인터넷 접근용)
- 보안 그룹 구성

### [B] EC2

- 3개 AZ에 각 1대씩 트랜스코딩 서버:
  - `wsi-transcode-a`, `wsi-transcode-b`, `wsi-transcode-c`
- Amazon Linux 2023, t3.medium

### [C] EFS

- `wsi-media-efs` 생성
  - AWS 관리형 키로 암호화
  - 성능 모드: generalPurpose
  - 처리량 모드: elastic
- 3개 AZ 모두에 Mount Target 구성

### [D] 라이프사이클 정책

- 7일간 미접근 파일 → IA(Infrequent Access) 전환
- 90일간 미접근 파일 → Archive 전환
- IA/Archive 파일 접근 시 → Standard로 자동 복귀 (Intelligent-Tiering)

### [E] File System Policy

- TLS 강제 (비TLS 거부)
- Mount Target 경유만 허용

### [F] 마운트

- 3대 모두 `/mnt/media`에 TLS 마운트
- fstab 등록

### [G] 검증

- 서버 A에서 파일 생성 → 서버 B, C에서 조회 가능
- 라이프사이클 정책이 올바르게 설정되었는지 CLI로 확인:
  ```bash
  aws efs describe-lifecycle-configuration --file-system-id fs-XXXXX
  ```

---

## 채점 기준

| 항목 | 배점 |
|------|------|
| VPC + 3AZ 서브넷 구성 | 2점 |
| NAT Gateway + 라우팅 | 2점 |
| SG 구성 | 1점 |
| EFS 생성 + 암호화 | 2점 |
| Mount Target 3AZ | 3점 |
| 라이프사이클 — IA 7일 | 2점 |
| 라이프사이클 — Archive 90일 | 2점 |
| 라이프사이클 — Intelligent-Tiering | 1점 |
| File System Policy (TLS + MT 강제) | 2점 |
| TLS 마운트 3대 | 2점 |
| fstab 자동 마운트 | 1점 |
| 3서버 간 파일 공유 확인 | 3점 |
| CLI로 라이프사이클 확인 | 1점 |
| **합계** | **24점** |
