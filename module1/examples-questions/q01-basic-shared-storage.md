
# [예시 과제 1] 기본 공유 스토리지 구축 (난이도: ★☆☆)

## 시나리오

스타트업 DevOps팀은 두 대의 웹 서버가 정적 콘텐츠를 공유해야 합니다.
단일 장애점 없이 모든 서버에서 동시에 접근 가능한 공유 파일 시스템을 구축하시오.

---

## 요구사항

### [A] 네트워크

- `wsi-vpc` (10.0.0.0/16) 생성
- `ap-northeast-2a`에 퍼블릭 서브넷 `wsi-sub-a` (10.0.1.0/24)
- `ap-northeast-2c`에 퍼블릭 서브넷 `wsi-sub-c` (10.0.2.0/24)
- 인터넷 게이트웨이 연결 및 라우팅 구성

### [B] 보안 그룹

- `sg-wsi-ec2`: SSH(22) 허용
- `sg-wsi-efs`: NFS(TCP 2049)를 `sg-wsi-ec2`에서만 허용

### [C] EC2

- Amazon Linux 2023 기반 인스턴스 2대:
  - `wsi-server-a` (ap-northeast-2a)
  - `wsi-server-c` (ap-northeast-2c)

### [D] EFS

- 파일 시스템 `wsi-efs` 생성
- 두 AZ 모두에 Mount Target 구성
- 암호화 없이 기본 설정

### [E] 마운트 및 검증

- 두 서버 모두 `/mnt/efs` 경로에 마운트
- 재부팅 후에도 자동 마운트 (fstab)
- `wsi-server-a`에서 생성한 파일이 `wsi-server-c`에서 조회 가능

---

## 채점 기준

| 항목 | 배점 |
|------|------|
| VPC + 서브넷 2개 구성 | 2점 |
| SG 구성 (NFS 2049 → EC2 SG만 허용) | 2점 |
| EFS 파일 시스템 생성 | 2점 |
| Mount Target 2개 AZ 구성 | 2점 |
| 두 서버 마운트 성공 | 3점 |
| fstab 자동 마운트 | 2점 |
| 서버 간 파일 공유 확인 | 2점 |
| **합계** | **15점** |
