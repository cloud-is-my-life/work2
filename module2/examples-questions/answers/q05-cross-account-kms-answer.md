# [정답] 예시 과제 5 — 크로스계정 Athena + KMS

## 목표

- Account A 분석 역할이 Account B 암호화 로그(S3+KMS)를 Athena로 조회
- Account A WorkGroup에서 결과 저장 암호화(SSE-KMS) 강제
- 테이블 생성 + 쿼리 1회 성공(`SUCCEEDED`)까지 검증

---

## 0) CloudShell 변수

```bash
export AWS_REGION="ap-northeast-2"

export AWS_PROFILE_A="account-a"
export AWS_PROFILE_B="account-b"

export ACCOUNT_A_ID="ACCOUNT_A_ID"
export ACCOUNT_B_ID="ACCOUNT_B_ID"

export ATHENA_QUERY_ROLE_NAME="AthenaCrossAccountQueryRole"
export WORKGROUP_NAME="wsi-kms-wg"

export DATA_BUCKET_B="ACCOUNT_B_LOG_BUCKET"
export RESULTS_BUCKET_A="ACCOUNT_A_RESULTS_BUCKET"

export DATA_KMS_KEY_ARN_B="arn:aws:kms:ap-northeast-2:ACCOUNT_B_ID:key/DATA_KEY_ID"
export RESULT_KMS_KEY_ARN_A="arn:aws:kms:ap-northeast-2:ACCOUNT_A_ID:key/RESULT_KEY_ID"
```

---

## 1) Account A 선행 작업 — Athena Query Role 생성

> Account B 정책에서 이 Role ARN을 Principal로 쓰므로 **먼저 생성**한다.

```bash
cat > trust-policy-athena-role.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::$ACCOUNT_A_ID:root"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

aws iam create-role \
  --profile "$AWS_PROFILE_A" \
  --role-name "$ATHENA_QUERY_ROLE_NAME" \
  --assume-role-policy-document file://trust-policy-athena-role.json

cat > athena-cross-account-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AthenaAndGlueRead",
      "Effect": "Allow",
      "Action": [
        "athena:StartQueryExecution",
        "athena:GetQueryExecution",
        "athena:GetQueryResults",
        "athena:GetWorkGroup",
        "athena:ListWorkGroups",
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
      "Sid": "ReadAccountBData",
      "Effect": "Allow",
      "Action": ["s3:GetBucketLocation", "s3:ListBucket", "s3:GetObject"],
      "Resource": [
        "arn:aws:s3:::$DATA_BUCKET_B",
        "arn:aws:s3:::$DATA_BUCKET_B/*"
      ]
    },
    {
      "Sid": "WriteAthenaResults",
      "Effect": "Allow",
      "Action": [
        "s3:GetBucketLocation", "s3:ListBucket", "s3:GetObject", "s3:PutObject",
        "s3:ListBucketMultipartUploads", "s3:ListMultipartUploadParts", "s3:AbortMultipartUpload"
      ],
      "Resource": [
        "arn:aws:s3:::$RESULTS_BUCKET_A",
        "arn:aws:s3:::$RESULTS_BUCKET_A/*"
      ]
    },
    {
      "Sid": "UseDataKmsKeyInAccountB",
      "Effect": "Allow",
      "Action": ["kms:Decrypt", "kms:DescribeKey", "kms:GenerateDataKey"],
      "Resource": "$DATA_KMS_KEY_ARN_B"
    },
    {
      "Sid": "UseResultKmsKeyInAccountA",
      "Effect": "Allow",
      "Action": ["kms:Decrypt", "kms:DescribeKey", "kms:GenerateDataKey"],
      "Resource": "$RESULT_KMS_KEY_ARN_A"
    }
  ]
}
EOF

aws iam put-role-policy \
  --profile "$AWS_PROFILE_A" \
  --role-name "$ATHENA_QUERY_ROLE_NAME" \
  --policy-name "AthenaCrossAccountInline" \
  --policy-document file://athena-cross-account-policy.json
```

---

## 2) Account B 설정 — 버킷 정책 + KMS 키 정책

### 2-1. S3 버킷 정책 적용

```bash
cat > bucket-policy-account-b.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowAccountARoleReadBucket",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::$ACCOUNT_A_ID:role/$ATHENA_QUERY_ROLE_NAME"
      },
      "Action": ["s3:GetBucketLocation", "s3:ListBucket"],
      "Resource": "arn:aws:s3:::$DATA_BUCKET_B"
    },
    {
      "Sid": "AllowAccountARoleReadObjects",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::$ACCOUNT_A_ID:role/$ATHENA_QUERY_ROLE_NAME"
      },
      "Action": ["s3:GetObject"],
      "Resource": "arn:aws:s3:::$DATA_BUCKET_B/*"
    }
  ]
}
EOF

aws s3api put-bucket-policy \
  --profile "$AWS_PROFILE_B" \
  --bucket "$DATA_BUCKET_B" \
  --policy file://bucket-policy-account-b.json
```

### 2-2. KMS 키 정책에 Decrypt Statement 추가

