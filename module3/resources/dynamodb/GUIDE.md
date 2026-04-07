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

