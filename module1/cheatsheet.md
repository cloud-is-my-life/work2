# EFS 빠른 참조 치트시트

> 경기 중 즉시 조회용. 복사 → 붙여넣기 → 실행.

---

## 1. amazon-efs-utils 설치

```bash
# Amazon Linux 2 / 2023
sudo yum install -y amazon-efs-utils

# Ubuntu / Debian
sudo apt-get update && sudo apt-get install -y git binutils stunnel4
git clone https://github.com/aws/efs-utils && cd efs-utils
./build-deb.sh && sudo apt-get install -y ./build/amazon-efs-utils*deb
```

---

## 2. 마운트 명령어

```bash
# 마운트 디렉토리 생성
sudo mkdir -p /mnt/efs # 이거 경기에 맞게 디렉토리 수정해야 함. 

# 기본 마운트
sudo mount -t efs fs-XXXXX:/ /mnt/efs

# TLS 암호화 마운트
sudo mount -t efs -o tls fs-XXXXX:/ /mnt/efs

# TLS + Access Point
sudo mount -t efs -o tls,accesspoint=fsap-XXXXX fs-XXXXX:/ /mnt/efs

# TLS + IAM 인증
sudo mount -t efs -o tls,iam fs-XXXXX:/ /mnt/efs

# TLS + IAM + Access Point
sudo mount -t efs -o tls,iam,accesspoint=fsap-XXXXX fs-XXXXX:/ /mnt/efs

# 서브디렉토리 마운트
sudo mount -t efs -o tls fs-XXXXX:/subdir /mnt/efs

# NFS4 폴백 (efs-utils 없을 때)
sudo mount -t nfs4 -o nfsvers=4.1,rsize=1048576,wsize=1048576,hard,timeo=600,retrans=2,noresvport \
  fs-XXXXX.efs.ap-northeast-2.amazonaws.com:/ /mnt/efs
```

---

## 3. /etc/fstab (재부팅 자동 마운트)

이거 다이렉트로 sudo nano /etc/fstab 하면 됨.  
이거 실수하면 hang나면서 ec2가 갑자기 죽어버릴 수 있으니 주의.  

```bash
# TLS 마운트
fs-XXXXX:/ /mnt/efs efs _netdev,tls 0 0

# TLS + Access Point
fs-XXXXX:/ /mnt/efs efs _netdev,tls,accesspoint=fsap-XXXXX 0 0

# TLS + IAM
fs-XXXXX:/ /mnt/efs efs _netdev,tls,iam 0 0

# TLS + IAM + Access Point
fs-XXXXX:/ /mnt/efs efs _netdev,tls,iam,accesspoint=fsap-XXXXX 0 0

# NFS4 폴백
fs-XXXXX.efs.ap-northeast-2.amazonaws.com:/ /mnt/efs nfs4 nfsvers=4.1,rsize=1048576,wsize=1048576,hard,timeo=600,retrans=2,noresvport,_netdev 0 0
```

> ⚠️ `_netdev` 필수! 네트워크 초기화 후 마운트 보장. 없으면 부팅 실패 가능.

### fstab 적용 테스트
```bash
sudo mount -fav    # fstab 문법 검증 (실제 마운트 안 함)
sudo mount -av     # fstab 기반 전체 마운트
```

---

## 4. AWS CLI 명령어

### 파일 시스템 생성
```bash
aws efs create-file-system \
  --performance-mode generalPurpose \
  --throughput-mode elastic \
  --encrypted \
  --kms-key-id alias/wsi-efs-key \
  --tags Key=Name,Value=wsi-shared-efs \
  --region ap-northeast-2
```

### 마운트 타겟 생성 (AZ별 1개)
```bash
aws efs create-mount-target \
  --file-system-id fs-XXXXX \
  --subnet-id subnet-XXXXX \
  --security-groups sg-XXXXX \
  --region ap-northeast-2
```

