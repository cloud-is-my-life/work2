# S3 Fine-grained IAM 실전 가이드

> AWS Skills Competition 2026 대비. 이 문서 하나로 S3 IAM 문제는 전부 커버된다.

---

## 빈출 패턴 요약

시험에서 반복해서 나오는 패턴 7가지. 이것만 외워도 절반은 먹고 들어간다.

| 순위 | 패턴 | 핵심 키워드 |
|------|------|------------|
| 1 | Prefix 읽기 + 삭제 Deny | `s3:prefix`, `DeleteObject` Deny |
| 2 | ABAC (PrincipalTag 기반 분기) | `${aws:PrincipalTag/Team}`, Null Deny |
| 3 | 사용자별 홈 디렉토리 | `${aws:username}`, NotResource |
| 4 | MFA 없으면 삭제 차단 | `aws:MultiFactorAuthPresent`, `BoolIfExists` |
| 5 | SSE-KMS 암호화 강제 | `s3:x-amz-server-side-encryption`, StringNotEquals Deny |
| 6 | IP + TLS 복합 제한 | `aws:SourceIp`, `aws:SecureTransport` |
| 7 | 크로스 계정 Bucket Policy | Principal + 양쪽 Allow 필수 |

---

## ARN 실수 방지

S3 IAM에서 가장 많이 틀리는 부분이다. 버킷 ARN과 오브젝트 ARN을 헷갈리면 즉시 감점.

### 버킷 ARN vs 오브젝트 ARN

```
버킷 ARN:   arn:aws:s3:::BUCKET_NAME
오브젝트 ARN: arn:aws:s3:::BUCKET_NAME/*
```

### 어떤 Action에 어떤 ARN을 써야 하나

| Action | Resource ARN | 틀리면? |
|--------|-------------|---------|
| `s3:ListBucket` | `arn:aws:s3:::BUCKET` (버킷) | `InvalidBucketName` 오류 |
| `s3:GetObject` | `arn:aws:s3:::BUCKET/*` (오브젝트) | 항상 AccessDenied |
| `s3:PutObject` | `arn:aws:s3:::BUCKET/*` (오브젝트) | 항상 AccessDenied |
| `s3:DeleteObject` | `arn:aws:s3:::BUCKET/*` (오브젝트) | 항상 AccessDenied |
| `s3:GetBucketPolicy` | `arn:aws:s3:::BUCKET` (버킷) | 항상 AccessDenied |

### 자주 나오는 실수 패턴

```json
// 틀린 예 — ListBucket에 오브젝트 ARN 사용
{
  "Action": "s3:ListBucket",
  "Resource": "arn:aws:s3:::my-bucket/*"  // 오답!
}

// 맞는 예
{
  "Action": "s3:ListBucket",
  "Resource": "arn:aws:s3:::my-bucket"    // 정답
}
```

`s3:prefix` 조건은 `ListBucket`에만 동작한다. `GetObject`에 `s3:prefix` 조건을 걸어봤자 아무 효과 없다. `GetObject` 범위 제한은 Resource ARN 패턴(`BUCKET/reports/*`)으로 해야 한다.

---

## Condition 연산자 빠른 참조

### 문자열 비교

| 연산자 | 의미 | 사용 예 |
|--------|------|---------|
| `StringEquals` | 정확히 일치 | 특정 팀 태그 허용 |
| `StringNotEquals` | 일치하지 않으면 | 특정 암호화 방식 아니면 Deny |
| `StringLike` | 와일드카드(`*`, `?`) 포함 | prefix 패턴 매칭 |
| `StringNotLike` | 와일드카드 포함 불일치 | 특정 패턴 외 차단 |
| `StringEqualsIfExists` | 키가 있을 때만 비교 | 선택적 헤더 검사 |

### 숫자 비교

| 연산자 | 의미 |
|--------|------|
| `NumericLessThanEquals` | 이하 |
| `NumericGreaterThan` | 초과 |

### 불리언

| 연산자 | 의미 | 주의 |
|--------|------|------|
| `Bool` | true/false 정확히 비교 | 키 없으면 조건 미적용 |
| `BoolIfExists` | 키가 있을 때만 비교 | MFA 조건에 권장 |

