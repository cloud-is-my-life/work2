# EC2 Fine-grained IAM 실전 가이드

> AWS Skills Competition 2026 대비. EC2 IAM 정책의 핵심 패턴을 시나리오 중심으로 정리했다.

---

## RunInstances 다중 리소스 완전 정복

경기에서 가장 많이 틀리는 부분이다. `RunInstances`는 단일 리소스가 아니라 **최대 6개 리소스 타입**에 동시에 권한이 필요하다.

### 왜 다중 리소스가 필요한가

인스턴스를 생성할 때 AWS는 내부적으로 여러 리소스를 함께 만든다.

- `instance` — 인스턴스 자체
- `volume` — EBS 루트 볼륨
- `network-interface` — 기본 네트워크 인터페이스
- `security-group` — 연결할 보안 그룹
- `subnet` — 배치할 서브넷
- `image` — 사용할 AMI

IAM은 각 리소스 타입별로 권한을 평가한다. `instance` ARN만 허용하면 `volume` 생성 단계에서 `AccessDenied`가 난다.

### 올바른 Statement 구조

```json
{
  "Sid": "AllowRunInstancesInstance",
  "Effect": "Allow",
  "Action": "ec2:RunInstances",
  "Resource": "arn:aws:ec2:AWS_REGION:ACCOUNT_ID:instance/*",
  "Condition": {
    "StringEquals": {
      "ec2:InstanceType": ["t3.micro", "t3.small"]
    }
  }
},
{
  "Sid": "AllowRunInstancesSupportingResources",
  "Effect": "Allow",
  "Action": "ec2:RunInstances",
  "Resource": [
    "arn:aws:ec2:AWS_REGION:ACCOUNT_ID:volume/*",
    "arn:aws:ec2:AWS_REGION:ACCOUNT_ID:network-interface/*",
    "arn:aws:ec2:AWS_REGION:ACCOUNT_ID:security-group/*",
    "arn:aws:ec2:AWS_REGION:ACCOUNT_ID:subnet/*",
    "arn:aws:ec2:AWS_REGION::image/ami-*",
    "arn:aws:ec2:AWS_REGION:ACCOUNT_ID:key-pair/*"
  ]
}
```

### 리소스별 조건 키 적용 범위

| 리소스 타입 | 적용 가능한 조건 키 |
|---|---|
| `instance` | `ec2:InstanceType`, `ec2:Tenancy`, `ec2:IsLaunchTemplateResource`, `ec2:InstanceMarketType` |
| `volume` | `ec2:VolumeType`, `ec2:VolumeSize`, `ec2:Encrypted`, `ec2:VolumeKmsKeyId` |
| `subnet` | `ec2:Subnet`, `ec2:Vpc` |
| `image` | `ec2:ImageId` |
| `network-interface` | `ec2:Vpc`, `ec2:Subnet` |

조건 키는 **해당 리소스 타입의 Statement에만** 넣어야 한다. `ec2:VolumeSize`를 `instance` 리소스 Statement에 넣으면 조건이 무시된다.

### AMI ARN의 계정 ID 자리

AMI는 소유자가 AWS 또는 다른 계정일 수 있다. ARN 형식에서 계정 ID 자리를 비워야 한다.

```
# 올바름
arn:aws:ec2:ap-northeast-2::image/ami-*

# 틀림 (계정 ID 넣으면 타사 AMI 차단됨)
arn:aws:ec2:ap-northeast-2:123456789012:image/ami-*
```

---

## ResourceTag vs RequestTag 구분법

이 둘을 혼동하면 정책이 의도대로 동작하지 않는다.

### ec2:ResourceTag

**이미 존재하는 리소스**의 태그를 기준으로 접근을 제어한다.

- 사용 시점: `StartInstances`, `StopInstances`, `TerminateInstances`, `DescribeInstances` 등
- 의미: "이 태그가 붙어 있는 리소스에 대해서만 허용/거부"

```json
"Condition": {
  "StringEquals": {
    "ec2:ResourceTag/Team": "${aws:PrincipalTag/Team}"
  }
}
```

### aws:RequestTag

**생성 요청 시 함께 전달되는 태그**를 기준으로 제어한다.

