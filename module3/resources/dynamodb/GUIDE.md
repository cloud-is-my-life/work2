# DynamoDB Fine-grained IAM 완전 정복 가이드

> AWS Skills Competition 2026 대비 | Module 3 | 고등학생 수험자용

---

## 빈출 패턴 요약

시험에서 DynamoDB IAM 문제가 나오면 아래 5가지를 먼저 떠올려라.

| 패턴 | 핵심 키워드 | 자주 나오는 함정 |
|---|---|---|
| 행 수준 제한 | `LeadingKeys` + `ForAllValues:StringEquals` | `ForAllValues:` 접두사 누락 |
| 열 수준 제한 | `Attributes` + `Select: SPECIFIC_ATTRIBUTES` | `Select` 조건 빠뜨리면 전체 반환 |
| 인덱스 접근 | 인덱스 ARN 별도 추가 | 테이블 ARN만 넣으면 GSI 쿼리 실패 |
| 트랜잭션 구분 | `EnclosingOperation` | 트랜잭션 내부 단일 작업도 IAM 평가 대상 |
| ABAC | `aws:ResourceTag` + `aws:PrincipalTag` | 계정 ABAC 활성화 안 하면 조건 무시됨 |

---

## LeadingKeys 완전 정복

### ForAllValues vs ForAnyValue, 뭐가 다른가

DynamoDB `LeadingKeys`는 배열 타입 조건 키다. 요청 하나에 키 값이 여러 개 들어올 수 있다 (BatchGetItem처럼). 그래서 일반 `StringEquals`가 아니라 집합 연산자를 써야 한다.

```
ForAllValues:StringEquals  →  요청의 모든 키 값이 조건 목록 안에 있어야 Allow
ForAnyValue:StringEquals   →  요청의 키 값 중 하나라도 조건 목록에 있으면 Allow
```

`LeadingKeys`에는 반드시 `ForAllValues:`를 써야 한다. `ForAnyValue:`를 쓰면 조건 목록에 없는 키도 섞어서 요청할 때 통과될 수 있다.

### ForAllValues의 빈 집합 함정

`ForAllValues:`는 요청에 해당 컨텍스트 키가 아예 없으면 조건을 `true`로 평가한다. 즉, `LeadingKeys` 값이 요청에 포함되지 않는 작업(예: `DescribeTable`)은 조건을 통과해버린다. 이건 버그가 아니라 설계된 동작이다. `DescribeTable`처럼 키 값이 없는 작업은 별도 Statement로 분리해서 허용하면 된다.

### 정책 변수 ${aws:username}

```json
"dynamodb:LeadingKeys": ["${aws:username}"]
```

IAM이 정책을 평가할 때 `${aws:username}`을 실제 IAM 사용자 이름으로 치환한다. 테이블의 파티션 키 값이 IAM 사용자 이름과 같으면 접근 허용, 다르면 거부. 멀티테넌트 테이블에서 사용자별 데이터 격리를 정책 하나로 구현할 수 있다.

### Scan은 LeadingKeys를 우회한다

`Scan`은 파티션 키 조건 없이 전체 테이블을 읽는다. DynamoDB는 `Scan` 요청에 `LeadingKeys` 컨텍스트 키를 채우지 않는다. 그러면 `ForAllValues:`가 빈 집합으로 `true`를 반환해서 Scan이 통과된다. 반드시 `Scan`을 Action 목록에서 빼거나 Explicit Deny로 막아야 한다.

---

## ARN 실수 방지

### 테이블 ARN vs 인덱스 ARN

```
테이블:  arn:aws:dynamodb:REGION:ACCOUNT_ID:table/TABLE_NAME
GSI:     arn:aws:dynamodb:REGION:ACCOUNT_ID:table/TABLE_NAME/index/INDEX_NAME
LSI:     arn:aws:dynamodb:REGION:ACCOUNT_ID:table/TABLE_NAME/index/INDEX_NAME
Stream:  arn:aws:dynamodb:REGION:ACCOUNT_ID:table/TABLE_NAME/stream/*
```

