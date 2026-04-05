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

## 케이스별 상세 설명

### Case 01 — 태그 기반 Start/Stop/Reboot 제한

**시나리오**: `Team` 태그가 자기 팀과 일치하는 인스턴스만 Start/Stop/Reboot 허용. 다른 팀 인스턴스는 조작 불가.

**핵심 메커니즘**:
- `ec2:ResourceTag/Team` + `StringEquals` + `${aws:PrincipalTag/Team}` 동적 매칭
- Action: `ec2:StartInstances`, `ec2:StopInstances`, `ec2:RebootInstances`

**허용**: 자기 팀 태그 인스턴스 Start/Stop/Reboot
**거부**: 다른 팀 인스턴스 조작 시 `AccessDenied`

**주의사항**:
- `ec2:ResourceTag`는 **이미 존재하는** 인스턴스에만 동작 — 생성 시점에는 `aws:RequestTag` 사용
- `DescribeInstances`는 태그 기반 필터링 불가 → `Resource: "*"` 별도 허용 필요
- 태그 미설정 인스턴스는 조건 불일치로 자동 거부됨

---

### Case 02 — RunInstances 인스턴스 타입 + 서브넷 제한

**시나리오**: 허용된 인스턴스 타입(`t3.micro`, `t3.small`)과 특정 서브넷에서만 인스턴스 생성 가능.

**핵심 메커니즘**:
- `ec2:InstanceType` + `StringEquals` → 허용 타입 목록
- `ec2:Subnet` → 허용 서브넷 ARN
- Resource에 instance, volume, network-interface, security-group, subnet, image 6개 리소스 타입 모두 지정

**허용**: `t3.micro`/`t3.small` + 지정 서브넷에서 `RunInstances`
**거부**: `m5.4xlarge` 등 비허용 타입 또는 다른 서브넷에서 생성 시 `AccessDenied`

**주의사항**:
- `RunInstances`는 **다중 리소스 타입** 필요 — instance ARN만 넣으면 volume/network-interface 생성 단계에서 실패
- `ec2:InstanceType` 조건은 `RunInstances`에만 적용 — `ModifyInstanceAttribute`로 타입 변경은 별도 제어 필요
- 서브넷 조건은 `ec2:Subnet` (서브넷 ARN) 또는 `ec2:Vpc` (VPC ARN)로 지정

---

### Case 03 — Production 태그 인스턴스 Terminate 차단

**시나리오**: `Environment=Production` 태그가 붙은 인스턴스는 누구도 Terminate 불가. Explicit Deny로 구현.

**핵심 메커니즘**:
- Deny: `ec2:TerminateInstances` + `ec2:ResourceTag/Environment: "Production"`
- Allow: 그 외 인스턴스에 대한 일반 관리 작업

**허용**: `Environment=Development` 등 비프로덕션 인스턴스 Terminate
**거부**: `Environment=Production` 인스턴스 Terminate → `AccessDenied` (관리자 포함)

**주의사항**:
- Explicit Deny는 어떤 Allow보다 우선 — 관리자 정책에 `ec2:*` Allow가 있어도 Deny가 이김
- 태그 제거 후 Terminate 우회 방지 → `ec2:DeleteTags` + `aws:TagKeys` 조건으로 `Environment` 태그 삭제도 차단 권장
- `StopInstances`는 별도 — Terminate만 차단하면 Stop은 가능

---

### Case 04 — EBS 암호화 강제

**시나리오**: `RunInstances` 시 EBS 볼륨이 암호화되지 않으면 인스턴스 생성 거부.

**핵심 메커니즘**:
- Deny: `ec2:RunInstances` + Resource `arn:aws:ec2:*:*:volume/*` + `ec2:Encrypted: "false"`
- 또는 Allow에 `ec2:Encrypted: "true"` 조건 추가

**허용**: 암호화된 EBS 볼륨으로 인스턴스 생성
**거부**: 비암호화 EBS 볼륨 포함 시 `AccessDenied`

**주의사항**:
- `ec2:Encrypted` 조건은 **volume 리소스 타입에만** 적용 — instance 리소스에 넣으면 무시됨
- Deny 패턴에서 Resource를 `arn:aws:ec2:*:*:volume/*`로 한정해야 다른 리소스 타입에 영향 없음
- 계정 수준 EBS 기본 암호화 설정(`aws ec2 enable-ebs-encryption-by-default`)과 병행 권장
- 특정 KMS 키 강제는 `ec2:VolumeKmsKeyId` 조건 추가

---

### Case 05 — 생성 시 필수 태그 강제

**시나리오**: `RunInstances` 시 `Environment`와 `Team` 태그가 반드시 포함되어야 함. 태그 없으면 생성 거부.

**핵심 메커니즘**:
- Deny: `ec2:RunInstances` + `aws:RequestTag/Environment` `Null: "true"` → 태그 누락 시 거부
- Deny: `aws:RequestTag/Team` `Null: "true"` → 태그 누락 시 거부
- Allow: `ec2:CreateTags` + `ec2:CreateAction: "RunInstances"` → RunInstances 시점에만 태그 생성 허용

**허용**: `Environment` + `Team` 태그 포함한 `RunInstances`
**거부**: 태그 누락 시 `AccessDenied`

**주의사항**:
- `CreateTags`는 `RunInstances`와 **별도 Statement** 필요 — 같은 Statement에 넣으면 안 됨
- `ec2:CreateAction` 조건으로 `CreateTags`를 `RunInstances` 시점에만 허용 → 기존 인스턴스에 임의 태그 추가 방지
- `aws:TagKeys` + `ForAllValues:StringEquals`로 허용 태그 키 목록도 제한 가능
- 태그 값 패턴 제한은 `aws:RequestTag/Environment` + `StringEquals: ["Production", "Development", "Staging"]`

---

### Case 06 — Launch Template 없이 RunInstances 차단

**시나리오**: 사전 승인된 Launch Template을 사용해야만 인스턴스 생성 가능. 직접 파라미터 지정 차단.

**핵심 메커니즘**:
- Deny: `ec2:RunInstances` + `ec2:IsLaunchTemplateResource: "false"` → Launch Template 미사용 시 거부
- 또는 Allow에 `ec2:IsLaunchTemplateResource: "true"` 조건 추가

**허용**: Launch Template 기반 `RunInstances`
**거부**: `--image-id`, `--instance-type` 등 직접 파라미터로 생성 시 `AccessDenied`

**주의사항**:
- `ec2:IsLaunchTemplateResource`는 Bool 타입 — `"true"`/`"false"` 문자열로 비교
- Launch Template 자체의 수정 권한(`ec2:CreateLaunchTemplateVersion`)도 별도 제어 필요 — 아니면 사용자가 템플릿 수정으로 우회 가능
- 특정 Launch Template만 허용하려면 Resource에 `arn:aws:ec2:REGION:ACCOUNT:launch-template/lt-XXXX` 지정

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
