# EFS Access Point 상세 가이드

> PosixUser vs CreationInfo 차이, 격리 패턴, 실전 구성법

---

## 1. Access Point 구성 요소

Access Point는 크게 두 파트로 나뉜다:

```yaml
AccessPoint:
  PosixUser:          # 파트 1: 이 AP로 접속하는 사람은 누구로 행동하나
    Uid: "1000"
    Gid: "1000"
    SecondaryGids: []
  RootDirectory:      # 파트 2: 이 AP의 루트 경로는 어디인가
    Path: /shared
    CreationInfo:     # (서브) 경로가 없을 때 자동 생성 설정
      OwnerUid: "1000"
      OwnerGid: "1000"
      Permissions: "0755"
```

---

## 2. PosixUser — 런타임 신분증 (매 요청마다 적용)

| 항목 | 설명 |
|------|------|
| 언제 적용? | AP를 통해 접근할 **때마다** |
| 뭘 하나? | 클라이언트의 실제 OS 사용자 ID를 **무시**하고, 설정된 UID/GID로 **강제 덮어씀** |
| root로 접속해도? | 무시됨. PosixUser의 UID/GID로 행동 |
| 파일 생성 시? | 소유자가 PosixUser의 UID:GID로 설정됨 |
| 파일 읽기 시? | PosixUser의 UID/GID 권한으로 접근 시도 |

```
[EC2 - root(UID 0)] ---> [Access Point: PosixUser UID=1000] ---> [EFS]
                           ^ 여기서 UID 0이 1000으로 바뀜
```

### 필드 상세

| 필드 | 필수 | 범위 | 설명 |
|------|------|------|------|
| Uid | O | 0 ~ 4294967295 | 강제 적용할 사용자 ID |
| Gid | O | 0 ~ 4294967295 | 강제 적용할 그룹 ID |
| SecondaryGids | X | 배열 | 보조 그룹 ID (최대 16개). 그룹 기반 공유 접근 시 사용 |

---

## 3. RootDirectory — AP의 루트 경로

| 항목 | 설명 |
|------|------|
| 뭘 하나? | AP로 접속한 클라이언트에게 이 경로를 `/`로 보이게 함 (chroot와 유사) |
| 격리 효과 | 클라이언트는 이 경로 바깥을 볼 수 없음 |

```
EFS 실제 구조:          클라이언트가 보는 구조:
/                       (접근 불가)
+-- alpha/              --> / (AP의 RootDirectory=/alpha)
|   +-- test.txt        --> /test.txt
|   +-- logs/           --> /logs/
+-- beta/               (접근 불가)
+-- config/             (접근 불가)
```

### Path
- AP의 루트로 사용할 EFS 내 절대 경로
- 예: `/alpha`, `/app/data`, `/shared`
- 미지정 시 EFS 루트(`/`)가 그대로 루트

---

## 4. CreationInfo — 디렉토리 자동 생성 (딱 한 번)

| 항목 | 설명 |
|------|------|
| 언제 적용? | RootDirectory.Path가 EFS에 **아직 없을 때**, 최초 1회 자동 생성 |
| 이미 존재하면? | **완전히 무시됨**. 기존 디렉토리의 소유자/권한 변경 안 함 |
| 미설정 시? | 경로가 없으면 AP 사용 불가 (마운트 실패) |

### 필드 상세

| 필드 | 필수 | 범위 | 설명 |
|------|------|------|------|
| OwnerUid | O | 0 ~ 4294967295 | 생성될 디렉토리의 소유자 UID |
| OwnerGid | O | 0 ~ 4294967295 | 생성될 디렉토리의 소유자 GID |
| Permissions | O | 8진수 문자열 | 디렉토리 POSIX 권한 (예: "0755") |

### 권한 값 참고

| 값 | 의미 | 사용 사례 |
|----|------|----------|
| 0755 | 소유자: rwx, 그룹: r-x, 기타: r-x | 일반적인 공유 디렉토리 |
| 0750 | 소유자: rwx, 그룹: r-x, 기타: --- | 그룹 내 공유, 외부 차단 |
| 0700 | 소유자: rwx, 그룹: ---, 기타: --- | 완전 격리 (소유자만 접근) |
| 0777 | 모두: rwx | 누구나 접근 (비권장) |

---

## 5. PosixUser vs CreationInfo 비교

| | PosixUser | CreationInfo |
|---|---|---|
| 비유 | 사원증 (매일 찍음) | 사무실 임대 계약서 (처음 한 번) |
| 적용 시점 | AP 통해 접근할 때마다 | 디렉토리 최초 생성 시 1회 |
| 대상 | 모든 파일/디렉토리 작업 | RootDirectory 경로 자체 |
| 이미 존재 시 | 항상 적용 | 무시 |
| 미설정 시 | 클라이언트 OS의 UID/GID 사용 | 경로 없으면 마운트 실패 |

### 값이 같아야 하나?

보통 같은 값을 넣지만, 반드시 같을 필요는 없다:

```yaml
# 일반적 (같은 값) — 경기에서 대부분 이 패턴
PosixUser:
  Uid: "1000"
  Gid: "1000"
RootDirectory:
  Path: /shared
  CreationInfo:
    OwnerUid: "1000"    # PosixUser와 동일
    OwnerGid: "1000"
    Permissions: "0755"
```

```yaml
# 다른 값도 가능 — 디렉토리는 root 소유, 작업은 앱 유저로
PosixUser:
  Uid: "1000"
  Gid: "1000"
RootDirectory:
  Path: /shared
  CreationInfo:
    OwnerUid: "0"       # 디렉토리 자체는 root 소유
    OwnerGid: "0"
    Permissions: "0777"  # 누구나 접근 가능하게
```

> 경기에서는 같은 값을 넣으라고 나올 확률이 높다.

---

## 6. 격리 패턴 — 멀티 앱 Access Point

하나의 EFS에 여러 AP를 만들어 앱별 격리:

```
EFS (fs-XXXXX)
+-- /alpha   <-- AP-Alpha (UID 1001, GID 1001, 0750)
+-- /beta    <-- AP-Beta  (UID 1002, GID 1002, 0750)
+-- /gamma   <-- AP-Gamma (UID 1003, GID 1003, 0700)
```

### 왜 격리가 되나?

1. **RootDirectory**: Alpha AP로 접속하면 `/alpha`가 `/`로 보임 -> `/beta` 경로 자체를 모름
2. **PosixUser**: Alpha는 UID 1001로 행동 -> `/beta`(UID 1002 소유, 0750)에 접근 권한 없음
3. **이중 격리**: 경로 격리 + 권한 격리가 동시에 작동

### CLI로 구성

```bash
# Alpha AP
aws efs create-access-point \
  --file-system-id fs-XXXXX \
  --posix-user Uid=1001,Gid=1001 \
  --root-directory "Path=/alpha,CreationInfo={OwnerUid=1001,OwnerGid=1001,Permissions=0750}" \
  --tags Key=Name,Value=wsi-ap-alpha

# Beta AP
aws efs create-access-point \
  --file-system-id fs-XXXXX \
  --posix-user Uid=1002,Gid=1002 \
  --root-directory "Path=/beta,CreationInfo={OwnerUid=1002,OwnerGid=1002,Permissions=0750}" \
  --tags Key=Name,Value=wsi-ap-beta
```

### CloudFormation으로 구성

```yaml
AlphaAccessPoint:
  Type: AWS::EFS::AccessPoint
  Properties:
    FileSystemId: !Ref EfsFileSystem
    PosixUser:
      Uid: "1001"
      Gid: "1001"
    RootDirectory:
      Path: /alpha
      CreationInfo:
        OwnerUid: "1001"
        OwnerGid: "1001"
        Permissions: "0750"
    AccessPointTags:
      - Key: Name
        Value: wsi-ap-alpha

BetaAccessPoint:
  Type: AWS::EFS::AccessPoint
  Properties:
    FileSystemId: !Ref EfsFileSystem
    PosixUser:
      Uid: "1002"
      Gid: "1002"
    RootDirectory:
      Path: /beta
      CreationInfo:
        OwnerUid: "1002"
        OwnerGid: "1002"
        Permissions: "0750"
    AccessPointTags:
      - Key: Name
        Value: wsi-ap-beta
```

### 마운트 (각 서버에서)

```bash
# Alpha 서버
sudo mount -t efs -o tls,accesspoint=fsap-ALPHA fs-XXXXX:/ /mnt/data
echo "fs-XXXXX:/ /mnt/data efs _netdev,tls,accesspoint=fsap-ALPHA 0 0" | sudo tee -a /etc/fstab

# Beta 서버
sudo mount -t efs -o tls,accesspoint=fsap-BETA fs-XXXXX:/ /mnt/data
echo "fs-XXXXX:/ /mnt/data efs _netdev,tls,accesspoint=fsap-BETA 0 0" | sudo tee -a /etc/fstab
```

### 격리 검증

```bash
# Alpha 서버에서
echo "alpha-secret" | sudo tee /mnt/data/test.txt
ls -la /mnt/data/test.txt
# 출력: -rw-r--r-- 1 1001 1001 ... test.txt

# Beta 서버에서
ls /mnt/data/
# 출력: (test.txt 안 보임 -- 다른 디렉토리니까)
echo "beta-data" | sudo tee /mnt/data/report.txt
ls -la /mnt/data/report.txt
# 출력: -rw-r--r-- 1 1002 1002 ... report.txt
```

---

## 7. SecondaryGids 활용 — 그룹 간 공유

팀 간 일부 데이터를 공유해야 할 때:

```yaml
# 공유 AP — 두 팀 모두 접근 가능
SharedAccessPoint:
  PosixUser:
    Uid: "1000"
    Gid: "1000"
    SecondaryGids:
      - "1001"    # Alpha 그룹
      - "1002"    # Beta 그룹
  RootDirectory:
    Path: /shared-data
    CreationInfo:
      OwnerUid: "1000"
      OwnerGid: "1000"
      Permissions: "0770"
```

이러면 이 AP로 접속한 클라이언트는 GID 1001, 1002 소유 파일 모두 그룹 권한으로 접근 가능.
