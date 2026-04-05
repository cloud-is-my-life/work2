# DynamoDB Fine-grained IAM 실전 케이스

## 핵심 요약

> **⚠️ `LeadingKeys`는 반드시 `ForAllValues:` 연산자와 함께** — 단일 항목 작업에도 복수형 키 이름 사용.

> **⚠️ `Scan`은 `LeadingKeys`를 우회** — 행 수준 제어 시 Action 목록에서 제외하거나 Explicit Deny.

> **⚠️ `Attributes` 제한 시 `Select: SPECIFIC_ATTRIBUTES` 강제 필수** — 없으면 전체 속성 반환.

> **⚠️ 인덱스 쿼리는 테이블 ARN만으로 부족** — `table/TABLE/index/*` ARN 별도 추가 필수.

> **⚠️ DynamoDB ABAC는 계정별 활성화 필요** — Console → Settings → Attribute-based access control.

---

## 전용 Condition Key 전체 목록

| Condition Key | 타입 | 설명 |
|---|---|---|
| `dynamodb:LeadingKeys` | ArrayOfString | 파티션 키 값 필터 (행 수준) |
| `dynamodb:Attributes` | ArrayOfString | 접근 가능 속성 목록 (열 수준) |
| `dynamodb:Select` | String | Query/Scan의 Select 파라미터 제어 |
| `dynamodb:ReturnValues` | String | 쓰기 작업의 ReturnValues 제어 |
| `dynamodb:ReturnConsumedCapacity` | String | 용량 소비 정보 반환 제어 |
| `dynamodb:EnclosingOperation` | String | 트랜잭션 vs 비트랜잭션 구분 |
| `dynamodb:FullTableScan` | Bool | PartiQL 전체 테이블 스캔 차단 |
| `aws:ResourceTag/${TagKey}` | String | 리소스 태그 기반 접근 제어 |
| `aws:RequestTag/${TagKey}` | String | 요청 태그 기반 접근 제어 |
| `aws:TagKeys` | ArrayOfString | 태그 키 기반 접근 제어 |

---

## ARN 패턴

```
# 테이블
arn:aws:dynamodb:REGION:ACCOUNT_ID:table/TABLE_NAME

# GSI / LSI
arn:aws:dynamodb:REGION:ACCOUNT_ID:table/TABLE_NAME/index/INDEX_NAME
arn:aws:dynamodb:REGION:ACCOUNT_ID:table/TABLE_NAME/index/*

# Streams
arn:aws:dynamodb:REGION:ACCOUNT_ID:table/TABLE_NAME/stream/*
```

---

## 정책 파일

| 케이스 | 파일 | 의도 |
|---|---|---|
| Case 01 | `policies/case01-leadingkeys-own-items.json` | 사용자별 파티션 키(행 수준) 제한 |
| Case 02 | `policies/case02-attributes-column-level.json` | 열 수준 제한 + Select 강제 |
| Case 03 | `policies/case03-deny-scan-delete-table.json` | Scan/DeleteTable 파괴 방지 |
| Case 04 | `policies/case04-abac-resource-tag.json` | 태그 기반 팀 단위 접근 |
| Case 05 | `policies/case05-index-query-only.json` | GSI 쿼리 전용 + Projected 속성만 |
| Case 06 | `policies/case06-deny-partiql-fullscan.json` | PartiQL 전체 스캔 차단 |

---

## 케이스별 상세 설명

### Case 01 — LeadingKeys 행 수준 제한

**시나리오**: 멀티테넌트 테이블에서 사용자가 자기 파티션 키(`UserId = ${aws:username}`)에 해당하는 항목만 CRUD 가능.

**핵심 메커니즘**:
- `dynamodb:LeadingKeys` + `ForAllValues:StringEquals` 조합
- `${aws:username}` 정책 변수로 IAM 사용자명과 파티션 키 값을 동적 매칭

**허용**: `Query`/`GetItem`/`PutItem`/`UpdateItem`/`DeleteItem` — 자기 파티션 키 항목만
**거부**: 다른 사용자의 파티션 키 항목 접근 시 `AccessDenied`