### Access Point 생성
```bash
aws efs create-access-point \
  --file-system-id fs-XXXXX \
  --posix-user Uid=1000,Gid=1000 \
  --root-directory "Path=/shared,CreationInfo={OwnerUid=1000,OwnerGid=1000,Permissions=0755}" \
  --tags Key=Name,Value=wsi-efs-ap \
  --region ap-northeast-2
```

### 파일 시스템 정책 적용
```bash
aws efs put-file-system-policy \
  --file-system-id fs-XXXXX \
  --policy file://policy.json \
  --region ap-northeast-2
```

### 라이프사이클 정책 설정
```bash
aws efs put-lifecycle-configuration \
  --file-system-id fs-XXXXX \
  --lifecycle-policies \
    '[{"TransitionToIA":"AFTER_30_DAYS"},{"TransitionToArchive":"AFTER_90_DAYS"},{"TransitionToPrimaryStorageClass":"AFTER_1_ACCESS"}]' \
  --region ap-northeast-2
```

### 조회 명령어
```bash
# 파일 시스템 목록
aws efs describe-file-systems --region ap-northeast-2

# 특정 파일 시스템
aws efs describe-file-systems --file-system-id fs-XXXXX

# 마운트 타겟 조회
aws efs describe-mount-targets --file-system-id fs-XXXXX

# Access Point 조회
aws efs describe-access-points --file-system-id fs-XXXXX

# 파일 시스템 정책 조회
aws efs describe-file-system-policy --file-system-id fs-XXXXX

# 라이프사이클 정책 조회
aws efs describe-lifecycle-configuration --file-system-id fs-XXXXX
```

### 삭제 순서 (의존성 주의!)
```bash
# 1. 마운트 해제 (EC2에서)
sudo umount /mnt/efs

# 2. Access Point 삭제
aws efs delete-access-point --access-point-id fsap-XXXXX

# 3. Mount Target 삭제 (모든 AZ)
aws efs delete-mount-target --mount-target-id fsmt-XXXXX

# 4. 파일 시스템 삭제 (Mount Target 삭제 완료 후)
aws efs delete-file-system --file-system-id fs-XXXXX
```

---

## 5. 파일 공유 검증

```bash
# Server A에서
echo "hello from server-a" | sudo tee /mnt/efs/test.txt

# Server C에서
cat /mnt/efs/test.txt
# 출력: hello from server-a
```

---

## 6. 마운트 상태 확인

```bash
# 마운트 확인
df -h | grep efs
mount | grep efs

# EFS 마운트 헬퍼 로그
sudo cat /var/log/amazon/efs/mount.log

# stunnel (TLS) 로그
sudo cat /var/log/amazon/efs/stunnel.log

# NFS 통계
nfsstat -c
```

---

## 7. 자주 쓰는 조합 (경기용)

### 전형적인 경기 과제 순서
```bash
# 1. efs-utils 설치
sudo yum install -y amazon-efs-utils

# 2. 마운트 디렉토리 생성
sudo mkdir -p /mnt/shared

# 3. TLS + Access Point 마운트
sudo mount -t efs -o tls,accesspoint=fsap-XXXXX fs-XXXXX:/ /mnt/shared

# 4. fstab 등록 (재부팅 자동 마운트)
echo "fs-XXXXX:/ /mnt/shared efs _netdev,tls,accesspoint=fsap-XXXXX 0 0" | sudo tee -a /etc/fstab

# 5. 검증
sudo mount -fav
echo "test" | sudo tee /mnt/shared/test.txt
cat /mnt/shared/test.txt
```

---

## 8. 보안 그룹 CLI

```bash
# EFS용 SG 생성
aws ec2 create-security-group \
  --group-name sg-wsi-efs \
  --description "EFS Mount Target SG" \
  --vpc-id vpc-XXXXX

# NFS 인바운드 규칙 (EC2 SG에서만 허용)
aws ec2 authorize-security-group-ingress \
  --group-id sg-XXXXX \
  --protocol tcp \
  --port 2049 \
  --source-group sg-EC2XXXXX
```