- 사용 시점: `RunInstances`, `CreateTags` (생성 시점)
- 의미: "이 태그를 포함해서 요청해야만 허용"

```json
"Condition": {
  "StringEquals": {
    "aws:RequestTag/Environment": ["dev", "staging", "production"]
  }
}
```

### 핵심 구분 기준

| 상황 | 사용할 조건 키 |
|---|---|
| 이미 있는 인스턴스를 Start/Stop/Terminate | `ec2:ResourceTag` |
| RunInstances 시 태그 강제 | `aws:RequestTag` |
| 태그 키 목록 제한 | `aws:TagKeys` |
| CreateTags 허용 범위 제한 | `ec2:CreateAction` |

### CreateTags는 반드시 별도 Statement

`RunInstances`와 `CreateTags`를 같은 Statement에 넣으면 안 된다. `RunInstances` 시점에 태그를 붙이려면 별도 Statement에 `ec2:CreateAction: "RunInstances"` 조건을 달아야 한다.

```json
{
  "Sid": "AllowCreateTagsOnLaunch",
  "Effect": "Allow",
  "Action": "ec2:CreateTags",
  "Resource": "arn:aws:ec2:AWS_REGION:ACCOUNT_ID:*/*",
  "Condition": {
    "StringEquals": {
      "ec2:CreateAction": "RunInstances"
    }
  }
}
```

---

## 기존 케이스 요약 (Case 01~06)

| 케이스 | 파일 | 핵심 메커니즘 |
|---|---|---|
| Case 01 | `case01-tag-based-start-stop.json` | `ec2:ResourceTag/Team` + `PrincipalTag` 동적 매칭 |
| Case 02 | `case02-run-instances-type-subnet.json` | `ec2:InstanceType` + `ec2:Subnet` + 다중 리소스 |
| Case 03 | `case03-deny-terminate-production.json` | Explicit Deny + `ec2:ResourceTag/Environment` |
| Case 04 | `case04-enforce-ebs-encryption.json` | `ec2:Encrypted: "false"` Deny (volume 리소스에만) |
| Case 05 | `case05-require-tags-on-create.json` | `aws:RequestTag` Null 체크 + `CreateTags` 분리 |
| Case 06 | `case06-launch-template-only.json` | `ec2:IsLaunchTemplateResource: "false"` Deny |

---

## Case 07 — AMI 제한 (특정 AMI만 허용)

### 시나리오

보안팀이 승인한 골든 AMI 목록 외의 이미지로는 인스턴스를 생성할 수 없다. 외부 마켓플레이스 AMI나 개인 AMI 사용을 차단한다.

### 정책 JSON

```json
{
  "Sid": "AllowRunInstancesApprovedAMIOnly",
  "Effect": "Allow",
  "Action": "ec2:RunInstances",
  "Resource": "arn:aws:ec2:AWS_REGION::image/ami-*",
  "Condition": {
    "StringEquals": {
      "ec2:ImageId": [
        "ami-APPROVED_AMI_ID_1",
        "ami-APPROVED_AMI_ID_2"
      ]
    }
  }
},
{
  "Sid": "DenyUnapprovedAMI",
  "Effect": "Deny",
  "Action": "ec2:RunInstances",
  "Resource": "arn:aws:ec2:AWS_REGION::image/ami-*",
  "Condition": {
    "StringNotEquals": {
      "ec2:ImageId": [
        "ami-APPROVED_AMI_ID_1",
        "ami-APPROVED_AMI_ID_2"
      ]
    }
  }
}
```

### 설명

`ec2:ImageId` 조건은 `image` 리소스 타입 Statement에 적용한다. Allow + Deny 이중 구조로 구성하면 허용 목록 외 AMI는 명시적으로 차단된다.

### 함정

- `image` ARN에 계정 ID를 넣으면 AWS 공식 AMI나 타 계정 공유 AMI가 차단된다. 반드시 `arn:aws:ec2:REGION::image/ami-*` 형식 (계정 ID 자리 비움) 사용.
- Allow만 있고 Deny가 없으면, 다른 정책에서 `ec2:*` Allow가 있을 때 우회 가능하다. Explicit Deny 추가 권장.
- AMI ID는 리전마다 다르다. 멀티 리전 환경이면 리전별로 AMI ID를 관리해야 한다.