**주의사항**:
- `ForAllValues:` 접두사 누락 시 정책이 무효화됨 (조건 무시 → 전체 허용)
- `Scan`은 `LeadingKeys`를 우회하므로 Action 목록에서 반드시 제외
- `BatchWriteItem`/`BatchGetItem`도 `LeadingKeys` 적용 대상이지만, 배치 내 모든 키가 조건을 만족해야 함

---

### Case 02 — Attributes 열 수준 제한

**시나리오**: 특정 속성(컬럼)만 읽기/쓰기 허용. 예: `UserId`, `Name`, `Email`만 접근 가능하고 `SSN`, `Salary` 등 민감 속성은 차단.

**핵심 메커니즘**:
- `dynamodb:Attributes` + `ForAllValues:StringEquals` — 허용 속성 목록 지정
- `dynamodb:Select` + `StringEquals: "SPECIFIC_ATTRIBUTES"` — ProjectionExpression 강제

**허용**: 허용 속성만 포함한 `Query`/`GetItem` (ProjectionExpression 필수)
**거부**: `Select: ALL_ATTRIBUTES` 또는 허용 외 속성 포함 시 `AccessDenied`

**주의사항**:
- `Select` 조건 없이 `Attributes`만 걸면, 클라이언트가 `Select=ALL_ATTRIBUTES`로 전체 속성 반환 가능 → 반드시 함께 사용
- 기본 키 속성(`UserId` 등)도 `Attributes` 목록에 포함해야 함 — 빠뜨리면 키 조회 자체가 실패
- `PutItem`/`DeleteItem`은 전체 아이템 교체/삭제이므로 `Attributes` 제한이 의미 없음 → Action에서 제외 권장
- `ReturnValues: ALL_OLD`/`ALL_NEW` 허용 시 제한된 속성도 응답에 포함됨 → `dynamodb:ReturnValues` 조건 추가 고려

---

### Case 03 — Scan/DeleteTable 파괴 방지

**시나리오**: 개발자에게 테이블 CRUD는 허용하되, `Scan`(전체 읽기)과 `DeleteTable`(테이블 삭제)은 Explicit Deny로 차단.

**핵심 메커니즘**:
- Allow Statement: `Query`, `GetItem`, `PutItem`, `UpdateItem`, `DeleteItem` 허용
- Deny Statement: `dynamodb:Scan`, `dynamodb:DeleteTable` 명시적 거부

**허용**: 개별 항목 CRUD + `Query`
**거부**: `Scan` 시도 → `AccessDenied`, `DeleteTable` 시도 → `AccessDenied`

**주의사항**:
- `Scan`만 Deny하고 `PartiQL ExecuteStatement`를 허용하면 `SELECT * FROM table` 우회 가능 → Case 06과 병행 권장
- `BatchWriteItem`으로 대량 삭제는 가능 — 이것도 차단하려면 별도 Deny 필요
- `DescribeTable`은 메타데이터만 반환하므로 보통 허용

---

### Case 04 — ABAC 태그 기반 팀 단위 접근

**시나리오**: 테이블에 `Team` 태그가 있고, IAM 사용자의 `PrincipalTag/Team` 값과 일치하는 테이블만 접근 허용.

**핵심 메커니즘**:
- `aws:ResourceTag/Team` + `StringEquals` + `${aws:PrincipalTag/Team}` 동적 매칭
- Deny Statement: `aws:PrincipalTag/Team`이 `Null`이면 모든 DynamoDB 작업 거부

**허용**: `PrincipalTag/Team = analytics`인 사용자 → `ResourceTag/Team = analytics`인 테이블만
**거부**: 태그 불일치 또는 태그 미설정 시 `AccessDenied`

**주의사항**:
- DynamoDB ABAC는 **계정별 활성화 필요** — Console → DynamoDB → Settings → Attribute-based access control
- 활성화 안 하면 `ResourceTag` 조건이 무시되어 전체 허용/거부 예상과 다르게 동작
- `ListTables`는 태그 조건 적용 불가 → `Resource: "*"` 별도 Statement 필요
- 테이블 생성 시 태그 강제는 `aws:RequestTag/Team` + `Null` 조건으로 별도 구현

