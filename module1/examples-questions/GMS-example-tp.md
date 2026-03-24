
# [과제 1] Shared Network Storage

> 해당 문제지는 공주마이스터고에서 출제한 예시 문제입니다.
## 시나리오

WorldPay 개발팀은 여러 애플리케이션 서버가 공통 설정 파일과 로그를 공유해야 합니다.
단일 장애점 없이 모든 서버에서 동시에 접근 가능한 공유 스토리지를 구축하시오.

---

## 요구사항

### [A] 네트워크

`wsi-efs-vpc` (10.0.0.0/16)를 생성하고, ap-northeast-2a와 ap-northeast-2c에 각각 퍼블릭 서브넷(`wsi-efs-sub-a`, `wsi-efs-sub-c`)을 구성하시오.
보안 그룹 `sg-wsi-ec2`와 `sg-wsi-efs`를 생성하시오. `sg-wsi-efs`는 NFS 트래픽(TCP 2049)을 `sg-wsi-ec2`에서만 허용해야 하며, 외부 인터넷에서의 직접 접근은 차단되어야 합니다.

### [B] EC2

두 가용 영역에 각각 Amazon Linux 2023 기반의 애플리케이션 서버를 생성하시오.
- `wsi-app-server-a` / ap-northeast-2a
- `wsi-app-server-c` / ap-northeast-2c

### [C] EFS

두 서버가 공유할 수 있는 EFS 파일 시스템(`wsi-shared-efs`)을 생성하시오.
파일 시스템은 KMS CMK(`alias/wsi-efs-key`)로 암호화되어야 하며, 30일간 접근하지 않은 파일은 자동으로 IA 계층으로 전환되도록 구성하시오.
두 가용 영역 모두에서 접근 가능해야 합니다.

### [D] Access Point

`/shared` 디렉토리로 접근을 제한하는 Access Point(`wsi-efs-ap`)를 구성하시오.
애플리케이션은 Access Point를 통해서만 EFS에 접근해야 하며, UID 1000 / GID 1000으로 일관된 파일 소유권이 적용되어야 합니다.

### [E] 마운트 및 검증

두 서버 모두 `/mnt/shared` 경로에 EFS를 마운트하시오.
전송 중 데이터 암호화(TLS)가 적용되어야 하며, 서버 재부팅 후에도 자동으로 마운트되어야 합니다.
최종적으로 `wsi-app-server-a`에서 생성한 파일이 `wsi-app-server-c`에서도 조회 가능해야 합니다.

---

## 채점 기준

| 항목 | 배점 |
|------|------|
| EFS 생성 + KMS 암호화 | 3점 |
| 마운트 타겟 AZ 2개 구성 | 2점 |
| sg-wsi-efs: TCP 2049 → sg-wsi-ec2만 허용 | 2점 |
| Access Point 구성 (경로 /shared, UID/GID 1000) | 3점 |
| TLS 마운트 옵션 | 2점 |
| 재부팅 자동 마운트 (fstab) | 2점 |
| 수명 주기 정책 30일 IA | 1점 |
| 서버 간 파일 공유 확인 | 5점 |
| **합계** | **20점** |