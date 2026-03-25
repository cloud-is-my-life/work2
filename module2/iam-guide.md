# IAM 가이드 — Athena / Glue / S3 Select

---

## 핵심 요약

> ⚠️ **s3:GetBucketLocation 빠뜨리면 Access Denied!** 가장 흔한 실수. 데이터 버킷 + 결과 버킷 둘 다 필요.

> ⚠️ **Glue Crawler Role은 Glue 권한 + S3 권한 둘 다 필요!** S3만 주면 카탈로그 등록 실패.

> ⚠️ **SSE-KMS 암호화 데이터 쿼리 시 kms:Decrypt 필요!** SSE-S3는 추가 권한 불필요.

> ⚠️ **CSE-KMS (클라이언트 측 암호화) 데이터는 Athena가 읽을 수 없음!**

---

## 1. Athena 최소 권한 정책

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AthenaExecution",
      "Effect": "Allow",
      "Action": [
        "athena:StartQueryExecution",
        "athena:StopQueryExecution",
        "athena:GetQueryExecution",
        "athena:GetQueryResults",
        "athena:GetWorkGroup",
        "athena:ListWorkGroups"
      ],
      "Resource": "*"
    },
    {
      "Sid": "GlueCatalogRead",
      "Effect": "Allow",
      "Action": [
        "glue:GetDatabase",
        "glue:GetDatabases",
        "glue:GetTable",
        "glue:GetTables",
        "glue:GetPartition",
        "glue:GetPartitions",
        "glue:BatchGetPartition"
      ],
      "Resource": "*"
    },
    {
      "Sid": "S3DataRead",
      "Effect": "Allow",
      "Action": [
        "s3:GetBucketLocation",
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::DATA-BUCKET",
        "arn:aws:s3:::DATA-BUCKET/*"
      ]
    },
    {
      "Sid": "S3ResultsWrite",
      "Effect": "Allow",
      "Action": [
        "s3:GetBucketLocation",
        "s3:GetObject",
        "s3:ListBucket",
        "s3:ListBucketMultipartUploads",
        "s3:ListMultipartUploadParts",
        "s3:AbortMultipartUpload",
        "s3:PutObject"
      ],
      "Resource": [
        "arn:aws:s3:::RESULTS-BUCKET",
        "arn:aws:s3:::RESULTS-BUCKET/*"
      ]
    }
  ]
}
```

---

## 2. 읽기 전용 Athena 사용자

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AthenaReadOnly",
      "Effect": "Allow",
      "Action": [
        "athena:GetQueryExecution",
        "athena:GetQueryResults",
        "athena:ListQueryExecutions",
        "athena:ListNamedQueries",
        "athena:GetNamedQuery",
        "athena:GetWorkGroup",
        "athena:ListWorkGroups",
        "athena:BatchGetQueryExecution"
      ],
      "Resource": "*"
    },
    {
      "Sid": "GlueReadOnly",
      "Effect": "Allow",
      "Action": [
        "glue:GetDatabase", "glue:GetDatabases",
        "glue:GetTable", "glue:GetTables",
        "glue:GetPartition", "glue:GetPartitions",
        "glue:BatchGetPartition"
      ],
      "Resource": "*"
    },
    {
      "Sid": "S3ReadOnly",
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:GetBucketLocation", "s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::DATA-BUCKET",
        "arn:aws:s3:::DATA-BUCKET/*",
        "arn:aws:s3:::RESULTS-BUCKET",
        "arn:aws:s3:::RESULTS-BUCKET/*"
      ]
    }
  ]
}
```

---

## 3. 워크그룹 제한 사용자

특정 워크그룹만 사용 가능하도록 제한:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowSpecificWorkgroup",
      "Effect": "Allow",
      "Action": [
        "athena:StartQueryExecution",
        "athena:StopQueryExecution",
        "athena:GetQueryExecution",
        "athena:GetQueryResults",
        "athena:GetWorkGroup"
      ],
      "Resource": "arn:aws:athena:REGION:ACCOUNT:workgroup/WORKGROUP-NAME"
    },
    {
      "Sid": "DenyPrimaryWorkgroup",
      "Effect": "Deny",
      "Action": "athena:*",
      "Resource": "arn:aws:athena:REGION:ACCOUNT:workgroup/primary"
    }
  ]
}
```

---

## 4. 데이터베이스 제한 사용자

특정 Glue 데이터베이스만 접근 가능:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "GlueSpecificDB",
      "Effect": "Allow",
      "Action": [
        "glue:GetDatabase", "glue:GetTable", "glue:GetTables",
        "glue:GetPartitions", "glue:BatchGetPartition"
      ],
      "Resource": [
        "arn:aws:glue:REGION:ACCOUNT:catalog",
        "arn:aws:glue:REGION:ACCOUNT:database/DB-NAME",
        "arn:aws:glue:REGION:ACCOUNT:table/DB-NAME/*"
      ]
    }
  ]
}
```

---

## 5. Glue Crawler 최소 권한

### Trust Policy
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "glue.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}
```

### Permission Policy
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "GlueCatalog",
      "Effect": "Allow",
      "Action": [
        "glue:GetDatabase", "glue:GetDatabases",
        "glue:CreateTable", "glue:UpdateTable",
        "glue:GetTable", "glue:GetTables",
        "glue:CreatePartition", "glue:BatchCreatePartition",
        "glue:UpdatePartition", "glue:GetPartition",
        "glue:GetPartitions", "glue:BatchGetPartition",
        "glue:ImportCatalogToGlue"
      ],
      "Resource": "*"
    },
    {
      "Sid": "S3Access",
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:ListBucket", "s3:GetBucketLocation"],
      "Resource": [
        "arn:aws:s3:::DATA-BUCKET",
        "arn:aws:s3:::DATA-BUCKET/*"
      ]
    },
    {
      "Sid": "Logs",
      "Effect": "Allow",
      "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
      "Resource": "arn:aws:logs:*:*:*"
    }
  ]
}
```

