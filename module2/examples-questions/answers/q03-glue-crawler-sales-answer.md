# [정답] 예시 과제 3 — Glue Crawler 기반 카탈로그 자동화

## 목표

- Glue DB `wsi_auto_db`, Crawler `wsi-sales-crawler` 구성
- 대상 경로 `s3://wsi-qfs-data/sales/daily/`, 6시간 스케줄 적용
- 생성된 테이블로 상품별 총매출 Top 10 조회

---

## 1) CloudShell 변수

```bash
export AWS_REGION="ap-northeast-2"
export GLUE_DB="wsi_auto_db"
export CRAWLER_NAME="wsi-sales-crawler"
export ROLE_NAME="AWSGlueServiceRole-wsi-sales-crawler"
export ACCOUNT_ID="123456789012"
export DATA_BUCKET="wsi-qfs-data"
export DATA_PREFIX="sales/daily/"
```

---

## 2) IAM Role 생성 (Glue 서비스 역할)

> 역할 이름은 `AWSGlueServiceRole`로 시작하게 유지.

```bash
cat > trust-policy.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {"Service": "glue.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

cat > crawler-policy.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "GlueCatalog",
      "Effect": "Allow",
      "Action": [
        "glue:GetDatabase","glue:GetDatabases",
        "glue:CreateTable","glue:UpdateTable",
        "glue:GetTable","glue:GetTables",
        "glue:CreatePartition","glue:BatchCreatePartition",
        "glue:UpdatePartition","glue:GetPartition",
        "glue:GetPartitions","glue:BatchGetPartition"
      ],
      "Resource": "*"
    },
    {
      "Sid": "ReadSalesData",
      "Effect": "Allow",
      "Action": ["s3:GetObject","s3:ListBucket","s3:GetBucketLocation"],
      "Resource": [
        "arn:aws:s3:::wsi-qfs-data",
        "arn:aws:s3:::wsi-qfs-data/*"
      ]
    },
    {
      "Sid": "Logs",
      "Effect": "Allow",
      "Action": ["logs:CreateLogGroup","logs:CreateLogStream","logs:PutLogEvents"],
      "Resource": "arn:aws:logs:*:*:*"
    }
  ]
}
EOF

aws iam create-role \
  --role-name "$ROLE_NAME" \
  --assume-role-policy-document file://trust-policy.json

aws iam put-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-name "WsiSalesCrawlerInline" \
  --policy-document file://crawler-policy.json
```

---

## 3) Glue DB + Crawler 생성/스케줄

```bash
aws glue create-database \
  --database-input "{\"Name\":\"$GLUE_DB\"}"

aws glue create-crawler \
  --name "$CRAWLER_NAME" \
  --role "arn:aws:iam::$ACCOUNT_ID:role/$ROLE_NAME" \
  --database-name "$GLUE_DB" \
  --targets "{\"S3Targets\":[{\"Path\":\"s3://$DATA_BUCKET/$DATA_PREFIX\"}]}" \
  --schedule "cron(0 */6 * * ? *)" \
  --schema-change-policy '{"UpdateBehavior":"UPDATE_IN_DATABASE","DeleteBehavior":"LOG"}' \
  --recrawl-policy '{"RecrawlBehavior":"CRAWL_NEW_FOLDERS_ONLY"}'
```

Crawler 1회 실행:

```bash
aws glue start-crawler --name "$CRAWLER_NAME"

while true; do
  STATE=$(aws glue get-crawler --name "$CRAWLER_NAME" --query 'Crawler.State' --output text)
  echo "Crawler state: $STATE"
  [ "$STATE" = "READY" ] && break
  sleep 10
done
```

---

## 4) Athena Top 10 집계 (정답)

크롤러가 만든 테이블명 확인:

```bash
CRAWLED_TABLE=$(aws glue get-tables \
  --database-name "$GLUE_DB" \
  --query 'TableList[0].Name' \
  --output text)

echo "$CRAWLED_TABLE"
```

Athena SQL:

```sql
SELECT
  product_name,
  SUM(CAST(amount AS DOUBLE)) AS total_sales
FROM wsi_auto_db.<CRAWLED_TABLE>
GROUP BY product_name
ORDER BY total_sales DESC
LIMIT 10;
```

`<CRAWLED_TABLE>`은 위에서 확인한 실제 테이블명으로 치환.

---

## 5) 검증 명령

```bash
aws glue get-crawler --name "$CRAWLER_NAME" \
  --query 'Crawler.{Name:Name,State:State,Schedule:Schedule}' \
  --output table

aws glue get-tables --database-name "$GLUE_DB" \
  --query 'TableList[].Name' \
  --output table
```

---

## 6) Console 경로

- AWS Glue Console → Data Catalog → Databases → `wsi_auto_db`
- AWS Glue Console → Crawlers → `wsi-sales-crawler` (Schedule/Last run 확인)
- Athena Console → Query editor에서 상품 매출 Top 10 SQL 실행

---

## 7) 감점 방지 포인트

- Crawler 역할명 prefix: `AWSGlueServiceRole...`
- Crawler 스케줄 형식: `cron(0 */6 * * ? *)`
- Crawler 실행 후 `READY` 상태까지 기다린 뒤 Athena 쿼리
