# Module 1: Shared Network Storage — EFS 종합 레퍼런스

> 2026 서울시 지방기능경기대회 클라우드컴퓨팅 직종 대비

---

## 디렉토리 구조

```
module1/
├── README.md                          <- 이 파일 (마스터 레퍼런스)
├── access-point-guide.md              <- AP 상세 (PosixUser vs CreationInfo, 격리 패턴)
├── cheatsheet.md                      <- 마운트/CLI/fstab 빠른 참조
├── troubleshooting.md                 <- 자주 발생하는 오류 & 함정
├── policies/                          <- 개별 정책 패턴 (복붙 즉시 사용)
│   ├── 01-enforce-tls.json
│   ├── 02-read-only.json
│   ├── 03-deny-root-access.json
│   ├── 04-restrict-by-access-point.json
│   ├── 05-restrict-by-ip.json
│   ├── 06-time-based-access.json
│   ├── 07-abac-tag-based.json
│   ├── 08-cross-account.json
│   └── combined-examples/
│       ├── combo-01-full-security-baseline.json
│       ├── combo-02-multi-condition-app.json
│       └── combo-03-competition-style.json
├── cfn-templates/
│   └── efs-full-stack.yaml            <- VPC+SG+EFS+MT+AP+EC2 올인원
└── examples-questions/
    ├── GMS-example-tp.md
    ├── q01-basic-shared-storage.md
    ├── q02-multi-app-isolation.md
    ├── q03-security-hardened.md
    ├── q04-cross-az-with-lifecycle.md
    ├── q05-advanced-policy-challenge.md
    └── q06-eks-integration.md
```

---

## 1. EFS 핵심 개념

### 1.1 EFS란?
- 완전관리형 NFS v4.1 파일 시스템
- 다수 EC2/ECS/EKS/Lambda에서 동시 마운트 (ReadWriteMany)
- 자동 확장/축소 (페타바이트 규모)
- 리전 서비스 — 멀티 AZ 자동 복제

### 1.2 핵심 구성 요소

| 구성 요소 | 설명 |
|-----------|------|
| File System | EFS의 최상위 리소스. 생성 시 암호화 여부 결정 (변경 불가) |
| Mount Target | VPC 서브넷에 생성하는 ENI. AZ당 1개. NFS 2049 포트 사용 |
| Access Point | 애플리케이션별 진입점. POSIX UID/GID 강제, 루트 디렉토리 격리 |
| File System Policy | 리소스 기반 정책. NFS 클라이언트 접근 제어 (IAM 조건 기반) |
| Security Group | Mount Target에 연결. NFS 트래픽(TCP 2049) 인바운드 제어 |

### 1.3 DNS 이름 형식
```
fs-{id}.efs.{region}.amazonaws.com
```
예: `fs-0123456789abcdef0.efs.ap-northeast-2.amazonaws.com`

---

## 2. 성능 구성

### 2.1 Performance Mode (생성 시 결정, 변경 불가)

| 모드 | 특징 | 사용 사례 |
|------|------|----------|
| generalPurpose (기본) | 낮은 지연시간, 대부분 워크로드 적합 | 웹서버, CMS, 홈디렉토리 |
| maxIO | 높은 집계 처리량/IOPS, 약간 높은 지연 | 빅데이터, 미디어 처리 |

> maxIO는 Elastic Throughput, One Zone 스토리지와 호환 불가

### 2.2 Throughput Mode (변경 가능)

| 모드 | 특징 | 과금 |
|------|------|------|
| bursting (기본) | 저장 용량에 비례 (50 KiB/s per GiB), 버스트 크레딧 | 저장량 기반 |
| provisioned | 고정 처리량 지정 (MiB/s) | 프로비저닝량 기반 |
| elastic (권장) | 자동 스케일 (최대 10 GB/s 읽기 / 3 GB/s 쓰기) | 전송량 기반 |

---

## 3. 암호화

### 3.1 저장 시 암호화 (Encryption at Rest)
- 생성 시 Encrypted: true 설정 (이후 변경 불가!)
- KMS 키 미지정 시 -> AWS 관리형 키 aws/elasticfilesystem 사용
- 커스텀 CMK 사용 시 -> KmsKeyId에 KMS 키 ARN 지정

### 3.2 전송 중 암호화 (Encryption in Transit)
- 클라이언트 측에서 TLS 활성화: mount -t efs -o tls
- amazon-efs-utils 패키지 필수
- File System Policy로 TLS 미사용 거부 가능 (-> policies/01-enforce-tls.json)

---

## 4. 라이프사이클 정책

### 4.1 스토리지 클래스