---

## 6. 크로스계정 Athena 쿼리

Account A가 Account B의 S3 데이터를 Athena로 쿼리하는 경우:

### Account B: S3 버킷 정책
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "CrossAccountRead",
    "Effect": "Allow",
    "Principal": {"AWS": "arn:aws:iam::ACCOUNT-A-ID:root"},
    "Action": [
      "s3:GetBucketLocation",
      "s3:GetObject",
      "s3:ListBucket"
    ],
    "Resource": [
      "arn:aws:s3:::ACCOUNT-B-BUCKET",
      "arn:aws:s3:::ACCOUNT-B-BUCKET/*"
    ]
  }]
}
```

### Account A: IAM 정책
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:GetBucketLocation", "s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::ACCOUNT-B-BUCKET",
        "arn:aws:s3:::ACCOUNT-B-BUCKET/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject", "s3:ListBucket", "s3:GetBucketLocation"],
      "Resource": [
        "arn:aws:s3:::ACCOUNT-A-RESULTS",
        "arn:aws:s3:::ACCOUNT-A-RESULTS/*"
      ]
    }
  ]
}
```

### KMS 암호화 버킷인 경우 (Account B KMS 키 정책 추가)
```json
{
  "Sid": "CrossAccountDecrypt",
  "Effect": "Allow",
  "Principal": {"AWS": "arn:aws:iam::ACCOUNT-A-ID:role/AthenaRole"},
  "Action": ["kms:Decrypt", "kms:DescribeKey", "kms:GenerateDataKey*"],
  "Resource": "*"
}
```

---

## 7. KMS 암호화 결과 설정

### Athena 결과 암호화 시 필요한 KMS 권한
```json
{
  "Sid": "AthenaKMS",
  "Effect": "Allow",
  "Action": [
    "kms:GenerateDataKey",
    "kms:Decrypt",
    "kms:DescribeKey"
  ],
  "Resource": "arn:aws:kms:REGION:ACCOUNT:key/KEY-ID"
}
```

### KMS 키 정책 (Athena 사용 허용)
```json
{
  "Sid": "AllowAthenaUse",
  "Effect": "Allow",
  "Principal": {"AWS": "arn:aws:iam::ACCOUNT:role/AthenaRole"},
  "Action": ["kms:GenerateDataKey", "kms:Decrypt", "kms:DescribeKey"],
  "Resource": "*"
}
```

### 암호화 옵션별 필요 권한

| 옵션 | 데이터 읽기 | 결과 쓰기 |
|------|------------|-----------|
| SSE-S3 | 추가 권한 없음 | 추가 권한 없음 |
| SSE-KMS | `kms:Decrypt` | `kms:GenerateDataKey`, `kms:Decrypt` |
| CSE-KMS | **Athena 읽기 불가!** | - |

---

## 8. S3 결과 버킷 정책

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AthenaResults",
      "Effect": "Allow",
      "Principal": {"AWS": "arn:aws:iam::ACCOUNT:role/AthenaRole"},
      "Action": [
        "s3:GetBucketLocation", "s3:GetObject",
        "s3:ListBucket", "s3:PutObject",
        "s3:ListBucketMultipartUploads",
        "s3:ListMultipartUploadParts",
        "s3:AbortMultipartUpload"
      ],
      "Resource": [
        "arn:aws:s3:::RESULTS-BUCKET",
        "arn:aws:s3:::RESULTS-BUCKET/*"
      ]
    },
    {
      "Sid": "DenyNonSSL",
      "Effect": "Deny",
      "Principal": "*",
      "Action": "s3:*",
      "Resource": [
        "arn:aws:s3:::RESULTS-BUCKET",
        "arn:aws:s3:::RESULTS-BUCKET/*"
      ],
      "Condition": {"Bool": {"aws:SecureTransport": "false"}}
    }
  ]
}
```

---

## 9. AmazonAthenaFullAccess 매니지드 정책 포함 내용

| 서비스 | 주요 액션 |
|--------|----------|
| Athena | `athena:*` |
| Glue | `glue:GetDatabase`, `GetDatabases`, `GetTable`, `GetTables`, `GetPartition`, `GetPartitions`, `BatchGetPartition`, `GetCatalog`, `GetCatalogs` |
| S3 | `GetBucketLocation`, `GetObject`, `ListBucket`, `PutObject`, `CreateBucket`, `ListBucketMultipartUploads`, `ListMultipartUploadParts`, `AbortMultipartUpload` |
| CloudWatch | `PutMetricAlarm`, `DescribeAlarms`, `DeleteAlarms`, `GetMetricData` |
| SNS | `ListTopics`, `GetTopicAttributes` |
| Lake Formation | `GetDataAccess` |

---

## 10. Lake Formation 연동

Lake Formation이 활성화된 환경에서는 IAM + Lake Formation 이중 게이트:

```bash
# Lake Formation SELECT 권한 부여
aws lakeformation grant-permissions \
  --principal '{"DataLakePrincipalIdentifier": "arn:aws:iam::ACCOUNT:role/AthenaRole"}' \
  --permissions '["SELECT"]' \
  --resource '{"Table": {"DatabaseName": "my_db", "Name": "my_table"}}'
```

> IAM 정책에 `lakeformation:GetDataAccess` 필요 (AmazonAthenaFullAccess에 포함됨)
