# Module 1: Shared Network Storage — EFS

---

## 핵심 요약 (경기장에서 이것만 기억)

- `-o iam` = IAM Role 신분증 제시. Principal에 Role ARN 있으면 필수, `*`이면 불필요.
- 같은 계정 내에서 IAM Role Policy든 EFS File System Policy든 **둘 중 하나만 Allow면 접근 가능.** Deny는 무조건 우선.
- File System Policy 없으면 EFS는 **기본 전체 허용.** 정책 붙이는 순간 명시적 Allow 필요.
- ABAC은 **IAM Role 태그만 봄.** EC2 인스턴스 태그는 안 봄.
- Access Point: **PosixUser = 매번** 신분 강제, **CreationInfo = 딱 한 번** 디렉토리 생성 시만.
- mount = 즉시 마운트. fstab = 재부팅 자동 마운트. **둘 다 해야 함.**
- fstab에는 **`_netdev` 필수.** mount 명령에는 불필요.
- 암호화는 **생성 시 결정, 변경 불가.** Performance Mode도 변경 불가. Throughput Mode만 변경 가능.

---

## 목차

| # | 주제 | 바로가기 |
|---|------|----------|
| 1 | IAM Role, 인증 흐름, ABAC | [iam-guide.md](./iam-guide.md) |
| 2 | Access Point (PosixUser vs CreationInfo, 격리) | [access-point-guide.md](./access-point-guide.md) |
| 3 | CLI / 마운트 / fstab | [cheatsheet.md](./cheatsheet.md) |
| 4 | 트러블슈팅 + 디버깅 체크리스트 | [troubleshooting.md](./troubleshooting.md) |
| 5 | File System Policy JSON (8종 + 복합 3종) | [policies/](./policies/) |
| 6 | CloudFormation 올인원 템플릿 | [cfn-templates/](./cfn-templates/) |
| 7 | 예시 과제 6종 (난이도별) | [examples-questions/](./examples-questions/) |

---

## 빠른 레퍼런스 (외우기 어려운 것만)

### EFS 액션

| 액션 | 설명 |
|------|------|
| elasticfilesystem:ClientMount | 읽기 전용 마운트 |
| elasticfilesystem:ClientWrite | 쓰기 (ClientMount 필요) |
| elasticfilesystem:ClientRootAccess | 루트 접근. 거부 시 root squashing |

### Condition Key

| 키 | 타입 |
|----|------|
| elasticfilesystem:AccessedViaMountTarget | Bool |
| elasticfilesystem:AccessPointArn | ARN |
| aws:SecureTransport | Bool |
| aws:SourceIp | IpAddress |
| aws:PrincipalTag/${TagKey} | String |
| aws:CurrentTime | Date |

### Condition Operator

| 연산자 | 용도 |
|--------|------|
| Bool | SecureTransport, AccessedViaMountTarget |
| StringEquals / StringNotEquals | PrincipalTag 정확 매칭 |
| StringLike / StringNotLike | 와일드카드 (*, ?) |
| ArnEquals / ArnLike | AccessPointArn |
| IpAddress / NotIpAddress | SourceIp |
| DateGreaterThan / DateLessThan | CurrentTime |

### 라이프사이클 전환 값

| 정책 | 허용 값 |
|------|---------|
| TransitionToIA | AFTER_1_DAY ~ AFTER_365_DAYS |
| TransitionToArchive | AFTER_1_DAY ~ AFTER_365_DAYS |
| TransitionToPrimaryStorageClass | AFTER_1_ACCESS |

CFn에서 각 정책은 배열 내 별도 객체:
```yaml
LifecyclePolicies:
  - TransitionToIA: AFTER_30_DAYS
  - TransitionToArchive: AFTER_90_DAYS
  - TransitionToPrimaryStorageClass: AFTER_1_ACCESS
```