| 클래스 | 설명 |
|--------|------|
| Standard | 기본. 자주 접근하는 데이터 |
| Infrequent Access (IA) | 자주 접근하지 않는 데이터. 저렴한 저장 비용, 접근 시 비용 발생 |
| Archive | 가장 저렴. 거의 접근하지 않는 데이터 |

### 4.2 전환 정책 값

| 정책 | 허용 값 |
|------|---------|
| TransitionToIA | AFTER_1_DAY, AFTER_7_DAYS, AFTER_14_DAYS, AFTER_30_DAYS, AFTER_60_DAYS, AFTER_90_DAYS, AFTER_180_DAYS, AFTER_270_DAYS, AFTER_365_DAYS |
| TransitionToArchive | 위와 동일 |
| TransitionToPrimaryStorageClass | AFTER_1_ACCESS (Intelligent-Tiering) |

### 4.3 CloudFormation 작성 시 주의
각 전환 정책은 배열 내 별도 객체로 작성:
```yaml
LifecyclePolicies:
  - TransitionToIA: AFTER_30_DAYS
  - TransitionToArchive: AFTER_90_DAYS
  - TransitionToPrimaryStorageClass: AFTER_1_ACCESS
```

---

## 5. Access Point 상세

-> 상세 가이드: [access-point-guide.md](./access-point-guide.md)

### 5.1 역할
- 애플리케이션별 격리된 진입점
- POSIX 사용자 ID 강제 (클라이언트 ID 무시)
- 루트 디렉토리 격리 (chroot와 유사)

### 5.2 주요 파라미터

| 파라미터 | 설명 | 예시 |
|----------|------|------|
| PosixUser.Uid | 강제 사용자 ID | 1000 |
| PosixUser.Gid | 강제 그룹 ID | 1000 |
| PosixUser.SecondaryGids | 보조 그룹 ID 배열 | [1001, 1002] |
| RootDirectory.Path | 루트로 사용할 경로 | /app/data |
| RootDirectory.CreationInfo.OwnerUid | 디렉토리 자동 생성 시 소유자 UID | 1000 |
| RootDirectory.CreationInfo.OwnerGid | 디렉토리 자동 생성 시 소유자 GID | 1000 |
| RootDirectory.CreationInfo.Permissions | 디렉토리 자동 생성 시 권한 (8진수) | 0755 |

### 5.3 ARN 형식
```
arn:aws:elasticfilesystem:{region}:{account}:access-point/{ap-id}
```

### 5.4 PosixUser vs CreationInfo 핵심 차이
- PosixUser: 매번 적용. 클라이언트 신분을 강제 덮어씀.
- CreationInfo: 딱 한 번. 디렉토리가 없을 때 자동 생성 시에만 적용.
- 자세한 내용은 [access-point-guide.md](./access-point-guide.md) 참조

---

## 6. File System Policy (리소스 기반 정책)

### 6.1 사용 가능한 EFS 액션

| 액션 | 설명 |
|------|------|
| elasticfilesystem:ClientMount | 읽기 전용 마운트 허용 |
| elasticfilesystem:ClientWrite | 쓰기 허용 (ClientMount 필요) |
| elasticfilesystem:ClientRootAccess | 루트(UID 0) 접근 허용. 거부 시 root squashing |

### 6.2 EFS 전용 Condition Key

| 키 | 타입 | 설명 |
|----|------|------|
| elasticfilesystem:AccessedViaMountTarget | Bool | Mount Target 경유 접근 여부 |
| elasticfilesystem:AccessPointArn | ARN | 특정 Access Point 경유 여부 |

### 6.3 사용 가능한 AWS 글로벌 Condition Key

| 키 | 타입 | 용도 |
|----|------|------|
| aws:SecureTransport | Bool | TLS 사용 여부 |
| aws:SourceIp | IpAddress | 소스 IP/CIDR 제한 |
| aws:PrincipalTag/${TagKey} | String | IAM 주체 태그 기반 (ABAC) |
| aws:CurrentTime | Date | 시간 기반 접근 제어 |
| aws:ResourceTag/${TagKey} | String | 리소스 태그 기반 |
| aws:RequestTag/${TagKey} | String | 요청 태그 강제 |
| aws:TagKeys | ArrayOfString | 허용 태그 키 제한 |

### 6.4 Condition Operator 레퍼런스

