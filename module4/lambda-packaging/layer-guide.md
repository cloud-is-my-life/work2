# Layer 패키징 가이드 — pymysql Layer 만들기

> pymysql은 Lambda 기본 런타임에 없으므로 Layer로 따로 올려야 한다.

---

## 1. 로컬에서 zip 만들기

터미널(Mac/Linux 기준):

```bash
# 1. python/ 디렉토리 생성 (이 이름이 정확해야 Lambda가 인식)
mkdir python

# 2. pymysql을 python/ 안에 설치
pip install pymysql -t python/

# 3. zip 압축 — python/ 디렉토리가 zip 최상위에 있어야 함
zip -r pymysql-layer.zip python/
```

**zip 내부 구조 확인 (중요):**

```
pymysql-layer.zip
└── python/              ← 반드시 이 이름
    ├── pymysql/
    │   ├── __init__.py
    │   └── ...
    └── PyMySQL-1.1.1.dist-info/
```

`python/` 없이 `pymysql/` 이 바로 최상위에 있으면 Lambda가 인식 못 함.

---

## 2. 콘솔에서 Layer 생성

1. AWS Console → **Lambda** → 좌측 메뉴 **Layers** → **레이어 생성**

2. 설정:
   | 항목 | 값 |
   |------|-----|
   | 이름 | `pymysql-layer` |
   | 업로드 방식 | `.zip 파일 업로드` |
   | 파일 | `pymysql-layer.zip` 선택 |
   | 호환 런타임 | `Python 3.11`, `Python 3.12` 체크 |

3. **생성** 클릭

4. 생성 후 화면에 표시되는 **ARN 복사** — 함수에 연결할 때 사용

---

## 3. Lambda 함수에 Layer 연결

1. Lambda 함수 → **구성** 탭 → **레이어** → **레이어 추가**
2. **ARN 지정** 선택
3. 위에서 복사한 ARN 붙여넣기 → **추가**

---

## 자주 발생하는 오류

| 오류 | 원인 | 해결 |
|------|------|------|
| `No module named 'pymysql'` | zip 구조가 `python/` 없음 | `zip -r layer.zip python/` 확인 |
| `No module named 'pymysql'` | 함수에 Layer 미연결 | 함수 > 구성 > 레이어 확인 |
| `No module named 'pymysql'` | 런타임 불일치 | Layer 호환 런타임 ↔ 함수 런타임 일치 확인 |
| 파일 크기 초과 | 불필요한 패키지 포함 | `pip install pymysql` 만 설치 |