### Null 체크

```json
// 키가 없으면(헤더 누락) Deny
{ "Null": { "s3:x-amz-server-side-encryption": "true" } }

// 키가 있으면(태그 설정됨) 통과
{ "Null": { "aws:PrincipalTag/Team": "false" } }
```

### ForAllValues vs ForAnyValue

- `ForAllValues:StringEquals` — 요청의 모든 값이 허용 목록 안에 있어야 함
- `ForAnyValue:StringEquals` — 요청 값 중 하나라도 허용 목록에 있으면 됨

---

## 기존 케이스 01~07 요약

### Case 01 — Prefix 읽기 전용 + 삭제 Deny + TLS 강제

`reports/` prefix만 읽기 허용. 삭제는 Explicit Deny. HTTP 차단.

핵심: `ListBucket`은 버킷 ARN + `s3:prefix` 조건, `GetObject`는 오브젝트 ARN.

### Case 02 — PrincipalTag 기반 Prefix 자동 분기 (ABAC)

`${aws:PrincipalTag/Team}` 변수로 팀별 prefix 자동 분기. 태그 없는 사용자는 Null Deny로 전면 차단.

핵심: 태그 미설정 시 변수가 빈 문자열이 되어 `home//` prefix 접근 가능해짐. Null Deny 필수.

### Case 03 — SSE-KMS 암호화 강제

`StringNotEquals` + Deny 패턴으로 지정 KMS 키 외 업로드 차단. 암호화 헤더 누락도 Null 조건으로 차단.

### Case 04 — Public ACL 차단

`s3:x-amz-acl` 조건으로 `public-read`, `public-read-write` 차단. S3 Block Public Access와 별개의 IAM 레벨 이중 방어.

### Case 05 — IP/VPC Endpoint 기반 접근 제한

`NotIpAddress` + `StringNotEquals(SourceVpce)` 조합으로 허용 IP 또는 VPC Endpoint 외 전면 차단.

### Case 06 — 오브젝트 태그 기반 접근 제어

`s3:ExistingObjectTag/Classification` 조건으로 태그 값에 따라 읽기 허용/차단. 업로드 시 태그 강제는 `s3:RequestObjectTag`.

### Case 07 — 크로스 계정 Bucket Policy

외부 계정에 prefix 읽기 권한 부여. 크로스 계정은 Bucket Policy + 상대 계정 IAM Policy 양쪽 모두 Allow 필요.

---

## 신규 케이스 08~13 상세 가이드

---

### Case 08 — 사용자별 홈 디렉토리 (aws:username 기반 prefix 분리)

**시나리오**: IAM 사용자 100명이 같은 버킷을 쓴다. 각자 자기 디렉토리(`home/alice/`, `home/bob/`)만 접근 가능하고, 다른 사람 디렉토리는 볼 수 없어야 한다.

