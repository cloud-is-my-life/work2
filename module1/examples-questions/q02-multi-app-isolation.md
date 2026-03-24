
# [예시 과제 2] 멀티 애플리케이션 격리 (난이도: ★★☆)

## 시나리오

FinTech 회사는 하나의 EFS 파일 시스템을 두 개의 애플리케이션 팀이 공유합니다.
각 팀은 자신의 디렉토리에만 접근할 수 있어야 하며, 다른 팀의 데이터를 볼 수 없어야 합니다.
Access Point를 활용하여 애플리케이션별 격리를 구현하시오.

---

## 요구사항

### [A] 네트워크

- `wsi-vpc` (10.0.0.0/16) 생성
- `ap-northeast-2a`에 퍼블릭 서브넷 `wsi-sub-a` (10.0.1.0/24)
- `ap-northeast-2c`에 퍼블릭 서브넷 `wsi-sub-c` (10.0.2.0/24)
- 보안 그룹 `sg-wsi-ec2`, `sg-wsi-efs` 구성 (NFS 트래픽 제어)

### [B] EC2

- `wsi-app-alpha` (ap-northeast-2a) — Alpha 팀 서버
- `wsi-app-beta` (ap-northeast-2c) — Beta 팀 서버
- 각 서버에 별도의 IAM Role 연결

### [C] EFS

- 파일 시스템 `wsi-shared-efs` 생성 (암호화 활성화, AWS 관리형 키)
- 두 AZ에 Mount Target 구성

### [D] Access Point

- `wsi-ap-alpha`:
  - 루트 디렉토리: `/alpha`
  - POSIX: UID 1001, GID 1001
  - 디렉토리 권한: 0750
- `wsi-ap-beta`:
  - 루트 디렉토리: `/beta`
  - POSIX: UID 1002, GID 1002
  - 디렉토리 권한: 0750

### [E] 마운트

- `wsi-app-alpha`는 `/mnt/data`에 `wsi-ap-alpha`를 통해 TLS 마운트
- `wsi-app-beta`는 `/mnt/data`에 `wsi-ap-beta`를 통해 TLS 마운트
- 재부팅 자동 마운트 (fstab)

### [F] 검증

- Alpha 서버에서 `/mnt/data/test.txt` 생성 → Beta 서버에서 해당 파일 보이지 않아야 함
- Beta 서버에서 `/mnt/data/report.txt` 생성 → Alpha 서버에서 해당 파일 보이지 않아야 함
- 각 서버에서 생성한 파일의 소유자가 해당 AP의 UID/GID와 일치해야 함

---

## 채점 기준

| 항목 | 배점 |
|------|------|
| EFS 생성 + 암호화 | 2점 |
| Mount Target 2AZ | 2점 |
| Access Point Alpha 구성 (경로/UID/GID/권한) | 3점 |
| Access Point Beta 구성 (경로/UID/GID/권한) | 3점 |
| TLS 마운트 (양쪽 서버) | 2점 |
| fstab 자동 마운트 | 2점 |
| Alpha ↔ Beta 격리 확인 | 4점 |
| 파일 소유자 UID/GID 일치 확인 | 2점 |
| **합계** | **20점** |