인덱스 쿼리를 허용하려면 인덱스 ARN을 Resource에 추가해야 한다. 테이블 ARN만 있으면 `Query`를 인덱스에 날릴 때 `AccessDenied`가 난다.

반대로 인덱스 ARN만 Resource에 넣으면 테이블 직접 접근은 자동으로 막힌다. GSI 전용 읽기 역할을 만들 때 유용하다.

### 와일드카드 주의

```
table/TABLE_NAME/index/*   →  해당 테이블의 모든 인덱스 허용
table/*/index/*            →  계정 내 모든 테이블의 모든 인덱스 허용 (위험)
```

특정 인덱스만 허용하려면 `index/*` 대신 정확한 인덱스 이름을 써야 한다.

### Stream ARN

Stream은 테이블 ARN과 별개다. `DescribeStream`, `GetRecords`, `GetShardIterator`는 Stream ARN에 대한 권한이 필요하다. `ListStreams`는 테이블 ARN 또는 `*`에 대한 권한이 필요하다.

---

## 기존 케이스 빠른 복습 (Case 01~06)

### Case 01 — LeadingKeys 행 수준 제한
파티션 키 = IAM 사용자명인 항목만 CRUD 허용. `ForAllValues:StringEquals` + `${aws:username}`. Scan은 Action에서 제외.

### Case 02 — Attributes 열 수준 제한
허용 속성 목록 지정 + `Select: SPECIFIC_ATTRIBUTES` 강제. 기본 키 속성도 목록에 포함해야 한다. `PutItem`/`DeleteItem`은 전체 아이템 교체라 Attributes 제한이 의미 없으므로 Action에서 제외.

### Case 03 — Scan/DeleteTable 파괴 방지
Allow Statement로 CRUD 허용, Deny Statement로 `Scan`/`DeleteTable` 명시적 거부. PartiQL 우회도 막으려면 Case 06과 병행.

### Case 04 — ABAC 태그 기반 팀 단위 접근
`aws:ResourceTag/Team` = `${aws:PrincipalTag/Team}` 동적 매칭. 계정 ABAC 활성화 필수. 태그 없는 주체는 Deny로 차단.

### Case 05 — GSI 쿼리 전용
Resource에 인덱스 ARN만 지정. `dynamodb:Attributes`로 Projected 속성만 허용. 테이블 직접 접근 자동 차단.

### Case 06 — PartiQL 전체 스캔 차단
`dynamodb:FullTableScan: true` 조건으로 Deny. `BatchExecuteStatement`도 함께 막아야 배치 우회 차단.

---

## 신규 케이스 상세 (Case 07~12)


### Case 07 — LeadingKeys + Attributes 복합 (행+열 동시 제한)

**시나리오**: 멀티테넌트 테이블에서 사용자가 자기 파티션 키 항목만 접근할 수 있고, 그 안에서도 허용된 속성만 읽고 쓸 수 있다.

**정책 JSON**:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowOwnRowsAndSpecificColumnsOnly",
      "Effect": "Allow",
      "Action": ["dynamodb:GetItem", "dynamodb:Query", "dynamodb:UpdateItem"],
      "Resource": "arn:aws:dynamodb:AWS_REGION:ACCOUNT_ID:table/TABLE_NAME",
      "Condition": {
        "ForAllValues:StringEquals": {
          "dynamodb:LeadingKeys": ["${aws:username}"],
          "dynamodb:Attributes": ["UserId", "Name", "Email", "Score", "UpdatedAt"]
        },
        "StringEqualsIfExists": {
          "dynamodb:Select": "SPECIFIC_ATTRIBUTES",
          "dynamodb:ReturnValues": ["NONE", "UPDATED_OLD", "UPDATED_NEW"]
        }
      }
    },
    {
      "Sid": "DenyAllScan",
      "Effect": "Deny",
      "Action": "dynamodb:Scan",
      "Resource": "arn:aws:dynamodb:AWS_REGION:ACCOUNT_ID:table/TABLE_NAME"
    }
  ]
}
```

**왜 이렇게 써야 하는가**: `ForAllValues:StringEquals` 블록 하나에 `LeadingKeys`와 `Attributes`를 같이 넣으면 두 조건이 AND로 묶인다. 행 제한과 열 제한이 동시에 적용된다. `StringEqualsIfExists`로 `Select`를 걸면 클라이언트가 `ProjectionExpression` 없이 요청할 때도 `SPECIFIC_ATTRIBUTES`가 강제된다.

**이거 빠뜨리면?**:
- `dynamodb:Select` 조건 없이 `Attributes`만 걸면 클라이언트가 `Select=ALL_ATTRIBUTES`로 전체 속성을 가져갈 수 있다.
- `PutItem`을 Action에 포함하면 `Attributes` 제한이 무의미해진다. `PutItem`은 아이템 전체를 교체하므로 속성 목록 조건이 적용되지 않는다.
- `ReturnValues`를 `ALL_OLD`/`ALL_NEW`로 허용하면 제한된 속성도 응답에 포함된다.

**CloudShell 검증**:

```bash
export TABLE_NAME="MOD3_DDB_TABLE"
export PROFILE_NAME="mod3-ddb-user"