### 검증 명령어

```bash
# 승인된 AMI로 생성 — 성공 기대
aws ec2 run-instances \
  --image-id ami-APPROVED_AMI_ID_1 \
  --instance-type t3.micro \
  --subnet-id subnet-XXXXXXXX \
  --profile "$PROFILE_NAME"

# 미승인 AMI로 생성 — AccessDenied 기대
aws ec2 run-instances \
  --image-id ami-UNAPPROVED_ID \
  --instance-type t3.micro \
  --subnet-id subnet-XXXXXXXX \
  --profile "$PROFILE_NAME"
```

---

## Case 08 — 볼륨 크기/타입 제한

### 시나리오

비용 통제를 위해 EBS 볼륨은 `gp3` 또는 `gp2` 타입만 허용하고, 크기는 100GB를 초과할 수 없다. `io2` 같은 고성능 볼륨이나 과도한 크기의 볼륨 생성을 차단한다.

### 정책 JSON

```json
{
  "Sid": "AllowRunInstancesVolumeWithConstraints",
  "Effect": "Allow",
  "Action": "ec2:RunInstances",
  "Resource": "arn:aws:ec2:AWS_REGION:ACCOUNT_ID:volume/*",
  "Condition": {
    "StringEquals": {
      "ec2:VolumeType": ["gp3", "gp2"]
    },
    "NumericLessThanEquals": {
      "ec2:VolumeSize": "100"
    }
  }
},
{
  "Sid": "DenyOversizedVolume",
  "Effect": "Deny",
  "Action": "ec2:RunInstances",
  "Resource": "arn:aws:ec2:AWS_REGION:ACCOUNT_ID:volume/*",
  "Condition": {
    "NumericGreaterThan": {
      "ec2:VolumeSize": "100"
    }
  }
}
```

### 설명

`ec2:VolumeType`과 `ec2:VolumeSize`는 `volume` 리소스 타입에만 적용된다. `instance` 리소스 Statement에 넣으면 조건이 평가되지 않는다.

### 함정

- `ec2:VolumeSize`는 숫자 비교 연산자(`NumericLessThanEquals`, `NumericGreaterThan`)를 사용한다. `StringEquals`로 비교하면 동작하지 않는다.
- `RunInstances`에서 볼륨 크기를 지정하지 않으면 AMI 기본값이 사용된다. 기본값이 100GB를 초과하는 AMI라면 생성이 차단된다.
- `ec2:VolumeType` 조건은 `RunInstances` 시점에만 적용된다. 이후 `ModifyVolume`으로 타입 변경은 별도 정책으로 제어해야 한다.

### 검증 명령어

```bash
# gp3, 50GB — 성공 기대
aws ec2 run-instances \
  --image-id ami-XXXXXXXX \
  --instance-type t3.micro \
  --block-device-mappings '[{"DeviceName":"/dev/xvda","Ebs":{"VolumeSize":50,"VolumeType":"gp3"}}]' \
  --profile "$PROFILE_NAME"

# io2, 200GB — AccessDenied 기대
aws ec2 run-instances \
  --image-id ami-XXXXXXXX \
  --instance-type t3.micro \
  --block-device-mappings '[{"DeviceName":"/dev/xvda","Ebs":{"VolumeSize":200,"VolumeType":"io2"}}]' \
  --profile "$PROFILE_NAME"
```

---

## Case 09 — 태그 변경 차단 (보호 태그 키)

### 시나리오

`Environment`, `CostCenter`, `Owner` 태그는 인프라 관리팀만 수정할 수 있다. 일반 사용자가 이 태그를 추가하거나 삭제하면 비용 추적과 환경 분리가 깨진다.

### 정책 JSON

```json
{
  "Sid": "DenyModifyProtectedTagKeys",
  "Effect": "Deny",
  "Action": [
    "ec2:CreateTags",
    "ec2:DeleteTags"
  ],
  "Resource": "arn:aws:ec2:AWS_REGION:ACCOUNT_ID:*/*",
  "Condition": {
    "ForAnyValue:StringEquals": {
      "aws:TagKeys": [
        "Environment",
        "CostCenter",
        "Owner"
      ]
    }
  }
}
```

