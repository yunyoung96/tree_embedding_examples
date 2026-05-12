# main_branch.py 함수 호출 구조 및 논문 알고리즘 대응표

이 문서는 `main_branch.py`의 주요 함수 호출 흐름(Call Stack)과, 각 코드가 논문의 어떤 알고리즘 부분에 대응되는지 설명합니다.

---

## 1. 전체 실행 흐름 (Call Stack)

### (1) main() 함수
- 타임스탬프 생성, q 값 반복
- 각 q에 대해 `run_branch_analysis()`를 random/ast 데이터셋에 대해 호출

### (2) run_branch_analysis(dataset_type, ...)
- 트리 데이터 생성/로드 (`random_tree`, `load_trees_from_json`)
- **핵심:** `run_binary_branch_distance_experiment()` 호출 → 실험 수행
- 결과로 lower bound 검사(`check_lower_bound_violations`), 그래프 저장(`save_branch_distance_comparison`)

### (3) run_binary_branch_distance_experiment(trees, q)
- 논문 알고리즘의 핵심 구현
    - 모든 트리 쌍에 대해:
        - **Edit Distance 계산**: `compute_edit_distance`
        - **Binary Branch Distance 계산**: `precompute_branch_vectors`, `compute_branch_distance_from_vectors`
    - 결과 통계(상관계수 등) 계산

### (4) check_lower_bound_violations(result)
- 논문 Theorem 3.1/3.2/3.3의 Lower Bound 조건(BDist ≥ ED) 위반 여부 검사

### (5) save_branch_distance_comparison(result, ...)
- 실험 결과 시각화 및 저장

---

## 2. 논문 알고리즘 ↔ 코드 매핑

| 논문 알고리즘/정리 | 코드 함수명/위치 |
|-------------------|-----------------|
| 트리 쌍 Edit Distance 계산 | `compute_edit_distance` (tree_utils.py) |
| Branch Vector 계산 (q-level) | `precompute_branch_vectors` (tree_utils.py) |
| Binary Branch Distance 계산 | `compute_branch_distance_from_vectors` (tree_utils.py) |
| Lower Bound (Theorem 3.1/3.2/3.3) | `check_lower_bound_violations` (algorithms.py) |
| 실험 전체 파이프라인 | `run_binary_branch_distance_experiment` (algorithms.py) |
| 결과 시각화 | `save_branch_distance_comparison` (main_branch.py) |

---

## 3. 요약
- **실험 전체 흐름**: main() → run_branch_analysis() → run_binary_branch_distance_experiment() → (거리 계산, 통계, lower bound 검사, 시각화)
- **논문 알고리즘**은 대부분 `algorithms.py`, `tree_utils.py`에 구현되어 있으며, `main_branch.py`는 실험 파이프라인과 입출력/시각화 역할을 담당합니다.

---

## 4. q-level Binary Branch 구조 계산 상세 (extract_q_level_binary_branches)

### 논문 Definition 5 (q-level binary branch)
- **코드 위치:** `extract_q_level_binary_branches` (tree_utils.py)
- **역할:**
    - 정규화된 full binary tree에서, 각 노드를 루트로 하는 높이 (q-1)인 완전 이진 부분트리(=q-level branch)를 모두 추출
    - ε(패딩) 노드는 제외하고, 실제 라벨이 있는 노드만 branch로 카운트
    - 각 branch는 문자열로 표현 (예: `A(B,.)`, `B(C,D)` 등)

### 계산 과정 상세
1. **이진 트리 변환 및 정규화**
    - 일반 트리를 left-child/right-sibling 방식의 이진 트리로 변환 (`tree_to_binary_tree`)
    - 모든 노드가 2개의 자식을 갖도록 full binary tree로 정규화 (`normalize_binary_tree`)
2. **q-level branch 추출**
    - 트리의 모든 노드에 대해, 그 노드를 루트로 하는 높이 (q-1)인 완전 이진 부분트리를 추출
    - 부분트리는 `extract_perfect_subtree`로 문자열화
    - 예: q=2면, 각 노드와 그 자식(들)의 구조를 모두 branch로 추출
3. **빈도 벡터화**
    - 추출된 branch 구조 리스트를 Counter로 변환해 벡터화 (`precompute_branch_vectors`)
4. **거리 계산**
    - 두 트리의 branch 벡터 차이의 L1 distance를 계산 (`compute_branch_distance_from_vectors`)
    - 정규화 계수(4(q-1)+1)로 나누어 논문 lower bound에 맞춤

### 예시 (q=2)
- 트리: (A, [(B, []), (C, [])])
- 이진 변환: (A, (B, ε, ε), (C, ε, ε))
- 추출 branch: 'A(B,C)', 'B(.,.)', 'C(.,.)' 등

### 코드 흐름
- `run_binary_branch_distance_experiment` (algorithms.py)
    → `precompute_branch_vectors` (tree_utils.py)
        → `extract_q_level_binary_branches` (tree_utils.py)
            → `extract_perfect_subtree` (tree_utils.py)

---

> 이 구조 덕분에, 논문에서 정의한 q-level binary branch 기반 거리 계산이 코드에서 체계적으로 구현됩니다. 각 단계별 함수와 역할을 위 표에서 확인하세요.