# 자기 행 + 허용 속성만 조회 — 성공 기대
aws dynamodb get-item \
  --table-name "$TABLE_NAME" \
  --key "{\"UserId\":{\"S\":\"$PROFILE_NAME\"}}" \
  --projection-expression "UserId, Name, Email" \
  --profile "$PROFILE_NAME"

# 허용 외 속성 포함 조회 — AccessDenied 기대
aws dynamodb get-item \
  --table-name "$TABLE_NAME" \
  --key "{\"UserId\":{\"S\":\"$PROFILE_NAME\"}}" \
  --projection-expression "UserId, SSN" \
  --profile "$PROFILE_NAME"

# 다른 사용자 행 접근 — AccessDenied 기대
aws dynamodb get-item \
  --table-name "$TABLE_NAME" \
  --key '{"UserId":{"S":"other-user"}}' \
  --projection-expression "UserId, Name" \
  --profile "$PROFILE_NAME"
```

---

### Case 08 — BatchWriteItem/BatchGetItem에서의 LeadingKeys 동작

**시나리오**: 배치 작업에서도 사용자가 자기 파티션 키 항목만 읽고 쓸 수 있다. 배치 요청 안에 다른 사용자 키가 하나라도 섞이면 전체 요청이 거부된다.

**정책 JSON**:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowBatchOpsOwnItemsOnly",
      "Effect": "Allow",
      "Action": ["dynamodb:BatchGetItem", "dynamodb:BatchWriteItem"],
      "Resource": "arn:aws:dynamodb:AWS_REGION:ACCOUNT_ID:table/TABLE_NAME",
      "Condition": {
        "ForAllValues:StringEquals": {
          "dynamodb:LeadingKeys": ["${aws:username}"]
        }
      }
    },
    {
      "Sid": "DenyBatchScanWorkaround",
      "Effect": "Deny",
      "Action": "dynamodb:Scan",
      "Resource": "arn:aws:dynamodb:AWS_REGION:ACCOUNT_ID:table/TABLE_NAME"
    }
  ]
}
```

**왜 이렇게 써야 하는가**: `BatchGetItem`은 요청 하나에 여러 키를 담을 수 있다. DynamoDB는 배치 안의 모든 키 값을 `dynamodb:LeadingKeys` 컨텍스트 키에 배열로 채운다. `ForAllValues:StringEquals`는 그 배열의 모든 값이 조건 목록에 있어야 통과시킨다. 배치 안에 `user-a`와 `user-b`가 섞이면 `user-b`가 조건을 위반해서 전체 요청이 거부된다.

**이거 빠뜨리면?**:
- `ForAnyValue:`를 쓰면 자기 키가 하나라도 있으면 다른 사용자 키도 같이 통과된다. 반드시 `ForAllValues:`를 써야 한다.
- `BatchWriteItem`에는 `PutRequest`와 `DeleteRequest`가 섞일 수 있다. 두 작업 모두 `LeadingKeys` 조건이 적용된다.

**CloudShell 검증**:

```bash
# 자기 키만 포함한 배치 조회 — 성공 기대
aws dynamodb batch-get-item \
  --request-items "{
    \"$TABLE_NAME\": {
      \"Keys\": [{\"UserId\":{\"S\":\"$PROFILE_NAME\"}}]
    }
  }" \
  --profile "$PROFILE_NAME"

# 다른 사용자 키 포함 배치 조회 — AccessDenied 기대
aws dynamodb batch-get-item \
  --request-items "{
    \"$TABLE_NAME\": {
      \"Keys\": [
        {\"UserId\":{\"S\":\"$PROFILE_NAME\"}},
        {\"UserId\":{\"S\":\"other-user\"}}
      ]
    }
  }" \
  --profile "$PROFILE_NAME"
```

---

### Case 09 — 트랜잭션 작업 제한 (TransactWriteItems/TransactGetItems)

**시나리오**: 트랜잭션 API만 허용하고 단일 쓰기 API는 차단한다. 트랜잭션 안에서도 자기 파티션 키 항목만 접근 가능하다.

**정책 JSON**:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowTransactOpsOwnItemsOnly",
      "Effect": "Allow",
      "Action": ["dynamodb:TransactWriteItems", "dynamodb:TransactGetItems"],
      "Resource": "arn:aws:dynamodb:AWS_REGION:ACCOUNT_ID:table/TABLE_NAME",
      "Condition": {
        "ForAllValues:StringEquals": {
          "dynamodb:LeadingKeys": ["${aws:username}"]
        }
      }
    },
    {
      "Sid": "AllowSingleOpsViaTransactionContext",
      "Effect": "Allow",
      "Action": ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:DeleteItem"],
      "Resource": "arn:aws:dynamodb:AWS_REGION:ACCOUNT_ID:table/TABLE_NAME",
      "Condition": {
        "ForAllValues:StringEquals": {
          "dynamodb:LeadingKeys": ["${aws:username}"]
        },
        "StringEquals": {
          "dynamodb:EnclosingOperation": ["TransactWriteItems", "TransactGetItems"]
        }
      }
    },
    {
      "Sid": "DenyDirectWriteOutsideTransaction",
      "Effect": "Deny",
      "Action": ["dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:DeleteItem"],
      "Resource": "arn:aws:dynamodb:AWS_REGION:ACCOUNT_ID:table/TABLE_NAME",
      "Condition": {
        "StringNotEquals": {
          "dynamodb:EnclosingOperation": "TransactWriteItems"
        }
      }
    }
  ]
}
```

**왜 이렇게 써야 하는가**: `TransactWriteItems`를 호출하면 DynamoDB가 내부적으로 `PutItem`/`UpdateItem`/`DeleteItem`을 실행한다. IAM은 트랜잭션 API와 내부 단일 작업 API 모두에 대해 권한을 평가한다. `dynamodb:EnclosingOperation` 조건 키로 "이 단일 작업이 트랜잭션 안에서 호출된 것인지" 구분할 수 있다. 트랜잭션 컨텍스트 밖에서 직접 `PutItem`을 호출하면 `EnclosingOperation`이 없으므로 Deny Statement가 발동한다.

**이거 빠뜨리면?**:
- `EnclosingOperation` 조건 없이 단일 작업을 허용하면 트랜잭션 우회 없이 직접 쓰기가 가능해진다.
- `TransactGetItems`도 내부적으로 `GetItem`을 호출한다. 읽기 트랜잭션도 같은 패턴으로 제어해야 한다.

**CloudShell 검증**:

```bash
# 트랜잭션 쓰기 — 성공 기대
aws dynamodb transact-write-items \
  --transact-items "[{
    \"Put\": {
      \"TableName\": \"$TABLE_NAME\",
      \"Item\": {\"UserId\":{\"S\":\"$PROFILE_NAME\"}, \"Data\":{\"S\":\"test\"}}
    }
  }]" \
  --profile "$PROFILE_NAME"

# 직접 PutItem — AccessDenied 기대
aws dynamodb put-item \
  --table-name "$TABLE_NAME" \
  --item "{\"UserId\":{\"S\":\"$PROFILE_NAME\"}, \"Data\":{\"S\":\"test\"}}" \
  --profile "$PROFILE_NAME"