### 설명

`ForAnyValue:StringEquals`는 요청에 포함된 태그 키 중 하나라도 보호 목록에 있으면 Deny를 발동시킨다. `ForAllValues`를 쓰면 모든 키가 목록에 있을 때만 Deny되므로 의도와 다르게 동작한다.

### 함정

- `ForAllValues:StringEquals`와 `ForAnyValue:StringEquals`를 혼동하면 안 된다. 보호 태그 차단에는 `ForAnyValue`가 맞다.
- `aws:TagKeys`는 요청에 포함된 태그 키 목록이다. `ec2:ResourceTag`와 다르다.
- `CreateTags`와 `DeleteTags` 둘 다 차단해야 한다. `DeleteTags`만 빠뜨리면 태그 삭제로 우회 가능하다.
- 이 Deny는 `RunInstances` 시점의 태그 생성에도 영향을 준다. `RunInstances`와 함께 보호 태그를 붙여야 한다면 별도 예외 처리가 필요하다.

### 검증 명령어

```bash
# 일반 태그 추가 — 성공 기대
aws ec2 create-tags \
  --resources i-XXXXXXXX \
  --tags Key=Name,Value=MyInstance \
  --profile "$PROFILE_NAME"

# 보호 태그 수정 시도 — AccessDenied 기대
aws ec2 create-tags \
  --resources i-XXXXXXXX \
  --tags Key=Environment,Value=hacked \
  --profile "$PROFILE_NAME"

# 보호 태그 삭제 시도 — AccessDenied 기대
aws ec2 delete-tags \
  --resources i-XXXXXXXX \
  --tags Key=CostCenter \
  --profile "$PROFILE_NAME"
```

---

## Case 10 — 특정 VPC/서브넷에서만 RunInstances

### 시나리오

개발팀은 승인된 프라이빗 서브넷에서만 인스턴스를 생성할 수 있다. 퍼블릭 서브넷이나 다른 VPC에 인스턴스를 올리면 보안 정책 위반이다.

### 정책 JSON

```json
{
  "Sid": "AllowRunInstancesApprovedSubnetsOnly",
  "Effect": "Allow",
  "Action": "ec2:RunInstances",
  "Resource": [
    "arn:aws:ec2:AWS_REGION:ACCOUNT_ID:subnet/SUBNET_ID_PRIVATE_1",
    "arn:aws:ec2:AWS_REGION:ACCOUNT_ID:subnet/SUBNET_ID_PRIVATE_2"
  ]
},
{
  "Sid": "DenyRunInstancesOutsideApprovedVpc",
  "Effect": "Deny",
  "Action": "ec2:RunInstances",
  "Resource": "arn:aws:ec2:AWS_REGION:ACCOUNT_ID:instance/*",
  "Condition": {
    "StringNotEquals": {
      "ec2:Vpc": "arn:aws:ec2:AWS_REGION:ACCOUNT_ID:vpc/VPC_ID"
    }
  }
}
```

### 설명

두 가지 방어선을 조합한다. 첫째, 허용된 서브넷 ARN만 Resource에 명시해서 다른 서브넷 사용을 차단한다. 둘째, `ec2:Vpc` 조건으로 VPC 수준에서도 이중 차단한다.

### 함정

- `ec2:Subnet` 조건 키는 `network-interface` 리소스에도 적용된다. 서브넷 제한을 `subnet` 리소스 ARN으로만 하면 `network-interface`를 통한 우회 가능성이 있다.
- `ec2:Vpc` 조건은 `instance` 리소스 Statement에 적용한다.
- 서브넷 ARN을 Resource에 명시하는 방식은 서브넷이 추가될 때마다 정책을 업데이트해야 한다. 유지보수 부담이 있다면 `ec2:Vpc` 조건만으로 VPC 수준 제한을 고려할 수 있다.

### 검증 명령어

