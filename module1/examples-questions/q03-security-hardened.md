
# [예시 과제 3] 보안 강화 공유 스토리지 (난이도: ★★★)

## 시나리오

금융 규제를 준수해야 하는 결제 시스템은 공유 스토리지에 대해 엄격한 보안 정책을 요구합니다.
KMS 암호화, TLS 강제, 루트 접근 거부, IAM 기반 접근 제어를 모두 적용한 EFS를 구축하시오.

---

## 요구사항

### [A] 네트워크

- `wsi-pay-vpc` (10.10.0.0/16) 생성
- `ap-northeast-2a`: `wsi-pay-sub-a` (10.10.1.0/24)
- `ap-northeast-2c`: `wsi-pay-sub-c` (10.10.2.0/24)
- 보안 그룹:
  - `sg-wsi-pay-ec2`: SSH(22) 허용
  - `sg-wsi-pay-efs`: NFS(2049)를 `sg-wsi-pay-ec2`에서만 허용

### [B] KMS

- CMK 생성: 별칭 `alias/wsi-pay-efs-key`
- 키 정책: 루트 계정 전체 권한

### [C] IAM

- IAM Role `wsi-pay-efs-role` 생성
  - EC2 서비스 신뢰
  - `AmazonElasticFileSystemClientReadWriteAccess` 정책 연결
  - 태그: `AppRole=payment-app`

### [D] EC2

- `wsi-pay-server-a` (ap-northeast-2a)
- `wsi-pay-server-c` (ap-northeast-2c)
- 두 서버 모두 `wsi-pay-efs-role` 연결

### [E] EFS

- 파일 시스템 `wsi-pay-efs` 생성
  - KMS CMK(`alias/wsi-pay-efs-key`)로 암호화
  - 라이프사이클: 14일 후 IA 전환, 접근 시 Standard 복귀
  - 성능 모드: generalPurpose
  - 처리량 모드: elastic

### [F] File System Policy

다음 조건을 **모두** 만족하는 정책 작성:
1. TLS 미사용 시 모든 접근 거부
2. 루트 접근(ClientRootAccess) 거부
3. `wsi-pay-efs-role` Role만 Mount + Write 허용
4. `AppRole=payment-app` 태그를 가진 주체만 허용
5. Mount Target 경유 접근만 허용

### [G] Access Point

- `wsi-pay-ap`:
  - 루트 디렉토리: `/payment-data`
  - POSIX: UID 2000, GID 2000
  - 디렉토리 권한: 0700

### [H] 마운트 및 검증

- 두 서버 모두 `/mnt/payment` 경로에 TLS + Access Point로 마운트
- fstab 등록 (재부팅 자동 마운트)
- 파일 공유 검증
- TLS 없이 마운트 시도 → 실패 확인

---

## 채점 기준

| 항목 | 배점 |
|------|------|
| KMS CMK 생성 + 별칭 | 2점 |
| EFS 생성 + KMS 암호화 | 2점 |
| 라이프사이클 정책 (IA 14일 + 복귀) | 2점 |
| Mount Target 2AZ | 1점 |
| SG 구성 (NFS → EC2 SG만) | 2점 |
| IAM Role + 태그 구성 | 2점 |
| File System Policy — TLS 강제 | 2점 |
| File System Policy — 루트 거부 | 2점 |
| File System Policy — Role 제한 | 2점 |
| File System Policy — 태그 기반 (ABAC) | 2점 |
| File System Policy — Mount Target 경유 강제 | 1점 |
| Access Point 구성 | 2점 |
| TLS + AP 마운트 성공 | 2점 |
| fstab 자동 마운트 | 1점 |
| 서버 간 파일 공유 확인 | 2점 |
| TLS 미사용 마운트 거부 확인 | 1점 |
| **합계** | **28점** |