```bash
cat > kms-statement-account-b.json <<EOF
{
  "Sid": "AllowAccountARoleDecrypt",
  "Effect": "Allow",
  "Principal": {
    "AWS": "arn:aws:iam::$ACCOUNT_A_ID:role/$ATHENA_QUERY_ROLE_NAME"
  },
  "Action": ["kms:Decrypt", "kms:DescribeKey", "kms:GenerateDataKey*"],
  "Resource": "*"
}
EOF
```

CloudShell에서 전체 키 정책 반영(기존 policy에 Statement append):

```bash
aws kms get-key-policy \
  --profile "$AWS_PROFILE_B" \
  --key-id "$DATA_KMS_KEY_ARN_B" \
  --policy-name default \
  --query Policy \
  --output text > kms-policy-current.json

python3 - <<'PY'
import json

with open('kms-policy-current.json') as f:
    current = json.load(f)
with open('kms-statement-account-b.json') as f:
    stmt = json.load(f)

statements = current.get('Statement', [])
if not any(s.get('Sid') == stmt.get('Sid') for s in statements):
    statements.append(stmt)
current['Statement'] = statements

with open('kms-policy-updated.json', 'w') as f:
    json.dump(current, f)
PY

aws kms put-key-policy \
  --profile "$AWS_PROFILE_B" \
  --key-id "$DATA_KMS_KEY_ARN_B" \
  --policy-name default \
  --policy file://kms-policy-updated.json
```

---

## 3) Account A WorkGroup 생성 (SSE-KMS 강제)

```bash
aws athena create-work-group \
  --profile "$AWS_PROFILE_A" \
  --name "$WORKGROUP_NAME" \
  --configuration "{\
    \"EnforceWorkGroupConfiguration\": true,\
    \"ResultConfiguration\": {\
      \"OutputLocation\": \"s3://$RESULTS_BUCKET_A/athena-results/\",\
      \"EncryptionConfiguration\": {\
        \"EncryptionOption\": \"SSE_KMS\",\
        \"KmsKey\": \"$RESULT_KMS_KEY_ARN_A\"\
      }\
    }\
  }"
```

---

## 4) 검증 (테이블 1개 + 쿼리 1회 성공)

Athena SQL (WorkGroup: `wsi-kms-wg` 선택):

```sql
CREATE DATABASE IF NOT EXISTS wsi_cross_db;

CREATE EXTERNAL TABLE IF NOT EXISTS wsi_cross_db.cloudtrail_cross (
  eventtime STRING,
  eventname STRING,
  sourceipaddress STRING,
  useridentity STRUCT<username:STRING, arn:STRING>
)
PARTITIONED BY (`timestamp` STRING)
ROW FORMAT SERDE 'org.apache.hive.hcatalog.data.JsonSerDe'
STORED AS INPUTFORMAT 'com.amazon.emr.cloudtrail.CloudTrailInputFormat'
OUTPUTFORMAT 'org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat'
LOCATION 's3://ACCOUNT_B_LOG_BUCKET/AWSLogs/ACCOUNT_B_ID/CloudTrail/ap-northeast-2/'
TBLPROPERTIES (
  'projection.enabled'='true',
  'projection.timestamp.type'='date',
  'projection.timestamp.range'='2026/01/01,NOW',
  'projection.timestamp.format'='yyyy/MM/dd',
  'projection.timestamp.interval'='1',
  'projection.timestamp.interval.unit'='DAYS',
  'storage.location.template'='s3://ACCOUNT_B_LOG_BUCKET/AWSLogs/ACCOUNT_B_ID/CloudTrail/ap-northeast-2/${timestamp}'
);

SELECT eventname, COUNT(*) AS cnt
FROM wsi_cross_db.cloudtrail_cross
WHERE `timestamp` BETWEEN date_format(current_date - INTERVAL '7' DAY, '%Y/%m/%d')
                      AND date_format(current_date, '%Y/%m/%d')
GROUP BY eventname
ORDER BY cnt DESC
LIMIT 20;
```

쿼리 성공 상태 확인(`SUCCEEDED`여야 함):

```bash
LATEST_ID=$(aws athena list-query-executions \
  --profile "$AWS_PROFILE_A" \
  --work-group "$WORKGROUP_NAME" \
  --max-results 1 \
  --query 'QueryExecutionIds[0]' \
  --output text)

aws athena get-query-execution \
  --profile "$AWS_PROFILE_A" \
  --query-execution-id "$LATEST_ID" \
  --query 'QueryExecution.Status.State' \
  --output text
```

---

## 5) Console 경로

- Account B: S3 Bucket policy, KMS Key policy
- Account A: IAM Role(Inline policy), Athena WorkGroup
- Athena Query editor: WorkGroup `wsi-kms-wg` 선택 후 SQL 실행

---

## 6) 감점 방지 포인트

- `s3:GetBucketLocation`은 데이터/결과 버킷 모두 필요
- KMS는 **IAM 정책 + Key policy** 둘 다 허용되어야 복호화 성공
- WorkGroup 강제 옵션(`EnforceWorkGroupConfiguration=true`) 누락 금지
