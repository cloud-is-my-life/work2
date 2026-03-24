
# [예시 과제 6] EKS + EFS 통합 (난이도: ★★★★)

## 시나리오

컨테이너 기반 마이크로서비스 아키텍처에서 여러 Pod가 공유 파일 시스템에 접근해야 합니다.
EFS CSI Driver를 활용하여 EKS 클러스터에서 EFS를 PersistentVolume으로 사용하시오.

---

## 요구사항

### [A] 네트워크

- `wsi-eks-vpc` (10.200.0.0/16) 생성
- 퍼블릭 서브넷 2개 + 프라이빗 서브넷 2개 (EKS 요구사항)
- 서브넷 태그: `kubernetes.io/role/elb`, `kubernetes.io/role/internal-elb`

### [B] EKS 클러스터

- `wsi-cluster` 생성
- 노드 그룹: t3.medium, 2노드 (2AZ 분산)
- `aws-efs-csi-driver` 애드온 설치

### [C] EFS

- `wsi-eks-efs` 생성 (암호화, elastic throughput)
- Mount Target: 프라이빗 서브넷 2개에 구성
- SG: 노드 그룹 SG에서 NFS 2049 허용

### [D] Static Provisioning

- PersistentVolume `efs-pv-static`:
  - 기존 EFS 파일 시스템 직접 참조
  - accessMode: ReadWriteMany
  - volumeHandle: `{fs-id}`
- PersistentVolumeClaim `efs-pvc-static`
- 테스트 Pod: `/data`에 마운트, 파일 생성 확인

### [E] Dynamic Provisioning (Access Point 기반)

- StorageClass `efs-sc`:
  - provisioner: `efs.csi.aws.com`
  - provisioningMode: `efs-ap`
  - fileSystemId: `{fs-id}`
  - directoryPerms: `700`
  - basePath: `/dynamic`
- PersistentVolumeClaim `efs-pvc-dynamic`
- 테스트 Pod: `/data`에 마운트, 파일 생성 확인
- Access Point가 자동 생성되었는지 확인

### [F] 검증

- Static PV Pod에서 파일 생성 → 다른 노드의 Pod에서 조회
- Dynamic PV Pod에서 파일 생성 → Access Point 자동 생성 확인
- `kubectl get pv,pvc` 출력으로 Bound 상태 확인

---

## 채점 기준

| 항목 | 배점 |
|------|------|
| VPC + 서브넷 구성 (EKS 요구사항 충족) | 2점 |
| EKS 클러스터 생성 | 3점 |
| EFS CSI Driver 설치 | 2점 |
| EFS 생성 + 암호화 | 2점 |
| Mount Target (프라이빗 서브넷) | 2점 |
| SG 구성 (노드 → EFS NFS) | 2점 |
| Static PV + PVC 구성 | 3점 |
| Static Pod 마운트 + 파일 공유 | 3점 |
| StorageClass 구성 (Dynamic) | 3점 |
| Dynamic PVC → AP 자동 생성 | 3점 |
| Dynamic Pod 마운트 + 파일 확인 | 2점 |
| PV/PVC Bound 상태 확인 | 1점 |
| **합계** | **28점** |

---

## 참고: Kubernetes 매니페스트 예시

### StorageClass (Dynamic)
```yaml
kind: StorageClass
apiVersion: storage.k8s.io/v1
metadata:
  name: efs-sc
provisioner: efs.csi.aws.com
parameters:
  provisioningMode: efs-ap
  fileSystemId: fs-XXXXX
  directoryPerms: "700"
  basePath: "/dynamic"
```

### PersistentVolume (Static)
```yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: efs-pv-static
spec:
  capacity:
    storage: 5Gi
  volumeMode: Filesystem
  accessModes:
    - ReadWriteMany
  persistentVolumeReclaimPolicy: Retain
  csi:
iver: efs.csi.aws.com
    volumeHandle: fs-XXXXX
```

### PersistentVolume (Static + Access Point)
```yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: efs-pv-ap
spec:
  capacity:
    storage: 5Gi
  volumeMode: Filesystem
  accessModes:
    - ReadWriteMany
  persistentVolumeReclaimPolicy: Retain
  csi:
    driver: efs.csi.aws.com
    volumeHandle: fs-XXXXX::fsap-XXXXX
```

### PersistentVolumeClaim
```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: efs-pvc
spec:
  accessModes:
    - ReadWriteMany
  storageClassName: efs-sc
  resources:
    requests:
      storage: 5Gi
```

### Test Pod
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: efs-test-pod
spec:
  containers:
    - name: app
      image: amazonlinux:2023
      command: ["/bin/sh", "-c", "echo 'hello from pod' > /data/test.txt && sleep 3600"]
      volumeMounts:
        - name: efs-volume
          mountPath: /data
  volumes:
    - name: efs-volume
      persistentVolumeClaim:
        claimName: efs-pvc
```