| 연산자 | 용도 | 예시 키 |
|--------|------|---------|
| Bool | 참/거짓 | aws:SecureTransport, elasticfilesystem:AccessedViaMountTarget |
| StringEquals / StringNotEquals | 정확한 문자열 일치 | aws:PrincipalTag/* |
| StringLike / StringNotLike | 와일드카드 매칭 (*, ?) | aws:PrincipalTag/* |
| ArnEquals / ArnLike | ARN 매칭 | elasticfilesystem:AccessPointArn |
| IpAddress / NotIpAddress | IP/CIDR 매칭 | aws:SourceIp |
| DateGreaterThan / DateLessThan | 시간 범위 | aws:CurrentTime |
| ForAllValues:StringEquals | 배열 내 모든 값 일치 | aws:TagKeys |
| ForAnyValue:StringEquals | 배열 내 하나라도 일치 | aws:TagKeys |

### 6.5 정책 패턴 파일 목록
-> policies/ 디렉토리 참조. 각 파일은 복사 후 즉시 사용 가능.

---

## 7. 복제 (Replication)

- 동일 리전 또는 교차 리전으로 자동 복제
- 대상 파일 시스템은 ReplicationOverwriteProtection: ENABLED (읽기 전용)
- 복제 삭제 시 대상이 쓰기 가능으로 전환
- CloudFormation: ReplicationConfiguration.Destinations 속성

---

## 8. 백업 (Backup)

- AWS Backup과 네이티브 통합
- BackupPolicy: { Status: ENABLED } -> 기본 백업 플랜 자동 적용
  - 일일 자동 백업, 35일 보존
- CloudFormation에서 BackupPolicy 속성으로 설정

---

## 9. 보안 그룹 설정

### 9.1 EFS Mount Target용 SG
```
인바운드: TCP 2049 (NFS) <- EC2 인스턴스의 SG (소스)
아웃바운드: 기본 (전체 허용)
```

### 9.2 EC2 인스턴스용 SG
```
아웃바운드: TCP 2049 (NFS) -> EFS Mount Target의 SG (대상)
+ 필요 시 SSH(22), HTTP(80/443) 등
```

### 9.3 핵심 포인트
- SG 소스를 IP가 아닌 SG ID로 지정 -> 인스턴스 추가/제거 시 자동 반영
- Mount Target SG에 EC2 SG를 소스로 지정하는 것이 모범 사례

---

## 10. CloudFormation 리소스 레퍼런스

### AWS::EFS::FileSystem
```yaml
Type: AWS::EFS::FileSystem
Properties:
  Encrypted: true
  KmsKeyId: !GetAtt MyKmsKey.Arn
  PerformanceMode: generalPurpose
  ThroughputMode: elastic
  ProvisionedThroughputInMibps: 100        # ThroughputMode가 provisioned일 때만
  BackupPolicy:
    Status: ENABLED
  LifecyclePolicies:
    - TransitionToIA: AFTER_30_DAYS
    - TransitionToArchive: AFTER_90_DAYS
    - TransitionToPrimaryStorageClass: AFTER_1_ACCESS
  FileSystemPolicy:
    Version: "2012-10-17"
    Statement: [...]
  FileSystemProtection:
    ReplicationOverwriteProtection: ENABLED
  ReplicationConfiguration:
    Destinations:
      - Region: us-west-2
        KmsKeyId: arn:aws:kms:us-west-2:111122223333:key/xxx
  FileSystemTags:
    - Key: Name
      Value: my-efs
```

### AWS::EFS::MountTarget
```yaml
Type: AWS::EFS::MountTarget
Properties:
  FileSystemId: !Ref MyFileSystem
  SubnetId: !Ref PrivateSubnetA
  SecurityGroups:
    - !Ref EfsSG
  IpAddress: 10.0.1.100                   # 선택. 미지정 시 자동 할당
```

### AWS::EFS::AccessPoint
```yaml
Type: AWS::EFS::AccessPoint
Properties:
  FileSystemId: !Ref MyFileSystem
  PosixUser:
    Uid: "1000"
    Gid: "1000"
    SecondaryGids:
      - "1001"
  RootDirectory:
    Path: /app/data
    CreationInfo:
      OwnerUid: "1000"
      OwnerGid: "1000"
      Permissions: "0755"
  AccessPointTags:
    - Key: Name
      Value: my-access-point
```

---

## 11. AWS CLI 명령어 레퍼런스

-> 상세 명령어는 [cheatsheet.md](./cheatsheet.md) 참조

---

## 12. 관련 파일 바로가기

| 파일 | 용도 |
|------|------|
| [access-point-guide.md](./access-point-guide.md) | AP 상세 (PosixUser vs CreationInfo, 격리 패턴) |
| [iam-guide.md](./iam-guide.md) | IAM Role, 인증 흐름, ABAC, File System Policy 관계 |
| [cheatsheet.md](./cheatsheet.md) | CLI/마운트/fstab 빠른 참조 |
| [troubleshooting.md](./troubleshooting.md) | 오류 해결 가이드 |
| [policies/](./policies/) | 정책 패턴 JSON 파일 |
| [cfn-templates/](./cfn-templates/) | CloudFormation 템플릿 |
| [examples-questions/](./examples-questions/) | 예시 과제 문제 |
