# Module 2 채점 대응 플레이북 (CloudShell 기준)

---

## 0) 전제 (이 저장소 기준)

- Module 2는 **CloudShell + AWS CLI 중심**으로 채점된다고 가정한다.
- 필요 시 AWS Management Console 확인이 가능하더라도, 채점 중에는 **인프라 변경 액션**(새 리소스 생성, 새 쿼리 작성 등)을 지양한다.
- 따라서 선수 입장에서는 “새로 만들기”보다 **이미 만든 결과를 재검증 가능하게 남기는 것**이 핵심이다.

---

## 1) 채점자가 실제로 확인하기 쉬운 증거

1. **Athena 실행 이력**: QueryExecutionId, 상태(SUCCEEDED), 실행 DB/WorkGroup
2. **S3 결과물**: Athena 결과 파일(output location), CTAS/UNLOAD 산출물
3. **Catalog 상태**: DB/Table/View 스키마와 LOCATION, 파티션 설정

> 핵심: Saved Query(= Named Query)는 “있으면 참고 가능”이지, **일반적으로 필수 증거는 아님**.

---

## 2) CloudShell 복붙 검증 템플릿

아래 값만 대문자 placeholder로 교체해서 사용:

```bash
export AWS_REGION="ap-northeast-2"
export WORKGROUP="primary"
export DATABASE="YOUR_DATABASE"
```

### (A) 최근 실행 쿼리 ID 확인

```bash
aws athena list-query-executions \
  --region "$AWS_REGION" \
  --work-group "$WORKGROUP" \
  --max-results 20 \
  --query 'QueryExecutionIds' \
  --output table
```

### (B) 특정 쿼리 1건 상세 확인

```bash
export QUERY_EXECUTION_ID="REPLACE_WITH_QUERY_EXECUTION_ID"

aws athena get-query-execution \
  --region "$AWS_REGION" \
  --query-execution-id "$QUERY_EXECUTION_ID" \
  --query 'QueryExecution.{State:Status.State,Database:QueryExecutionContext.Database,WorkGroup:WorkGroup,Output:ResultConfiguration.OutputLocation,Submitted:Status.SubmissionDateTime,Completed:Status.CompletionDateTime}' \
  --output table
```

### (C) 결과 레코드 샘플 확인

```bash
aws athena get-query-results \
  --region "$AWS_REGION" \
  --query-execution-id "$QUERY_EXECUTION_ID" \
  --max-results 20
```

### (D) DB/테이블 메타데이터 확인 (재현성 증거)

```bash
aws athena list-table-metadata \
  --region "$AWS_REGION" \
  --catalog-name AwsDataCatalog \
  --database-name "$DATABASE" \
  --max-results 50 \
  --query 'TableMetadataList[].{Name:Name,Type:TableType,Columns:length(Columns)}' \
  --output table
```

---

## 3) Console fallback (채점자가 UI로 볼 때)

- Athena Console → **Query history**: 실행 시간/상태/쿼리 문자열/출력 위치 확인
- Athena Console → **Data**: DB/테이블/컬럼/파티션 설정 확인
- S3 Console → 결과 버킷/CTAS 출력 prefix 존재 확인

> 원칙: Console은 “확인용”으로 쓰고, 채점 스크립트/CloudShell 결과와 모순 없이 맞아야 한다.

---

## 4) Saved Query(쿼리 저장) 정책 정리

### 기본 원칙
- Athena 실행 자체에 Saved Query는 **필수 아님**
- 실제 실행 증거는 QueryExecutionId + 상태 + OutputLocation으로 충분한 경우가 많음

### 예외 (필수로 봐야 하는 경우)
- 문제/루브릭에 아래가 명시된 경우:
  - “저장된 쿼리 생성”
  - “Named Query ID 제출”
  - “쿼리 저장 목록 확인”

> 결론: **문제 지시문에 저장 요구가 없으면 저장은 선택사항**. 지시문에 있으면 반드시 수행.

---

## 5) 금지/지양 액션 (감점/분쟁 방지)

- 채점 시점 이후 불필요한 리소스 생성/수정
- 채점 증거를 바꾸는 재실행(원문 지시 없는 추가 쿼리 작성 등)
- 멱등 검증을 깨는 수동 변경

---

## 6) 제출 직전 60초 체크리스트

- [ ] 주요 쿼리의 `QueryExecutionId`를 확보했다
- [ ] 주요 쿼리 상태가 `SUCCEEDED`다
- [ ] 결과 S3 위치(OutputLocation) 확인 가능하다
- [ ] 과제 산출 DB/테이블이 Catalog에 남아 있다
- [ ] 문제에서 Saved Query를 요구했는지 확인했다 (요구 시에만 생성)
- [ ] 재검증 명령(CloudShell)으로 같은 결과를 다시 확인할 수 있다

---

## 7) 실전 한 줄 전략

**“새로 만들지 말고, 이미 만든 걸 CloudShell에서 같은 명령으로 다시 증명한다.”**