**정책 JSON**:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyIfUsernameTagMissing",
      "Effect": "Deny",
      "Action": "s3:*",
      "Resource": "*",
      "Condition": {
        "Null": {
          "aws:username": "true"
        }
      }
    },
    {
      "Sid": "AllowListOwnHomePrefix",
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::DATA_BUCKET",
      "Condition": {
        "StringLike": {
          "s3:prefix": [
            "home/${aws:username}/",
            "home/${aws:username}/*"
          ]
        }
      }
    },
    {
      "Sid": "AllowReadWriteOwnHomeObjects",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::DATA_BUCKET/home/${aws:username}/*"
    },
    {
      "Sid": "DenyAccessOtherUsersHome",
      "Effect": "Deny",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "NotResource": "arn:aws:s3:::DATA_BUCKET/home/${aws:username}/*"
    }
  ]
}
```

**왜 이렇게 써야 하나**: `${aws:username}`은 IAM 정책 변수다. 정책을 평가할 때 실제 호출자의 IAM 사용자 이름으로 자동 치환된다. 사용자 100명에게 같은 정책 하나만 붙여도 각자 자기 prefix만 접근하게 된다. 정책을 100개 만들 필요가 없다.

**이거 빠뜨리면?**:
- `DenyAccessOtherUsersHome` Statement 없으면: `home/alice/`에 Allow가 있어도 `home/bob/`에 대한 명시적 Deny가 없으니 다른 Allow 정책이 있을 경우 접근 가능해진다.
- `s3:prefix` 조건에 `home/${aws:username}/` (슬래시 포함)을 빠뜨리면: 디렉토리 자체 리스팅이 안 된다.
- IAM Role로 접근하면 `aws:username`이 비어 있다. Role 기반 접근에는 `aws:PrincipalTag` 방식(Case 02)을 써야 한다.

**CloudShell 검증**:

```bash
export DATA_BUCKET="YOUR_BUCKET"
export PROFILE_ALICE="alice-profile"
export PROFILE_BOB="bob-profile"

# alice 자기 디렉토리 — 성공 기대
aws s3 ls "s3://$DATA_BUCKET/home/alice/" --profile "$PROFILE_ALICE"
aws s3 cp test.txt "s3://$DATA_BUCKET/home/alice/test.txt" --profile "$PROFILE_ALICE"

# alice가 bob 디렉토리 접근 — AccessDenied 기대
aws s3 ls "s3://$DATA_BUCKET/home/bob/" --profile "$PROFILE_ALICE"
aws s3 cp "s3://$DATA_BUCKET/home/bob/secret.txt" - --profile "$PROFILE_ALICE"
```

---

### Case 09 — MFA 없으면 삭제 차단 (aws:MultiFactorAuthPresent)

**시나리오**: 일반 읽기는 MFA 없이 가능하지만, 오브젝트 삭제는 반드시 MFA 인증을 거쳐야 한다. 실수나 탈취된 자격증명으로 인한 대량 삭제를 방지한다.

**정책 JSON**:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowListAndRead",
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket",
        "s3:GetObject"
      ],
      "Resource": [
        "arn:aws:s3:::DATA_BUCKET",
        "arn:aws:s3:::DATA_BUCKET/*"
      ]
    },
    {
      "Sid": "DenyDeleteWithoutMFA",
      "Effect": "Deny",
      "Action": [
        "s3:DeleteObject",
        "s3:DeleteObjectVersion"
      ],
      "Resource": "arn:aws:s3:::DATA_BUCKET/*",
      "Condition": {
        "BoolIfExists": {
          "aws:MultiFactorAuthPresent": "false"
        }
      }
    },
    {
      "Sid": "AllowDeleteWithMFA",
      "Effect": "Allow",
      "Action": [
        "s3:DeleteObject",
        "s3:DeleteObjectVersion"
      ],
      "Resource": "arn:aws:s3:::DATA_BUCKET/*",
      "Condition": {
        "Bool": {
          "aws:MultiFactorAuthPresent": "true"
        }
      }
    }
  ]
}
```

**왜 이렇게 써야 하나**: `BoolIfExists`를 쓰는 이유가 있다. `Bool`만 쓰면 `aws:MultiFactorAuthPresent` 키 자체가 없는 경우(예: 액세스 키 직접 사용)에 조건이 적용되지 않아 Deny가 뚫린다. `BoolIfExists`는 키가 없을 때도 `false`로 처리해서 Deny가 확실히 걸린다.

**이거 빠뜨리면?**:
- `BoolIfExists` 대신 `Bool` 쓰면: 장기 자격증명(액세스 키)으로 호출 시 `aws:MultiFactorAuthPresent` 키 자체가 컨텍스트에 없어서 Deny 조건이 무시된다. MFA 없이 삭제 가능해진다.
- `AllowDeleteWithMFA` Statement 없으면: MFA 인증해도 삭제 불가. Deny가 Allow보다 우선이므로 Allow도 있어야 한다.
- `DeleteObjectVersion` 빠뜨리면: 버전 관리 활성화된 버킷에서 특정 버전 삭제가 MFA 없이 가능해진다.

**CloudShell 검증**:

```bash
export DATA_BUCKET="YOUR_BUCKET"
export PROFILE_NAME="mod3-mfa-user"

# MFA 없는 일반 자격증명으로 삭제 시도 — AccessDenied 기대
aws s3 rm "s3://$DATA_BUCKET/test.txt" --profile "$PROFILE_NAME"

# MFA 세션 토큰 발급 후 삭제 시도 — 성공 기대
MFA_ARN="arn:aws:iam::ACCOUNT_ID:mfa/YOUR_MFA_DEVICE"
MFA_TOKEN="123456"
CREDS=$(aws sts get-session-token   --serial-number "$MFA_ARN"   --token-code "$MFA_TOKEN"   --profile "$PROFILE_NAME")

export AWS_ACCESS_KEY_ID=$(echo $CREDS | jq -r '.Credentials.AccessKeyId')
export AWS_SECRET_ACCESS_KEY=$(echo $CREDS | jq -r '.Credentials.SecretAccessKey')
export AWS_SESSION_TOKEN=$(echo $CREDS | jq -r '.Credentials.SessionToken')

aws s3 rm "s3://$DATA_BUCKET/test.txt"
```

---

### Case 10 — 특정 스토리지 클래스 강제 (s3:x-amz-storage-class)

**시나리오**: 비용 절감 정책으로 모든 업로드는 반드시 `STANDARD_IA` 또는 `ONEZONE_IA` 클래스만 허용한다. `STANDARD` 클래스로 올리면 차단한다.

**정책 JSON**:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowListAndRead",
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket",
        "s3:GetObject"
      ],
      "Resource": [
        "arn:aws:s3:::DATA_BUCKET",
        "arn:aws:s3:::DATA_BUCKET/*"
      ]
    },
    {
      "Sid": "DenyPutObjectWrongStorageClass",
      "Effect": "Deny",
      "Action": "s3:PutObject",
      "Resource": "arn:aws:s3:::DATA_BUCKET/*",
      "Condition": {
        "StringNotEqualsIfExists": {
          "s3:x-amz-storage-class": [
            "STANDARD_IA",
            "ONEZONE_IA"
          ]
        }
      }
    },
    {
      "Sid": "DenyPutObjectMissingStorageClassHeader",
      "Effect": "Deny",
      "Action": "s3:PutObject",
      "Resource": "arn:aws:s3:::DATA_BUCKET/*",
      "Condition": {
        "Null": {
          "s3:x-amz-storage-class": "true"
        }
      }
    }
  ]
}
```

**왜 이렇게 써야 하나**: `StringNotEqualsIfExists`를 쓰는 이유는 헤더가 있을 때만 비교하기 위해서다. 그런데 헤더 자체가 없는 경우(기본값 STANDARD로 업로드)는 `IfExists` 조건이 통과시켜버린다. 그래서 `Null: true` Deny를 별도로 추가해야 헤더 누락도 차단된다.

**이거 빠뜨리면?**:
- `Null` Deny 없으면: `--storage-class` 옵션 없이 업로드하면 헤더가 없어서 `StringNotEqualsIfExists` 조건이 무시되고 STANDARD로 업로드된다.
- `StringNotEquals` 대신 `StringEquals` + Allow 패턴 쓰면: 헤더 없는 경우를 Allow 조건이 걸러내지 못해 의도치 않은 업로드 허용 가능.

**CloudShell 검증**:

```bash
export DATA_BUCKET="YOUR_BUCKET"
export PROFILE_NAME="mod3-storage-user"

# STANDARD_IA로 업로드 — 성공 기대
aws s3 cp test.txt "s3://$DATA_BUCKET/test-ia.txt"   --storage-class STANDARD_IA   --profile "$PROFILE_NAME"

# STANDARD로 업로드 — AccessDenied 기대
aws s3 cp test.txt "s3://$DATA_BUCKET/test-std.txt"   --storage-class STANDARD   --profile "$PROFILE_NAME"

# 스토리지 클래스 미지정 업로드 — AccessDenied 기대
aws s3 cp test.txt "s3://$DATA_BUCKET/test-default.txt"   --profile "$PROFILE_NAME"
```

---

### Case 11 — 버전 관리: 최신만 읽기 vs 관리자 전체 버전 접근

**시나리오**: 일반 사용자는 최신 버전만 읽을 수 있다. 버전 관리자 역할만 이전 버전 조회, 삭제, 복원이 가능하다.

**정책 JSON**:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowListBucket",
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::DATA_BUCKET"
    },
    {
      "Sid": "AllowReadLatestVersionOnly",
      "Effect": "Allow",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::DATA_BUCKET/*"
    },
    {
      "Sid": "DenyGetSpecificVersion",
      "Effect": "Deny",
      "Action": "s3:GetObjectVersion",
      "Resource": "arn:aws:s3:::DATA_BUCKET/*",
      "Condition": {
        "StringNotEquals": {
          "aws:PrincipalArn": [
            "arn:aws:iam::ACCOUNT_ID:role/S3VersionAdminRole",
            "arn:aws:iam::ACCOUNT_ID:user/s3-version-admin"
          ]
        }
      }
    },
    {
      "Sid": "AllowAdminFullVersionAccess",
      "Effect": "Allow",
      "Action": [
        "s3:GetObjectVersion",
        "s3:DeleteObjectVersion",
        "s3:ListBucketVersions",
        "s3:RestoreObject"
      ],
      "Resource": [
        "arn:aws:s3:::DATA_BUCKET",
        "arn:aws:s3:::DATA_BUCKET/*"
      ],
      "Condition": {
        "StringEquals": {
          "aws:PrincipalArn": [
            "arn:aws:iam::ACCOUNT_ID:role/S3VersionAdminRole",
            "arn:aws:iam::ACCOUNT_ID:user/s3-version-admin"
          ]
        }
      }
    }
  ]
}
```

**왜 이렇게 써야 하나**: `s3:GetObject`와 `s3:GetObjectVersion`은 별개의 Action이다. `GetObject`는 항상 최신 버전을 반환하고, `GetObjectVersion`은 `?versionId=` 파라미터로 특정 버전을 지정해서 가져온다. 일반 사용자에게 `GetObjectVersion`을 Deny하면 이전 버전 접근을 차단할 수 있다.

**이거 빠뜨리면?**:
- `ListBucketVersions` 권한을 관리자에게만 주지 않으면: 일반 사용자가 버전 목록을 조회해서 versionId를 알아낼 수 있다.
- `DeleteObjectVersion` 빠뜨리면: 관리자가 특정 버전을 영구 삭제할 수 없다. 버전 관리 버킷에서 `DeleteObject`는 삭제 마커만 추가하고 실제 삭제는 `DeleteObjectVersion`이다.

**CloudShell 검증**:

```bash
export DATA_BUCKET="YOUR_BUCKET"
export PROFILE_USER="mod3-regular-user"
export PROFILE_ADMIN="mod3-version-admin"

# 최신 버전 읽기 — 일반 사용자 성공 기대
aws s3 cp "s3://$DATA_BUCKET/file.txt" - --profile "$PROFILE_USER"

# 특정 버전 읽기 — 일반 사용자 AccessDenied 기대
VERSION_ID="YOUR_VERSION_ID"
aws s3api get-object   --bucket "$DATA_BUCKET"   --key "file.txt"   --version-id "$VERSION_ID"   /tmp/out.txt   --profile "$PROFILE_USER"

# 버전 목록 조회 — 관리자 성공 기대
aws s3api list-object-versions   --bucket "$DATA_BUCKET"   --profile "$PROFILE_ADMIN"
```

---

### Case 12 — 파일 크기 제한 업로드 (s3:content-length-range)

**시나리오**: 사용자 업로드 버킷에 10MB 초과 파일은 올릴 수 없다. 대용량 파일 업로드로 인한 비용 폭증을 방지한다.

**정책 JSON**:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowListBucket",
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::DATA_BUCKET",
      "Condition": {
        "StringLike": {
          "s3:prefix": ["uploads/*"]
        }
      }
    },
    {
      "Sid": "AllowGetObject",
      "Effect": "Allow",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::DATA_BUCKET/uploads/*"
    },
    {
      "Sid": "AllowPutObjectWithSizeLimit",
      "Effect": "Allow",
      "Action": "s3:PutObject",
      "Resource": "arn:aws:s3:::DATA_BUCKET/uploads/*",
      "Condition": {
        "NumericLessThanEquals": {
          "s3:content-length-range": 10485760
        }
      }
    },
    {
      "Sid": "DenyPutObjectExceedsSizeLimit",
      "Effect": "Deny",
      "Action": "s3:PutObject",
      "Resource": "arn:aws:s3:::DATA_BUCKET/uploads/*",
      "Condition": {
        "NumericGreaterThan": {
          "s3:content-length-range": 10485760
        }
      }
    }
  ]
}
```

**왜 이렇게 써야 하나**: `s3:content-length-range`는 요청의 `Content-Length` 헤더 값을 기준으로 평가한다. 10485760은 10MB(10 * 1024 * 1024)다. Allow에 `NumericLessThanEquals`로 허용 범위를 걸고, Deny에 `NumericGreaterThan`으로 초과를 명시적으로 차단하는 이중 구조가 안전하다.

**이거 빠뜨리면?**:
- Deny Statement 없이 Allow만 쓰면: 다른 Allow 정책이 있을 경우 크기 제한이 우회될 수 있다. Explicit Deny가 있어야 확실하다.
- Multipart Upload 사용 시: `s3:content-length-range`는 각 파트의 크기를 기준으로 평가한다. 전체 파일 크기가 아니라 파트 크기 기준이므로 Multipart로 쪼개면 우회 가능하다. `s3:PutObject` 외에 `s3:CreateMultipartUpload`도 함께 제어해야 한다.

**CloudShell 검증**:

```bash
export DATA_BUCKET="YOUR_BUCKET"
export PROFILE_NAME="mod3-upload-user"

# 5MB 파일 생성 후 업로드 — 성공 기대
dd if=/dev/urandom of=/tmp/small.bin bs=1M count=5
aws s3 cp /tmp/small.bin "s3://$DATA_BUCKET/uploads/small.bin"   --profile "$PROFILE_NAME"

# 15MB 파일 생성 후 업로드 — AccessDenied 기대
dd if=/dev/urandom of=/tmp/large.bin bs=1M count=15
aws s3 cp /tmp/large.bin "s3://$DATA_BUCKET/uploads/large.bin"   --profile "$PROFILE_NAME"
```

---

### Case 13 — 복합 조건: IP + Prefix + TLS 동시 적용

**시나리오**: 가장 엄격한 보안 요구사항. 허용된 IP 대역 또는 VPC Endpoint에서만, `secure/` prefix에만, HTTPS로만 접근 가능하다. 세 조건 중 하나라도 어기면 차단.

**정책 JSON**:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowListAllowedPrefixFromAllowedIP",
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::DATA_BUCKET",
      "Condition": {
        "StringLike": {
          "s3:prefix": ["secure/*"]
        },
        "IpAddress": {
          "aws:SourceIp": ["ALLOWED_CIDR_1", "ALLOWED_CIDR_2"]
        },
        "Bool": {
          "aws:SecureTransport": "true"
        }
      }
    },
    {
      "Sid": "AllowGetObjectAllowedPrefixFromAllowedIP",
      "Effect": "Allow",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::DATA_BUCKET/secure/*",
      "Condition": {
        "IpAddress": {
          "aws:SourceIp": ["ALLOWED_CIDR_1", "ALLOWED_CIDR_2"]
        },
        "Bool": {
          "aws:SecureTransport": "true"
        }
      }
    },
    {
      "Sid": "DenyNonTLS",
      "Effect": "Deny",
      "Action": "s3:*",
      "Resource": [
        "arn:aws:s3:::DATA_BUCKET",
        "arn:aws:s3:::DATA_BUCKET/*"
      ],
      "Condition": {
        "Bool": {
          "aws:SecureTransport": "false"
        }
      }
    },
    {
      "Sid": "DenyOutsideAllowedIP",
      "Effect": "Deny",
      "Action": "s3:*",
      "Resource": [
        "arn:aws:s3:::DATA_BUCKET",
        "arn:aws:s3:::DATA_BUCKET/*"
      ],
      "Condition": {
        "NotIpAddress": {
          "aws:SourceIp": ["ALLOWED_CIDR_1", "ALLOWED_CIDR_2"]
        },
        "StringNotEquals": {
          "aws:SourceVpce": "VPCE_ID"
        }
      }
    },
    {
      "Sid": "DenyAccessOutsideSecurePrefix",
      "Effect": "Deny",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "NotResource": "arn:aws:s3:::DATA_BUCKET/secure/*"
    }
  ]
}
```

**왜 이렇게 써야 하나**: 복합 조건은 Allow에 모든 조건을 AND로 걸고, 각 위반 케이스마다 별도 Deny Statement를 두는 구조가 가장 명확하다. 하나의 Deny에 여러 조건을 AND로 묶으면 "모든 조건이 동시에 위반될 때만" Deny가 되어 의도와 달라진다.

`DenyOutsideAllowedIP`의 `Condition` 블록 안에 `NotIpAddress`와 `StringNotEquals`가 함께 있으면 AND 조건이다. "허용 IP도 아니고 허용 VPCE도 아닌 경우"에만 Deny가 걸린다. 즉 VPC Endpoint로 오면 IP 조건과 무관하게 통과된다.

**이거 빠뜨리면?**:
- `DenyNonTLS` 없으면: Allow에 `SecureTransport: true` 조건이 있어도 다른 Allow 정책이 HTTP 접근을 허용할 수 있다.
- `DenyAccessOutsideSecurePrefix`에 `NotResource` 대신 `Resource: *`로 쓰면: `secure/` 외 모든 오브젝트 접근이 차단되지만 `secure/` 내부도 함께 차단된다. `NotResource`를 써야 `secure/` 외부만 차단된다.
- VPC Endpoint 경유 시 `aws:SourceIp`가 설정되지 않는다. IP 조건만 쓰면 VPC 내부 접근도 차단된다. `SourceVpce` 조건을 OR로 함께 써야 한다.

**CloudShell 검증**:

```bash
export DATA_BUCKET="YOUR_BUCKET"
export PROFILE_NAME="mod3-secure-user"
export ALLOWED_IP="YOUR_IP"

# 허용 IP + HTTPS + secure/ prefix — 성공 기대
aws s3 ls "s3://$DATA_BUCKET/secure/" --profile "$PROFILE_NAME"
aws s3 cp "s3://$DATA_BUCKET/secure/data.txt" - --profile "$PROFILE_NAME"

# secure/ 외 prefix 접근 — AccessDenied 기대
aws s3 cp "s3://$DATA_BUCKET/public/data.txt" - --profile "$PROFILE_NAME"

# IP 확인 (CloudShell은 AWS 관리 IP 사용)
curl -s https://checkip.amazonaws.com
```

---

## CloudShell 공통 준비

```bash
export AWS_REGION="ap-northeast-2"
export ACCOUNT_ID="123456789012"
export DATA_BUCKET="YOUR_DATA_BUCKET"

# 정책 적용 공통 패턴
POLICY_NAME="MOD3_CASE_POLICY"
USER_NAME="mod3-test-user"

aws iam create-user --user-name "$USER_NAME"
aws iam create-policy   --policy-name "$POLICY_NAME"   --policy-document file://policy.json
aws iam attach-user-policy   --user-name "$USER_NAME"   --policy-arn "arn:aws:iam::$ACCOUNT_ID:policy/$POLICY_NAME"

# 액세스 키 발급
aws iam create-access-key --user-name "$USER_NAME"
aws configure --profile "mod3-test-user"

# 신분 확인
aws sts get-caller-identity --profile "mod3-test-user"
```

---

## 감점 방지 최종 체크리스트

- `ListBucket` Resource가 `BUCKET/*`이면 오답. 반드시 `BUCKET`(버킷 ARN)
- `s3:prefix` 조건은 `ListBucket`에만 유효. `GetObject`에 걸면 무시됨
- `aws:MultiFactorAuthPresent` 조건은 `BoolIfExists` 사용. `Bool`만 쓰면 액세스 키 직접 사용 시 뚫림
- `${aws:username}` 변수는 IAM User에만 동작. Role 기반이면 `${aws:PrincipalTag/...}` 사용
- 복합 Deny 조건에서 AND/OR 로직 혼동 주의. 같은 Statement 내 여러 조건은 AND
- `NotResource`와 `Resource: *` + Deny는 다르다. `NotResource`는 지정 리소스 외 모두 차단
- 크로스 계정은 Bucket Policy + 상대 계정 IAM Policy 양쪽 모두 Allow 필요
- `s3:content-length-range`는 Multipart Upload 파트 크기 기준. 전체 파일 크기 아님
