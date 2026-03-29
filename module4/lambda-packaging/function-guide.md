# 함수 배포 가이드 — 콘솔에서 Lambda 코드 올리기

---

## 방법 1: 인라인 편집 (코드가 짧을 때)

Lambda 콘솔에서 직접 코드를 입력할 수 있다. 파일이 1개이고 짧을 때 가장 빠름.

1. Lambda 함수 → **코드** 탭
2. 우측 `lambda_function.py` 클릭 → 코드 붙여넣기
3. **Deploy** 버튼 클릭

> 단, 의존성(pymysql 등)이 있는 경우 Layer를 먼저 연결해야 함.

---

## 방법 2: zip 업로드 (파일이 여러 개일 때)

```bash
# lambda_function.py 하나만 올릴 때
zip function.zip lambda_function.py

# 여러 파일을 올릴 때 (utils.py 등 포함)
zip function.zip lambda_function.py utils.py config.py
```

1. Lambda 함수 → **코드** 탭 → **업로드 위치** → `.zip 파일`
2. `function.zip` 선택 → **저장**

> **주의**: `python/` 디렉토리 없이 `.py` 파일이 zip 최상위에 있어야 함.
> Layer와 달리 함수 코드 zip은 `python/` 감싸지 않음.

---

## 함수 생성 시 콘솔 설정 체크리스트

### 기본 설정 (함수 생성 화면)

| 항목 | 설정값 |
|------|--------|
| 함수 이름 | 원하는 이름 (예: `my-api-function`) |
| 런타임 | `Python 3.11` |
| 실행 역할 | 기존 역할 사용 또는 새 역할 생성 |

### 생성 후 — 구성 탭에서 추가 설정

**일반 구성:**
| 항목 | 설정값 |
|------|--------|
| 타임아웃 | 기본 3초 → 용도에 맞게 변경 (ETL: 300초, API: 30초) |
| 메모리 | 기본 128MB (ETL이면 256~512MB 권장) |

**환경변수:**
함수마다 필요한 환경변수를 여기에 입력.
```
DB_HOST   = mydb.xxxx.ap-northeast-2.rds.amazonaws.com
DB_USER   = admin
DB_PASS   = yourpassword
DB_NAME   = mydb
```

**VPC:**
| 항목 | 설정값 |
|------|--------|
| VPC | Lambda가 접근해야 할 RDS가 있는 VPC 선택 |
| 서브넷 | **Private Subnet** 선택 (Public 아님) |
| 보안 그룹 | Lambda용 SG 선택 (아웃바운드 3306 → RDS SG) |

**레이어:**
- 구성 → 레이어 → 레이어 추가 → ARN 지정 → pymysql-layer ARN 입력

---

## 핸들러 설정

콘솔 기본값이 `lambda_function.lambda_handler` 이므로,
파일 이름을 `lambda_function.py`, 함수 이름을 `lambda_handler` 로 맞추면 변경할 필요 없음.

```python
# lambda_function.py
def lambda_handler(event, context):
    ...
```

---

## 배포 후 테스트

1. 함수 페이지 → **테스트** 탭
2. 테스트 이벤트 JSON 입력 후 **테스트** 버튼
3. 실행 결과 및 로그 확인

**CloudWatch Logs 바로 가기:**
함수 → **모니터링** 탭 → **CloudWatch Logs 보기**
