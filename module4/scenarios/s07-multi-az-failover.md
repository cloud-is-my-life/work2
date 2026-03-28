# 시나리오 7: Multi-AZ RDS + Lambda Failover

> 출제 가능성: **중간** | 난이도: **중상**

---

## 아키텍처 구성

```
Lambda Function
  [VPC: Private Subnet, 여러 AZ]
  |
  | DNS 조회 (항상 엔드포인트 hostname 사용)
  v
RDS Endpoint (DNS)
  mydb.xxxx.ap-northeast-2.rds.amazonaws.com
  |
  |--- 정상 시 -------> Primary (AZ-a)
  |
  |--- 장애 조치 후 --> Standby → Primary (AZ-b) [60-120초 소요]
  v
RDS MySQL Multi-AZ
  [Primary: AZ-a, Standby: AZ-b]
```

---

## 출제 의도

- RDS Multi-AZ 장애 조치 메커니즘 이해도 측정
- Lambda에서 DB 연결 재시도 로직 구현 능력 평가
- DNS 캐싱 문제와 해결 방법 이해

---

## 왜 현실적인 문제인가

- 고가용성은 프로덕션 필수 요건
- Lambda의 컨테이너 재사용 특성과 DB 연결 관리의 충돌 이해 필요
- 장애 조치 시나리오는 실무 운영 능력을 직접 평가

---

## 참가자가 자주 틀리는 포인트

1. **DNS 캐싱으로 인한 연결 실패** — Lambda 컨테이너는 DNS 조회 결과를 캐싱함. 장애 조치 후 RDS DNS가 새 Primary를 가리켜도 Lambda는 이전 IP로 연결 시도. 해결책: 항상 hostname을 사용하고 연결 실패 시 새 연결 생성.

2. **IP 주소 하드코딩** — RDS 엔드포인트 IP를 직접 사용하면 장애 조치 후 연결 불가. 반드시 DNS 엔드포인트 hostname 사용.

3. **연결 재시도 로직 없음** — 장애 조치 중(60-120초) Lambda 호출이 실패할 수 있음. `ping(reconnect=True)` 또는 try/except로 재연결 로직 필수.

4. **모듈 레벨 커넥션만 사용** — 컨테이너 재사용 시 이전 커넥션이 끊어진 상태일 수 있음. `conn.open` 체크 또는 `ping()` 으로 연결 상태 확인 후 재연결.

5. **Multi-AZ와 Read Replica 혼동** — Multi-AZ Standby는 읽기 트래픽을 받지 않음. 읽기 분산은 Read Replica 사용. Multi-AZ 장애 조치 시 Standby가 Primary로 승격.

---

## 디버깅 포인트

**RDS Multi-AZ 상태 확인:**
```bash
aws rds describe-db-instances --db-instance-identifier my-db \
  --query "DBInstances[0].{MultiAZ:MultiAZ,Status:DBInstanceStatus,AZ:AvailabilityZone,SecondaryAZ:SecondaryAvailabilityZone}"
```

**장애 조치 테스트 (주의: 실제 장애 조치 발생):**
```bash
aws rds reboot-db-instance \
  --db-instance-identifier my-db \
  --force-failover
```

**RDS 이벤트 확인:**
```bash
aws rds describe-events \
  --source-identifier my-db \
  --source-type db-instance \
  --duration 60
```

**CloudWatch Logs 패턴:**
- `Lost connection to MySQL server` → 장애 조치 중 연결 끊김
- `Can't connect to MySQL server` → DNS 캐싱 또는 재연결 실패
- 재연결 성공 후 정상 처리 → 재시도 로직 동작 확인

---

## 풀이 우선순위

1. **(5분) RDS Multi-AZ 활성화 확인** — 콘솔 또는 CLI로 Multi-AZ 상태 확인
2. **(5분) Lambda 함수 생성** — VPC 설정, 환경변수 (DB_HOST에 DNS hostname 사용)
3. **(15분) 재연결 로직 구현** — `ping(reconnect=True)`, 지수 백오프, 재시도
4. **(5분) 정상 동작 테스트** — Lambda 실행 확인
5. **(10분) 장애 조치 테스트** — `force-failover` 후 Lambda 재실행, 재연결 확인

→ 참고 코드: `code-templates/conn-failover.py`
