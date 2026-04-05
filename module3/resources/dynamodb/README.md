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