```bash
# 승인된 서브넷 — 성공 기대
aws ec2 run-instances \
  --image-id ami-XXXXXXXX \
  --instance-type t3.micro \
  --subnet-id SUBNET_ID_PRIVATE_1 \
  --profile "$PROFILE_NAME"

# 미승인 서브넷 — AccessDenied 기대
aws ec2 run-instances \
  --image-id ami-XXXXXXXX \
  --instance-type t3.micro \
  --subnet-id subnet-PUBLIC_SUBNET_ID \
  --profile "$PROFILE_NAME"
```

---

## Case 11 — Spot 인스턴스 차단

### 시나리오

예산 예측 가능성을 위해 On-Demand 인스턴스만 허용한다. Spot 인스턴스는 갑작스러운 중단이 발생할 수 있어 프로덕션 워크로드에 부적합하다.

### 정책 JSON

```json
{
  "Sid": "AllowRunInstancesOnDemandOnly",
  "Effect": "Allow",
  "Action": "ec2:RunInstances",
  "Resource": "arn:aws:ec2:AWS_REGION:ACCOUNT_ID:instance/*",
  "Condition": {
    "StringEquals": {
      "ec2:InstanceMarketType": "on-demand"
    }
  }
},
{
  "Sid": "DenySpotInstances",
  "Effect": "Deny",
  "Action": "ec2:RunInstances",
  "Resource": "arn:aws:ec2:AWS_REGION:ACCOUNT_ID:instance/*",
  "Condition": {
    "StringEquals": {
      "ec2:InstanceMarketType": "spot"
    }
  }
}
```

### 설명

`ec2:InstanceMarketType`은 `instance` 리소스 타입에 적용되는 조건 키다. 값은 `"on-demand"` 또는 `"spot"`이다.

### 함정

- `ec2:InstanceMarketType` 조건 키가 없으면 (일반 `RunInstances` 호출) 기본값은 `on-demand`다. 조건이 없는 경우 Allow가 적용되도록 설계해야 한다.
- Spot Fleet(`ec2:RequestSpotFleet`)이나 Spot 요청(`ec2:RequestSpotInstances`)은 별도 Action이다. `RunInstances` 차단만으로는 이 경로를 막지 못한다.
- Auto Scaling Group에서 Spot을 사용하는 경우 `ec2:RunInstances` 외에 `autoscaling:*` 권한도 검토해야 한다.

### 검증 명령어

```bash
# On-Demand — 성공 기대
aws ec2 run-instances \
  --image-id ami-XXXXXXXX \
  --instance-type t3.micro \
  --subnet-id subnet-XXXXXXXX \
  --profile "$PROFILE_NAME"

# Spot 요청 — AccessDenied 기대
aws ec2 run-instances \
  --image-id ami-XXXXXXXX \
  --instance-type t3.micro \
  --instance-market-options '{"MarketType":"spot"}' \
  --subnet-id subnet-XXXXXXXX \
  --profile "$PROFILE_NAME"
```

---

## Case 12 — 보안 그룹 인바운드 규칙 제한

### 시나리오

`0.0.0.0/0` (전체 인터넷)에서 인바운드를 허용하는 보안 그룹 규칙 추가를 차단한다. 특히 프로덕션 환경 보안 그룹에 퍼블릭 인바운드 규칙이 생기면 즉각적인 보안 위협이 된다.

### 정책 JSON

```json
{
  "Sid": "DenyWildcardCidrOnAllSecurityGroups",
  "Effect": "Deny",
  "Action": [
    "ec2:AuthorizeSecurityGroupIngress",
    "ec2:AuthorizeSecurityGroupEgress"
  ],
  "Resource": "arn:aws:ec2:AWS_REGION:ACCOUNT_ID:security-group/*",
  "Condition": {
    "IpAddress": {
      "aws:SourceIp": [
        "0.0.0.0/0",
        "::/0"
      ]
    }
  }
},
{
  "Sid": "DenyPublicIngressOnProductionSG",
  "Effect": "Deny",
  "Action": "ec2:AuthorizeSecurityGroupIngress",
  "Resource": "arn:aws:ec2:AWS_REGION:ACCOUNT_ID:security-group/*",
  "Condition": {
    "IpAddress": {
      "aws:SourceIp": "0.0.0.0/0"
    },
    "StringEquals": {
      "ec2:ResourceTag/Environment": "production"
    }
  }
}
```

