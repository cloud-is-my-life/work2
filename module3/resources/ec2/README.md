# EC2 Fine-grained IAM 실전 케이스

## 핵심 요약

> **⚠️ `RunInstances`는 다중 리소스 ARN 필요** — instance, volume, network-interface, security-group, subnet, image 등 최대 6개 리소스 타입을 동시에 지정해야 함.

> **⚠️ `ec2:ResourceTag` vs `aws:RequestTag` 구분** — 기존 리소스 제어는 `ResourceTag`, 생성 시 태그 강제는 `RequestTag`.

> **⚠️ `ec2:InstanceType` 조건은 `RunInstances`에만 적용** — `StartInstances`/`StopInstances`에는 태그 기반 제어 사용.

> **⚠️ EBS 암호화 강제는 `ec2:Encrypted` 조건** — `RunInstances`의 volume 리소스에 적용.

> **⚠️ `CreateTags`는 별도 Statement 필요** — `RunInstances`와 분리해서 `ec2:CreateAction` 조건으로 제어.

---

## 전용 Condition Key

| Condition Key | 적용 Action | 설명 |
|---|---|---|
| `ec2:InstanceType` | `RunInstances` | 인스턴스 타입 제한 |
| `ec2:ResourceTag/${TagKey}` | Start/Stop/Terminate/Describe 등 | 기존 리소스 태그 기반 |
| `aws:RequestTag/${TagKey}` | `RunInstances`, `CreateTags` | 생성 시 태그 강제 |
| `aws:TagKeys` | 태깅 액션 | 허용 태그 키 제한 |
| `ec2:Encrypted` | `RunInstances` (volume) | EBS 암호화 강제 |
| `ec2:VolumeType` | `RunInstances` (volume) | EBS 볼륨 타입 제한 |
| `ec2:VolumeSize` | `RunInstances` (volume) | EBS 볼륨 크기 제한 |
| `ec2:ImageId` | `RunInstances` | 허용 AMI 제한 |
| `ec2:Subnet` | `RunInstances` | 서브넷 제한 |
| `ec2:Vpc` | `RunInstances` | VPC 제한 |
| `ec2:Region` | 전체 | 리전 제한 |
| `ec2:Tenancy` | `RunInstances` | 테넌시 제한 |
| `ec2:IsLaunchTemplateResource` | `RunInstances` | Launch Template 강제 |
| `ec2:CreateAction` | `CreateTags` | 태그 생성을 허용할 원본 액션 |

---

## ARN 패턴

```
arn:aws:ec2:REGION:ACCOUNT_ID:instance/*
arn:aws:ec2:REGION:ACCOUNT_ID:volume/*
arn:aws:ec2:REGION:ACCOUNT_ID:network-interface/*
arn:aws:ec2:REGION:ACCOUNT_ID:security-group/*
arn:aws:ec2:REGION:ACCOUNT_ID:subnet/SUBNET_ID
arn:aws:ec2:REGION::image/ami-*
arn:aws:ec2:REGION:ACCOUNT_ID:key-pair/*
arn:aws:ec2:REGION:ACCOUNT_ID:launch-template/*
```

---

## 정책 파일

| 케이스 | 파일 | 의도 |
|---|---|---|
| Case 01 | `policies/case01-tag-based-start-stop.json` | 태그 기반 Start/Stop/Reboot 제한 |
| Case 02 | `policies/case02-run-instances-type-subnet.json` | RunInstances 인스턴스 타입 + 서브넷 제한 |
| Case 03 | `policies/case03-deny-terminate-production.json` | Production 태그 인스턴스 Terminate 차단 |
| Case 04 | `policies/case04-enforce-ebs-encryption.json` | EBS 암호화 강제 |
| Case 05 | `policies/case05-require-tags-on-create.json` | 생성 시 필수 태그 강제 |
| Case 06 | `policies/case06-launch-template-only.json` | Launch Template 없이 RunInstances 차단 |

---

## CloudShell 준비

```bash
export AWS_REGION="ap-northeast-2"
export ACCOUNT_ID="123456789012"
export USER_NAME="mod3-ec2-user"
export PROFILE_NAME="mod3-ec2-user"
```

---

## 검증 예시

```bash
# 태그 기반 — 자기 팀 인스턴스 Stop 성공 기대
aws ec2 stop-instances \
  --instance-ids i-0abc123def456 \
  --profile "$PROFILE_NAME"

# 다른 팀 인스턴스 Stop — AccessDenied 기대
aws ec2 stop-instances \
  --instance-ids i-0other789ghi \
  --profile "$PROFILE_NAME"

# 허용되지 않은 인스턴스 타입으로 RunInstances — AccessDenied 기대
aws ec2 run-instances \
  --image-id ami-XXXXXXXX \
  --instance-type m5.4xlarge \
  --subnet-id subnet-XXXXXXXX \
  --profile "$PROFILE_NAME"
```

---

## 감점 방지 포인트

- `RunInstances`에 instance ARN만 넣고 volume/network-interface ARN 빠뜨리면 실패
- `ec2:ResourceTag`는 이미 존재하는 리소스에만 동작 — 생성 시점에는 `aws:RequestTag` 사용
- `CreateTags`를 `RunInstances`와 같은 Statement에 넣으면 안 됨 — 별도 분리 필수
- `ec2:Encrypted` 조건은 volume 리소스 타입에만 적용 (instance 리소스에 넣으면 무시)
- AMI는 소유자가 다를 수 있으므로 ARN에 계정 ID 대신 `*` 사용: `arn:aws:ec2:REGION::image/*`
