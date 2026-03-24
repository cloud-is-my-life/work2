# EFS IAM 가이드

> IAM Role 구성, 인증 흐름, ABAC, File System Policy와의 관계

---

## 0. 핵심 요약 (경기장에서 이것만 기억)

- **`-o iam` = 신분증 제시.** 안 쓰면 EFS가 니가 누군지 모름 (익명). 쓰면 IAM Role로 인증.
- **같은 계정 내에서는 IAM Role Policy든 EFS File System Policy든 둘 중 하나만 Allow면 접근 가능.** 둘 다 없으면 거부. Deny는 어디에 있든 무조건 우선.
- **File System Policy에 특정 Role ARN이 Principal이면 `-o iam` 필수.** Principal: * 이면 `-o iam` 없어도 OK.
- **ABAC(태그 기반)은 IAM Role 태그만 본다.** EC2 인스턴스 태그는 EFS가 안 봄.
- **File System Policy가 아예 없으면 EFS는 기본적으로 모든 마운트 허용.** 정책을 붙이는 순간부터 명시적 Allow 필요.

---

## 1. EFS 접근 시 IAM 인증 흐름

```
EC2 Instance
  +-- Instance Profile
        +-- IAM Role (identity-based policy + 태그)
              |
              v
        [mount -t efs -o tls,iam ...]
              |
              v
        EFS File System Policy (resource-based policy)
              |
              v
        접근 허용/거부
```

### 핵심: 두 가지 정책이 별개로 존재

| | Identity-based (IAM Role Policy) | Resource-based (EFS File System Policy) |
|---|---|---|
| 어디에 붙나? | IAM Role에 | EFS 파일 시스템에 |
| 누가 관리? | IAM 콘솔 | EFS 콘솔 |
| 뭘 제어? | "이 Role이 EFS API를 호출할 수 있는가" | "이 EFS에 누가 접근할 수 있는가" |
| 조건 키 | IAM 글로벌 조건만 | EFS 전용 + IAM 글로벌 조건 |

---

## 2. -o iam 유무에 따른 동작 차이

| 마운트 옵션 | IAM 인증 | 동작 |
|---|---|---|
| -o tls | 안 함 | 클라이언트가 신분 증명 안 함. File System Policy의 Principal: * 규칙만 적용 |
| -o tls,iam | 함 | EC2의 IAM Role 자격증명으로 인증. Role ARN 기반 정책 평가 가능 |

### 접근 허용 조건 (같은 계정 내)

| File System Policy | IAM Role Policy | -o iam | 결과 |
|---|---|---|---|
| Role A Allow | EFS 정책 없음 | O | **허용** (리소스 정책만으로 충분) |
| 없음 | EFS ReadWrite 정책 있음 | O | **허용** (identity 정책만으로 충분) |
| Role A Allow | EFS 정책 없음 | X | **거부** (신분 증명 안 해서 Role 매칭 불가) |
| Principal: * Allow | 무관 | X | **허용** (누구나 허용이니까) |
| Deny 규칙 존재 | 무관 | 무관 | **거부** (Deny는 항상 우선) |

> 경기 팁: 가장 안전한 조합은 IAM Role에 관리형 정책 붙이고 + File System Policy에서 조건(TLS, IP 등) 제어. -o iam 없이도 동작하면서 보안 조건은 적용됨.

---

## 3. IAM Role 생성 — 단계별

### 3.1 Trust Policy (누가 이 Role을 사용할 수 있나)

EC2가 사용하는 Role이면 항상 이 형태:

```json
{
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Principal": { "Service": "ec2.amazonaws.com" },
        "Action": "sts:AssumeRole"
    }]
}
```

### 3.2 Permission Policy (이 Role이 뭘 할 수 있나)

AWS 관리형 EFS 정책 3종:

| 정책 ARN | 권한 | 용도 |
|----------|------|------|
| AmazonElasticFileSystemClientReadWriteAccess | ClientMount + ClientWrite | 읽기/쓰기 (가장 흔함) |
| AmazonElasticFileSystemClientReadOnlyAccess | ClientMount만 | 읽기 전용 |
| AmazonElasticFileSystemClientFullAccess | ClientMount + ClientWrite + ClientRootAccess | 전체 (root 포함) |

### 3.3 Instance Profile (EC2에 Role 연결하는 컨테이너)

EC2는 Role을 직접 연결 못 함. Instance P이라는 래퍼가 필요:

```
EC2 Instance --> Instance Profile --> IAM Role
```

콘솔에서는 자동 생성되지만, CLI에서는 수동으로 만들어야 함.

---

## 4. CLI 전체 플로우

### 기본 (Role + 관리형 정책)

```bash
# 1. Role 생성
aws iam create-role \
  --role-name wsi-ec2-efs-role \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": { "Service": "ec2.amazonaws.com" },
      "Action": "sts:AssumeRole"
    }]
  }'

# 2. EFS 권한 부여
aws iam attach-role-policy \
  --role-name wsi-ec2-efs-role \
  --policy-arn arn:aws:iam::aws:policy/AmazonElasticFileSystemClientReadWriteAccess

# 3. SSM 접근 권한 (Session Manager 사용 시)
aws iam attach-role-policy \
  --role-name wsi-ec2-efs-role \
  --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore

# 4. Instance Profile 생성
aws iam create-instance-profile \
  --instance-profile-name wsi-ec2-efs-profile

# 5. Role을 Instance Profile에 연결
aws iam add-role-to-instance-profile \
  --instance-profile-name wsi-ec2-efs-profile \
  --role-name wsi-ec2-efs-role

# 6. EC2에 연결 (이미 실행 중인 인스턴스)
aws ec2 associate-iam-instance-profile \
  --instance-id i-XXXXX \
  --iam-instance-profile Name=wsi-ec2-efs-profile
```

### ABAC용 (Role에 태그 추가)

```bash
# Role 생성 시 태그 포함
aws iam create-role \
  --role-name wsi-ec2-efs-role \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": { "Service": "ec2.amazonaws.com" },
      "Action": "sts:AssumeRole"
    }]
  }' \
  --tags Key=AppRole,Value=wsi-app Key=Team,Value=engineering

# 이미 존재하는 Role에 태그 추가
aws iam tag-role \
  --role-name wsi-ec2-efs-role \
  --tags Key=AppRole,Value=wsi-app Key=Team,Value=engineering
```

---

## 5. CloudFormation

```yaml
Ec2EfsRole:
  Type: AWS::IAM::Role
  Properties:
    RoleName: wsi-ec2-efs-role
    AssumeRolePolicyDocument:
      Version: "2012-10-17"
      Statement:
        - Effect: Allow
          Principal:
            Service: ec2.amazonaws.com
          Action: sts:AssumeRole
    ManagedPolicyArns:
      - arn:aws:iam::aws:policy/AmazonElasticFileSystemClientReadWriteAccess
      - arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore
    Tags:
      - Key: AppRole
        Value: wsi-app
      - Key: Team
        Value: engineering

Ec2InstanceProfile:
  Type: AWS::IAM::InstanceProfile
  Properties:
    InstanceProfileName: wsi-ec2-efs-profile
    Roles:
      - !Ref Ec2EfsRole
```

EC2에서 참조:
```yaml
AppServer:
  Type: AWS::EC2::Instance
  Properties:
    IamInstanceProfile: !Ref Ec2InstanceProfile
    # ...
```

---

## 6. ABAC (태그 기반 접근 제어)

### aws:PrincipalTag는 IAM Role 태그만 본다

```
EC2 인스턴스 태그: Team=engineering     <-- EFS가 안 봄
IAM Role 태그:    Team=engineering     <-- EFS가 이걸 봄
```

EC2 인스턴스에 아무리 태그를 달아도 EFS File System Policy의 aws:PrincipalTag 조건에는 영향 없음.

### ABAC 동작 흐름

```
EC2 (인스턴스 태그 무관)
  --> Instance Profile
    --> IAM Role (Tags: AppRole=wsi-app)
      --> EFS File System Policy 평가
        --> aws:PrincipalTag/AppRole == "wsi-app" ? --> 허용
```

### File System Policy에서 ABAC 사용

```json
{
    "Sid": "AllowByTag",
    "Effect": "Allow",
    "Principal": { "AWS": "*" },
    "Action": [
        "elasticfilesystem:ClientMount",
        "elasticfilesystem:ClientWrite"
    ],
    "Condition": {
        "StringEquals": {
            "aws:PrincipalTag/AppRole": "wsi-app"
        }
    }
}
```

이 정책은 Principal이 *이지만, AppRole=wsi-app 태그가 있는 IAM Role만 통과시킴.

### 여러 태그 조합 (AND)

같은 Condition 블록 안의 조건은 AND:

```json
"Condition": {
    "StringEquals": {
        "aws:PrincipalTag/AppRole": "wsi-app",
        "aws:PrincipalTag/Team": "engineering"
    }
}
```
--> AppRole=wsi-app AND Team=engineering 둘 다 있어야 허용

---

## 7. 커스텀 IAM Policy (관리형 대신 직접 작성)

특정 EFS만 접근 허용하고 싶을 때:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "AllowEfsAccess",
            "Effect": "Allow",
            "Action": [
                "elasticfilesystem:ClientMount",
                "elasticfilesystem:ClientWrite",
                "elasticfilesystem:DescribeMountTargets"
            ],
            "Resource": "arn:aws:elasticfilesystem:ap-northeast-2:ACCOUNT_ID:file-system/fs-XXXXX"
        }
    ]
}
```

```bash
# 인라인 정책으로 Role에 직접 부착
aws iam put-role-policy \
  --role-name wsi-ec2-efs-role \
  --policy-name efs-custom-access \
  --policy-document file://custom-efs-policy.json
```

---

## 8. 경기 중 빠른 참조

### 가장 흔한 패턴 (복붙용)

```bash
# Role 생성 + 정책 + Instance Profile + 태그 한 번에
aws iam create-role \
  --role-name wsi-ec2-efs-role \
  --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}]}' \
  --tags Key=AppRole,Value=wsi-app

aws iam attach-role-policy \
  --role-name wsi-ec2-efs-role \
  --policy-arn arn:aws:iam::aws:policy/AmazonElasticFileSystemClientReadWriteAccess

aws iam create-instance-profile \
  --instance-profile-name wsi-ec2-efs-profile

aws iam add-role-to-instance-profile \
  --instance-profile-name wsi-ec2-efs-profile \
  --role-name wsi-ec2-efs-role
```

### EC2 시작 시 Role 지정 (run-instances)

```bash
aws ec2 run-instances \
  --image-id ami-XXXXX \
  --instance-type t3.micro \
  --subnet-id subnet-XXXXX \
  --security-group-ids sg-XXXXX \
  --iam-instance-profile Name=wsi-ec2-efs-profile \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=wsi-app-server}]'
```

### 이미 실행 중인 EC2에 Role 연결

```bash
aws ec2 associate-iam-instance-profile \
  --instance-id i-XXXXX \
  --iam-instance-profile Name=wsi-ec2-efs-profile
```

### Role 확인

```bash
# Role에 붙은 정책 확인
aws iam list-attached-role-policies --role-name wsi-ec2-efs-role

# Role 태그 확인
aws iam list-role-tags --role-name wsi-ec2-efs-role

# EC2에 연결된 Instance Profile 확인
aws ec2 describe-iam-instance-profile-associations \
  --filters Name=instance-id,Values=i-XXXXX
```

---

## 9. 삭제 순서 (의존성 주의)

```bash
# 1. EC2에서 Instance Profile 분리
aws ec2 disassociate-iam-instance-profile \
  --association-id iip-assoc-XXXXX

# 2. Instance Profile에서 Role 제거
aws iam remove-role-from-instance-profile \
  --instance-profile-name wsi-ec2-efs-profile \
  --role-name wsi-ec2-efs-role

# 3. Instance Profile 삭제
aws iam delete-instance-profile \
  --instance-profile-name wsi-ec2-efs-profile

# 4. Role에서 정책 분리
aws iam detach-role-policy \
  --role-name wsi-ec2-efs-role \
  --policy-arn arn:aws:iam::aws:policy/AmazonElasticFileSystemClientReadWriteAccess

# 5. Role 삭제
aws iam delete-role --role-name wsi-ec2-efs-role
```

---

## 10. 자주 하는 실수

| 실수 | 증상 | 해결 |
|------|------|------|
| Instance Profile 안 만듦 | EC2에 Role 연결 불가 | create-instance-profile + add-role-to-instance-profile |
| -o iam 빼먹음 | File System Policy의 Role 기반 Allow가 안 먹힘 | mount 옵션에 iam 추가 |
| EC2 태그로 ABAC 시도 | 조건 매칭 안 됨 | IAM Role에 태그 달아야 함 |
| Role 생성 후 바로 사용 | 간헐적 접근 실패 | IAM 전파 지연 (수 초). 잠시 대기 |
| 관리형 정책 이름 오타 | attach 실패 | 정확한 ARN 확인: arn:aws:iam::aws:policy/Amazon... |