---

### Case 05 — GSI 쿼리 전용

**시나리오**: 특정 GSI(Global Secondary Index)에 대한 `Query`만 허용. 테이블 직접 접근은 차단.

**핵심 메커니즘**:
- Resource에 인덱스 ARN만 지정: `arn:aws:dynamodb:REGION:ACCOUNT:table/TABLE/index/INDEX_NAME`
- Action: `dynamodb:Query`만 허용
- `dynamodb:Attributes` 조건으로 Projected 속성만 접근 가능하도록 추가 제한

**허용**: 지정 GSI에 대한 `Query` (Projected 속성만)
**거부**: 테이블 직접 `Query`/`GetItem`, 다른 인덱스 접근, `Scan`

**주의사항**:
- 인덱스 ARN을 빠뜨리고 테이블 ARN만 넣으면 인덱스 쿼리가 `AccessDenied`
- 반대로 인덱스 ARN만 넣으면 테이블 직접 접근은 자동 차단
- GSI의 Projected 속성 외 속성을 요청하면 DynamoDB 자체가 오류 반환 (IAM 이전 단계)
- `index/*` 와일드카드는 모든 인덱스 허용 — 특정 인덱스만 허용하려면 정확한 이름 지정

---

### Case 06 — PartiQL 전체 스캔 차단

**시나리오**: PartiQL `SELECT * FROM table` 같은 전체 테이블 스캔을 차단. `WHERE` 절로 키 조건 지정한 쿼리만 허용.

**핵심 메커니즘**:
- `dynamodb:FullTableScan` + `Bool: "true"` → Deny
- PartiQL `ExecuteStatement`/`BatchExecuteStatement` Action에 적용

**허용**: `SELECT * FROM table WHERE pk = 'value'` (키 조건 포함)
**거부**: `SELECT * FROM table` (전체 스캔) → `AccessDenied`

**주의사항**:
- `dynamodb:FullTableScan`은 PartiQL 전용 — 일반 `Scan` API에는 적용 안 됨 (별도 Deny 필요)
- `BatchExecuteStatement`도 함께 Deny해야 배치 PartiQL 우회 차단
- `FullTableScan` 조건은 DynamoDB가 실행 계획을 분석한 결과 기반 — `WHERE` 절이 있어도 키 조건이 아니면 full scan으로 판정될 수 있음

---

## CloudShell 준비

```bash
export AWS_REGION="ap-northeast-2"
export ACCOUNT_ID="123456789012"
export TABLE_NAME="MOD3_DDB_TABLE"
export USER_NAME="mod3-ddb-user"
export PROFILE_NAME="mod3-ddb-user"
```

---

## 검증 예시

```bash
# 자신의 파티션 키 조회 — 성공 기대
aws dynamodb query \
  --table-name "$TABLE_NAME" \
  --key-condition-expression "UserId = :uid" \
  --expression-attribute-values '{":uid":{"S":"user-a"}}' \
  --profile "$PROFILE_NAME"

# 다른 사용자 파티션 키 조회 — AccessDenied 기대
aws dynamodb query \
  --table-name "$TABLE_NAME" \
  --key-condition-expression "UserId = :uid" \
  --expression-attribute-values '{":uid":{"S":"user-b"}}' \
  --profile "$PROFILE_NAME"

# Scan 시도 — AccessDenied 기대 (Deny 정책 적용 시)
aws dynamodb scan \
  --table-name "$TABLE_NAME" \
  --profile "$PROFILE_NAME"
```

---

## 감점 방지 포인트

- `LeadingKeys`에 `ForAllValues:` 빠뜨리면 정책 무효
- `Attributes` 제한 시 **기본 키 속성도 목록에 포함**해야 함
- `PutItem`/`DeleteItem`은 전체 아이템 교체이므로 `Attributes` 제한 정책에서 **제외**
- `ReturnValues`를 `ALL_OLD`/`ALL_NEW`로 허용하면 제한된 속성도 노출됨
- 인덱스 ARN 누락 시 GSI/LSI 쿼리 전부 실패
- ABAC 비활성화 상태에서 태그 조건 정책은 동작하지 않음
