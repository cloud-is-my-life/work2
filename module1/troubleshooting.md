# EFS 트러블슈팅 가이드

> 경기 중 자주 만나는 오류와 해결법. 시간 절약이 핵심.

---

## 1. 마운트 실패

### 증상: `mount.nfs4: Connection timed out`
- 원인: 보안 그룹에서 NFS(TCP 2049) 미허용
- 해결:
  ```bash
  # EFS Mount Target SG에 인바운드 규칙 추가
  aws ec2 authorize-security-group-ingress \
    --group-id sg-EFS_SG_ID \
    --protocol tcp --port 2049 \
    --source-group sg-EC2_SG_ID
  ```

### 증상: `mount.nfs4: No such file or directory`
- 원인: 마운트 포인트 디렉토리 미생성
- 해결: `sudo mkdir -p /mnt/efs`

### 증상: `mount: unknown filesystem type 'efs'`
- 원인: `amazon-efs-utils` 미설치
- 해결:
  ```bash
  sudo yum install -y amazon-efs-utils   # Amazon Linux
  ```

### 증상: `Failed to resolve "fs-XXXXX.efs.ap-northeast-2.amazonaws.com"`
- 원인 1: Mount Target이 해당 AZ에 없음
- 원인 2: VPC DNS 설정 비활성화
- 해결:
  ```bash
  # Mount Target 확인
  aws efs describe-mount-targets --file-system-id fs-XXXXX

  # VPC DNS 활성화
  aws ec2 modify-vpc-attribute --vpc-id vpc-XXXXX --enable-dns-support '{"Value":true}'
  aws ec2 modify-vpc-attribute --vpc-id vpc-XXXXX --enable-dns-hostnames '{"Value":true}'
  ```

### 증상: `mount.nfs4: access denied by server`
- 원인 1: File System Policy에서 거부됨
- 원인 2: IAM 인증 필요한데 `-o iam` 미사용
- 원인 3: TLS 필수인데 `-o tls` 미사용
- 해결:
  ```bash
  # 정책 확인
  aws efs describe-file-system-policy --file-system-id fs-XXXXX

  # TLS + IAM으로 재마운트
  sudo umount /mnt/efs
  sudo mount -t efs -o tls,iam fs-XXXXX:/ /mnt/efs
  ```

---

## 2. TLS 관련

### 증상: `stunnel: SSL_connect returned error`
- 원인: stunnel 패키지 미설치 또는 버전 문제
- 해결:
  ```bash
  sudo yum install -y stunnel   # Amazon Linux
  sudo apt-get install -y stunnel4   # Ubuntu
  ```

### 증상: TLS 마운트 시 `EFS Mount Helper: TLS is not supported`
- 원인: `amazon-efs-utils` 버전이 너무 오래됨
- 해결:
  ```bash
  sudo yum update -y amazon-efs-utils
  ```

---

## 3. Access Point 관련

### 증상: AP 마운트 시 `access denied`
- 원인 1: File System Policy에서 해당 AP ARN 미허용
- 원인 2: AP 마운트 시 TLS 미사용 (AP는 TLS 필수)
- 해결:
  ```bash
  # 반드시 tls 옵션과 함께 사용
  sudo mount -t efs -o tls,accesspoint=fsap-XXXXX fs-XXXXX:/ /mnt/efs
  ```

### 증상: AP로 마운트했는데 파일 소유자가 예상과 다름
- 원인: AP의 PosixUser 설정 확인 필요
- 해결:
  ```bash
  aws efs describe-access-points --access-point-id fsap-XXXXX
  # PosixUser의 Uid/Gid 확인
  ```

### 증상: AP의 RootDirectory 경로에 접근 불가
- 원인: CreationInfo 미설정 + 경로가 존재하지 않음
- 해결: AP 재생성 시 CreationInfo 포함
  ```bash
  aws efs create-access-point \
    --file-system-id fs-XXXXX \
    --root-directory "Path=/app,CreationInfo={OwnerUid=1000,OwnerGid=1000,Permissions=0755}"
  ```