### 설명

`aws:SourceIp` 조건으로 요청 출처 IP를 제한하는 것이 아니라, 보안 그룹 규칙에 추가하려는 CIDR 범위를 제한하는 것이다. IPv4(`0.0.0.0/0`)와 IPv6(`::/0`) 둘 다 차단해야 한다.

### 함정

- `aws:SourceIp`는 여기서 "요청자의 IP"가 아니라 보안 그룹 규칙에 설정하려는 CIDR 값을 의미하지 않는다. 실제로 `AuthorizeSecurityGroupIngress`의 CIDR 제한은 `ec2:AuthorizedService` 같은 전용 조건 키가 없어서 완전한 CIDR 제한은 어렵다. 이 케이스는 요청자 IP 기반 제어로 이해하는 것이 정확하다.
- 보안 그룹 규칙의 CIDR 범위를 정책으로 완전히 제어하려면 AWS Config 규칙(`restricted-ssh`, `vpc-sg-open-only-to-authorized-ports`)과 병행하는 것이 현실적이다.
- `ec2:ResourceTag` 조건으로 특정 환경의 보안 그룹만 추가 보호할 수 있다.

### 검증 명령어

```bash
# 특정 CIDR 인바운드 추가 — 성공 기대
aws ec2 authorize-security-group-ingress \
  --group-id sg-XXXXXXXX \
  --protocol tcp \
  --port 443 \
  --cidr 10.0.0.0/8 \
  --profile "$PROFILE_NAME"

# 0.0.0.0/0 인바운드 추가 시도 — AccessDenied 기대
aws ec2 authorize-security-group-ingress \
  --group-id sg-XXXXXXXX \
  --protocol tcp \
  --port 22 \
  --cidr 0.0.0.0/0 \
  --profile "$PROFILE_NAME"
```

---

## 감점 방지 포인트 총정리

- `RunInstances`에 `instance` ARN만 넣으면 `volume`/`network-interface` 생성 단계에서 실패한다. 6개 리소스 타입 모두 커버해야 한다.
- `ec2:ResourceTag`는 이미 존재하는 리소스에만 동작한다. 생성 시점 태그 강제는 `aws:RequestTag`를 써야 한다.
- `CreateTags`를 `RunInstances`와 같은 Statement에 넣으면 안 된다. `ec2:CreateAction` 조건으로 분리 필수.
- `ec2:Encrypted`, `ec2:VolumeSize`, `ec2:VolumeType` 조건은 `volume` 리소스 Statement에만 넣어야 한다.
- AMI ARN은 `arn:aws:ec2:REGION::image/ami-*` 형식으로 계정 ID 자리를 비워야 한다.
- `ForAnyValue`와 `ForAllValues` 혼동 주의. 보호 태그 차단에는 `ForAnyValue:StringEquals`가 맞다.
- Spot 차단 시 `ec2:RequestSpotInstances`와 `ec2:RequestSpotFleet`도 별도로 차단해야 완전하다.

---

## 공통 환경 변수

```bash
export AWS_REGION="ap-northeast-2"
export ACCOUNT_ID="123456789012"
export USER_NAME="mod3-ec2-user"
export PROFILE_NAME="mod3-ec2-user"
```

## 정책 연결 및 검증 루틴

```bash
# 정책 생성
aws iam create-policy \
  --policy-name "EC2FineGrainedPolicy" \
  --policy-document file://policies/case07-ami-restriction.json

# 사용자에 연결
aws iam attach-user-policy \
  --user-name "$USER_NAME" \
  --policy-arn "arn:aws:iam::$ACCOUNT_ID:policy/EC2FineGrainedPolicy"

# 신분 확인
aws sts get-caller-identity --profile "$PROFILE_NAME"

# 시뮬레이터로 1차 검증
aws iam simulate-principal-policy \
  --policy-source-arn "arn:aws:iam::$ACCOUNT_ID:user/$USER_NAME" \
  --action-names ec2:RunInstances \
  --resource-arns "arn:aws:ec2:$AWS_REGION::image/ami-APPROVED_AMI_ID_1"
```