```

---

### Case 10 — Streams 읽기 전용

**시나리오**: Lambda나 외부 소비자가 DynamoDB Streams를 읽을 수 있지만 테이블 데이터에는 직접 접근할 수 없다.

**정책 JSON**:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowStreamsReadOnly",
      "Effect": "Allow",
      "Action": [
        "dynamodb:DescribeStream",
        "dynamodb:GetRecords",
        "dynamodb:GetShardIterator",
        "dynamodb:ListStreams"
      ],
      "Resource": "arn:aws:dynamodb:AWS_REGION:ACCOUNT_ID:table/TABLE_NAME/stream/*"
    },
    {
      "Sid": "AllowDescribeTableForStreamDiscovery",
      "Effect": "Allow",
      "Action": ["dynamodb:DescribeTable", "dynamodb:ListTables"],
      "Resource": "*"
    },
    {
      "Sid": "DenyTableDataAccess",
      "Effect": "Deny",
      "Action": [
        "dynamodb:GetItem", "dynamodb:BatchGetItem", "dynamodb:Query", "dynamodb:Scan",
        "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:DeleteItem",
        "dynamodb:BatchWriteItem", "dynamodb:TransactGetItems", "dynamodb:TransactWriteItems"
      ],
      "Resource": "arn:aws:dynamodb:AWS_REGION:ACCOUNT_ID:table/TABLE_NAME"
    }
  ]
}
```

**왜 이렇게 써야 하는가**: Stream ARN과 테이블 ARN은 별개다. Stream 읽기 권한은 `table/TABLE_NAME/stream/*` ARN에 부여하고, 테이블 직접 접근은 Deny로 명시적으로 차단한다. `ListStreams`는 테이블 ARN 또는 `*`에 대한 권한이 필요하므로 `DescribeTable`과 함께 `*` Resource Statement에 넣는다.

**이거 빠뜨리면?**:
- Stream ARN 대신 테이블 ARN에 `GetRecords`를 허용하면 권한이 적용되지 않는다. Stream 작업은 반드시 Stream ARN이 Resource여야 한다.
- `DescribeStream` 없이 `GetShardIterator`만 허용하면 스트림 구조를 파악할 수 없어서 소비자가 동작하지 않는다.
- Streams를 활성화하지 않은 테이블에 이 정책을 붙이면 `GetRecords` 호출 시 DynamoDB 레벨 오류가 난다 (IAM 오류가 아님).

**CloudShell 검증**:

```bash
export STREAM_ARN=$(aws dynamodb describe-table \
  --table-name "$TABLE_NAME" \
  --query "Table.LatestStreamArn" \
  --output text)

# 스트림 설명 조회 — 성공 기대
aws dynamodb describe-stream \
  --stream-arn "$STREAM_ARN" \
  --profile "$PROFILE_NAME"

# 테이블 직접 조회 — AccessDenied 기대
aws dynamodb scan \
  --table-name "$TABLE_NAME" \
  --profile "$PROFILE_NAME"
```

---

### Case 11 — 테이블 생성 시 태그 강제 + 암호화 강제

**시나리오**: 개발자가 테이블을 생성할 때 `Environment`와 `Owner` 태그를 반드시 붙여야 한다. 태그 없이 생성하면 거부된다.