---

## 4. 권한 관련

### 증상: `Permission denied` (파일 생성/수정 시)
- 원인 1: File System Policy에서 `ClientWrite` 미허용
- 원인 2: POSIX 파일 권한 문제
- 원인 3: Root squashing 활성화 상태에서 root로 작업 시도
- 해결:
  ```bash
  # 정책에서 ClientWrite 확인
  aws efs describe-file-system-policy --file-system-id fs-XXXXX

  # POSIX 권한 확인
  ls -la /mnt/efs/

  # root squashing 확인 — ClientRootAccess가 Deny인지 확인
  # 필요 시 일반 사용자로 작업하거나 AP의 PosixUser 활용
  ```

### 증상: `Operation not permitted` (chown/chmod 시)
- 원인: Root access가 거부됨 (root squashing)
- 해결: Access Point의 PosixUser로 소유권 자동 설정 활용

---

## 5. fstab 관련

### 증상: 재부팅 후 마운트 안 됨
- 원인 1: `_netdev` 옵션 누락
- 원인 2: `amazon-efs-utils` 미설치 상태에서 `efs` 타입 사용
- 해결:
  ```bash
  # fstab 확인 — _netdev 필수!
  cat /etc/fstab
  # 올바른 예: fs-XXXXX:/ /mnt/efs efs _netdev,tls 0 0
  ```

### 증상: 부팅 시 행(hang) — 부팅 불가
- 원인: fstab에 잘못된 EFS 엔트리 + `_netdev` 누락
- 해결:
  1. EC2 인스턴스 중지
  2. 루트 볼륨을 다른 인스턴스에 연결
  3. fstab 수정
  4. 볼륨 재연결 후 시작

### fstab 안전 테스트
```bash
# 마운트 전 문법 검증 (실제 마운트 안 함)
sudo mount -fav

# 문제 없으면 실제 마운트
sudo mount -av
```

---

## 6. 성능 관련

### 증상: 처리량이 예상보다 낮음
- 원인: Bursting 모드에서 크레딧 소진
- 해결:
  ```bash
  # CloudWatch에서 BurstCreditBalance 확인
  # 또는 Throughput Mode 변경
  aws efs update-file-system \
    --file-system-id fs-XXXXX \
    --throughput-mode elastic
  ```

### 증상: `maxIO` 모드 변경 불가
- 원인: Performance Mode는 생성 후 변경 불가
- 해결: 새 파일 시스템 생성 후 DataSync로 데이터 이전

---

## 7. 삭제 관련

### 증상: `FileSystemInUse` — 파일 시스템 삭제 실패
- 원인: Mount Target이 아직 존재
- 해결: 삭제 순서 준수
  ```bash
  # 1. EC2에서 umount
  sudo umount /mnt/efs

  # 2. Access Point 삭제
  aws efs delete-access-point --access-point-id fsap-XXXXX

  # 3. Mount Target 삭제 (모든 AZ)
  aws efs delete-mount-target --mount-target-id fsmt-XXXXX
  # Mount Target 삭제 완료까지 대기 (약 1-2분)

  # 4. 파일 시스템 삭제
  aws efs delete-file-system --file-system-id fs-XXXXX
  ```

---

## 8. 경기 중 빠른 디버깅 체크리스트

문제 발생 시 이 순서로 확인:

1. ✅ `amazon-efs-utils` 설치됨?
2. ✅ Mount Target이 해당 AZ에 존재?
3. ✅ SG에서 TCP 2049 인바운드 허용?
4. ✅ VPC DNS Support/Hostnames 활성화?
5. ✅ File System Policy가 접근을 거부하지 않는지?
6. ✅ TLS 필수 정책인데 `-o tls` 사용했는지?
7. ✅ AP 사용 시 `-o tls,accesspoint=fsap-XXX` 형식인지?
8. ✅ IAM Role이 EC2에 연결되어 있는지? (IAM 인증 시)
9. ✅ fstab에 `_netdev` 포함?
10. ✅ 마운트 포인트 디렉토리 존재?