**정책 JSON**:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowCreateTableOnlyWithRequiredTags",
      "Effect": "Allow",
      "Action": "dynamodb:CreateTable",
      "Resource": "arn:aws:dynamodb:AWS_REGION:ACCOUNT_ID:table/*",
      "Condition": {
        "StringEquals": {
          "aws:RequestTag/Environment": ["production", "staging", "development"],
          "aws:RequestTag/Owner": "${aws:username}"
        }
      }
    },
    {
      "Sid": "DenyCreateTableWithoutRequiredTags",
      "Effect": "Deny",
      "Action": "dynamodb:CreateTable",
      "Resource": "arn:aws:dynamodb:AWS_REGION:ACCOUNT_ID:table/*",
      "Condition": {
        "Null": {
          "aws:RequestTag/Environment": "true",
          "aws:RequestTag/Owner": "true"
        }
      }
    },
    {
      "Sid": "AllowDescribeAndList",
      "Effect": "Allow",
      "Action": ["dynamodb:DescribeTable", "dynamodb:ListTables", "dynamodb:ListTagsOfResource"],
      "Resource": "*"
    }
  ]
}
```

**왜 이렇게 써야 하는가**: Allow Statement만으로는 부족하다. 태그 없이 요청하면 Allow 조건이 false가 되어 묵시적 거부가 되지만, 다른 정책(예: AdministratorAccess)이 붙어 있으면 그쪽에서 허용될 수 있다. Deny Statement를 추가하면 다른 정책과 무관하게 태그 없는 생성을 막는다. `aws:RequestTag`는 생성 요청에 포함된 태그를 검사한다. `aws:ResourceTag`와 혼동하지 말 것. `aws:ResourceTag`는 이미 존재하는 리소스의 태그를 검사한다.

**이거 빠뜨리면?**:
- `Null` 조건에서 `"true"`는 문자열이다. `true` (불리언)가 아니다. JSON에서 따옴표를 빠뜨리면 정책 검증 오류가 난다.
- `aws:RequestTag/Owner`에 `${aws:username}`을 쓰면 자기 이름만 Owner로 설정 가능하다. 다른 사람 이름으로 태그를 달면 거부된다.
- DynamoDB `CreateTable`에서 암호화 타입을 IAM 조건으로 강제하는 공식 조건 키는 현재 지원이 제한적이다. 암호화 강제는 AWS Config 규칙(`dynamodb-table-encrypted-at-rest`)과 병행하는 것이 더 확실하다.

**CloudShell 검증**:

```bash
# 태그 포함 테이블 생성 — 성공 기대
aws dynamodb create-table \
  --table-name "TestTable" \
  --attribute-definitions AttributeName=PK,AttributeType=S \
  --key-schema AttributeName=PK,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --tags Key=Environment,Value=development "Key=Owner,Value=$PROFILE_NAME" \
  --profile "$PROFILE_NAME"

# 태그 없이 테이블 생성 — AccessDenied 기대
aws dynamodb create-table \
  --table-name "TestTable2" \
  --attribute-definitions AttributeName=PK,AttributeType=S \
  --key-schema AttributeName=PK,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --profile "$PROFILE_NAME"
```

---

### Case 12 — 조건부 쓰기만 허용 (ConditionExpression 강제 패턴 설명)

**시나리오**: 항목이 이미 존재할 때만 업데이트를 허용하고, 존재하지 않는 항목에 대한 맹목적 쓰기(blind write)를 막고 싶다.

**중요한 사실**: IAM으로 `ConditionExpression` 자체를 강제하는 것은 불가능하다. DynamoDB IAM 조건 키 중에 "요청에 ConditionExpression이 있는지" 확인하는 키가 없다. 이건 IAM의 한계다.

**정책 JSON (설계 보완 패턴)**:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowUpdateItemOwnRowsOnly",
      "Effect": "Allow",
      "Action": ["dynamodb:UpdateItem"],
      "Resource": "arn:aws:dynamodb:AWS_REGION:ACCOUNT_ID:table/TABLE_NAME",
      "Condition": {
        "ForAllValues:StringEquals": {
          "dynamodb:LeadingKeys": ["${aws:username}"]
        },
        "StringEquals": {
          "dynamodb:ReturnValues": ["NONE", "UPDATED_NEW", "UPDATED_OLD"]
        }
      }
    },
    {
      "Sid": "AllowReadOwnItems",
      "Effect": "Allow",
      "Action": ["dynamodb:GetItem", "dynamodb:Query"],
      "Resource": "arn:aws:dynamodb:AWS_REGION:ACCOUNT_ID:table/TABLE_NAME",
      "Condition": {
        "ForAllValues:StringEquals": {
          "dynamodb:LeadingKeys": ["${aws:username}"]
        }
      }
    },
    {
      "Sid": "DenyPutItemToPreventBlindOverwrite",
      "Effect": "Deny",
      "Action": "dynamodb:PutItem",
      "Resource": "arn:aws:dynamodb:AWS_REGION:ACCOUNT_ID:table/TABLE_NAME"
    },
    {
      "Sid": "DenyDeleteItemToPreventUnconditionalDelete",
      "Effect": "Deny",
      "Action": "dynamodb:DeleteItem",
      "Resource": "arn:aws:dynamodb:AWS_REGION:ACCOUNT_ID:table/TABLE_NAME"
    }
  ]
}
```

**왜 이렇게 써야 하는가**: `PutItem`은 항목 전체를 덮어쓴다. 존재 여부와 무관하게 새 항목을 만들거나 기존 항목을 교체한다. `PutItem`을 Deny하고 `UpdateItem`만 허용하면 이미 존재하는 항목만 수정 가능하다. `UpdateItem`은 항목이 없으면 기본적으로 새 항목을 만들지만, 애플리케이션 레이어에서 `ConditionExpression: "attribute_exists(PK)"`를 강제하면 존재하는 항목만 업데이트된다.

**IAM으로 해결 안 되는 부분과 대안**:

| 요구사항 | IAM 가능 여부 | 대안 |
|---|---|---|
| ConditionExpression 강제 | 불가 | Lambda authorizer, 애플리케이션 레이어 |
| PutItem 차단 | 가능 | Deny Statement |
| 존재하는 항목만 업데이트 | 부분 가능 | UpdateItem만 허용 + 앱 레이어 조건 |
| 특정 속성 값 범위 제한 | 불가 | DynamoDB Streams + Lambda 검증 |

**이거 빠뜨리면?**:
- `UpdateItem`만 허용해도 `ConditionExpression` 없이 호출하면 항목이 없을 때 새로 생성된다. IAM만으로는 이걸 막을 수 없다.
- `ReturnValues: ALL_OLD`를 허용하면 업데이트 전 전체 항목이 응답에 포함된다. 열 수준 제한이 있다면 `ReturnValues`도 제한해야 한다.

**CloudShell 검증**:

```bash
# UpdateItem (항목 존재 시) — 성공 기대
aws dynamodb update-item \
  --table-name "$TABLE_NAME" \
  --key "{\"UserId\":{\"S\":\"$PROFILE_NAME\"}}" \
  --update-expression "SET Score = :s" \
  --condition-expression "attribute_exists(UserId)" \
  --expression-attribute-values '{":s":{"N":"100"}}' \
  --profile "$PROFILE_NAME"

# PutItem — AccessDenied 기대
aws dynamodb put-item \
  --table-name "$TABLE_NAME" \
  --item "{\"UserId\":{\"S\":\"$PROFILE_NAME\"}, \"Score\":{\"N\":\"100\"}}" \
  --profile "$PROFILE_NAME"
```

---

## 감점 방지 최종 체크리스트

시험 제출 전 아래를 순서대로 확인한다.

1. `LeadingKeys` 조건에 `ForAllValues:` 접두사가 있는가
2. `Attributes` 제한 시 `dynamodb:Select: SPECIFIC_ATTRIBUTES` 조건이 함께 있는가
3. `Attributes` 목록에 기본 키 속성(파티션 키, 정렬 키)이 포함되어 있는가
4. `Scan`이 Action 목록에서 빠져 있거나 Explicit Deny로 막혀 있는가
5. GSI/LSI 쿼리가 필요하면 인덱스 ARN이 Resource에 있는가
6. Stream 작업은 Stream ARN(`table/TABLE_NAME/stream/*`)에 부여했는가
7. ABAC 정책이라면 계정 ABAC 활성화 여부를 확인했는가
8. 태그 강제 정책에서 `aws:RequestTag`와 `aws:ResourceTag`를 혼동하지 않았는가
9. `ReturnValues` 제한이 필요한 경우 `dynamodb:ReturnValues` 조건을 추가했는가
10. CloudShell 검증에서 Allow 케이스와 Deny 케이스를 모두 실행했는가
