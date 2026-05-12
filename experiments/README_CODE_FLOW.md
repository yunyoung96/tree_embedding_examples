# Binary Branch Distance 코드 호출 흐름 (Code Flow)

## 📊 전체 아키텍처 개요

```
main_branch.py (진입점)
│
├─ main() 실행
│  │
│  ├─ [q=2, 3, 4] 루프
│  │  │
│  │  ├─ run_branch_analysis('random', q=q, ...)
│  │  │  └─ run_branch_analysis('ast', q=q, ...)
│  │
│  └─ 최종 완료 메시지 출력
│
└─ 그래프 저장 (branch_results/{timestamp}/)
```

---

## 🔄 상세 호출 흐름 (Detailed Call Stack)

### 1️⃣ **진입점: `main_branch.py::main()`**

```python
def main():
    # 타임스탬프 생성 (e.g., "2026-04-17_15-59-38")
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    
    # 각 q 값 (2, 3, 4)에 대해 순회
    for q in [2, 3, 4]:
        # RANDOM 트리 분석
        run_branch_analysis('random', q=q, timestamp=timestamp)
        
        # AST 트리 분석
        run_branch_analysis('ast', q=q, timestamp=timestamp)
```

**호출 대상**: `run_branch_analysis()`

---

### 2️⃣ **트리 로드/생성: `main_branch.py::run_branch_analysis()`**

```python
def run_branch_analysis(dataset_type='random', q=2, timestamp=None):
    # 결과 디렉토리 생성
    result_dir = f'branch_results/{timestamp}'
    
    # 트리 생성/로드 선택
    if dataset_type == 'random':
        # 전용 함수 호출 (tree_utils.py)
        trees = [random_tree() for _ in range(20)]
    else:  # 'ast'
        # AST JSON 파일에서 로드 (tree_utils.py)
        trees = load_trees_from_json('asts.json', max_trees=50)
    
    print(f"[{dataset_type.upper()}_q{q}] {len(trees)} trees | ", end='', flush=True)
```

**호출 대상들**:
- `tree_utils.py::random_tree()` → 무작위 트리 생성
- `tree_utils.py::load_trees_from_json()` → AST 트리 로드

**진행**: 다음 단계로 Binary Branch Distance 계산

---

### 3️⃣ **핵심 알고리즘: `algorithms.py::run_binary_branch_distance_experiment()`**

이 함수가 모든 거리 계산을 수행합니다.

#### **단계 1: Branch Vector 사전 계산**

```python
def run_binary_branch_distance_experiment(trees, q=2):
    # === 단계 1 ===
    # 모든 트리의 q-level branch count 벡터를 미리 계산
    branch_vectors = precompute_branch_vectors(trees, q)
    #                 ↓
    #         tree_utils.py::precompute_branch_vectors() 호출
```

**`precompute_branch_vectors()` 내부 흐름** (`tree_utils.py`):

```python
def precompute_branch_vectors(trees, q=2):
    branch_vectors = []
    
    for tree in trees:
        # 3단계: 일반 트리 → 이진 트리 변환
        bt = tree_to_binary_tree(tree, make_full=True)
        #     ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
        # left-child, right-sibling 표현으로 변환
        
        # 4단계: 이진 트리 정규화 (full binary tree)
        bt = normalize_binary_tree(bt)
        #     ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
        # 모든 내부 노드가 정확히 2개 자식을 가지도록
        # (없는 자식은 ε 노드로 채움)
        
        # 5단계: q-level binary branch 추출
        branches = extract_q_level_binary_branches(bt, q)
        #          ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
        # 각 (non-ε) 노드를 루트로 높이 (q-1) 완전 이진 트리 추출
        
        # 6단계: Branch 빈도 계산 (Counter)
        count = Counter(branches)
        branch_vectors.append(count)
    
    return branch_vectors  # [{branch_name: count, ...}, ...]
```

**호출 체인**:
```
precompute_branch_vectors()
  ├─ tree_to_binary_tree()
  │  └─ (재귀적으로 모든 노드 처리)
  │
  ├─ normalize_binary_tree()
  │  └─ (재귀적으로 ε 노드 채움)
  │
  ├─ extract_q_level_binary_branches()
  │  └─ extract_perfect_subtree() (각 non-ε 노드마다)
  │
  └─ Counter() (Python 표준)
```

**핵심 알고리즘 세부사항**:

##### **a) `tree_to_binary_tree()` - 일반 트리 → 이진 트리 변환**

```python
def tree_to_binary_tree(tree, make_full=True):
    label, children = tree
    
    if not children:
        # 리프 노드: 왼쪽 자식에 ε 추가
        return (label, ("ε", None, None), None)
    
    # 첫 자식 → left child
    left_child = tree_to_binary_tree(children[0], make_full)
    
    # 나머지 자식들 → right sibling chain
    right_sibling = None
    for child in reversed(children[1:]):
        binary_child = tree_to_binary_tree(child, make_full)
        right_sibling = (None, binary_child, right_sibling)
    
    return (label, left_child, right_sibling)
```

**예제**:
```
원본 트리:           이진 트리로 변환:
    A                    A
   /|\          →       / \
  B C D              B   (right sibling)
                       \
                        C
                         \
                          D
```

##### **b) `normalize_binary_tree()` - Full Binary Tree 정규화**

```python
def normalize_binary_tree(btree):
    label, left, right = btree
    
    # 왼쪽 자식이 없으면 ε으로 채우기
    if left is None:
        left = ("ε", None, None)
    else:
        left = normalize_binary_tree(left)  # 재귀
    
    # 오른쪽 자식이 없으면 ε으로 채우기
    if right is None:
        right = ("ε", ("ε", None, None), ("ε", None, None))
    else:
        right = normalize_binary_tree(right)  # 재귀
    
    return (label, left, right)
```

**결과**: 모든 내부 노드가 정확히 2개의 자식을 가지는 full binary tree

##### **c) `extract_q_level_binary_branches()` - q-level branch 추출**

```python
def extract_q_level_binary_branches(btree, q=2, branches=None):
    if branches is None:
        branches = []
    
    label, left, right = btree
    
    # 💡 핵심: ε 노드 제외! (padding이므로 카운트 안함)
    if label != "ε":
        # 이 노드를 루트로 하는 높이 (q-1) 완전 이진 트리 추출
        branch_structure = extract_perfect_subtree(btree, q - 1)
        branches.append(branch_structure)  # 문자열 표현으로 저장
    
    # 재귀: 왼쪽과 오른쪽 자식 모두 처리
    if left is not None:
        extract_q_level_binary_branches(left, q, branches)
    if right is not None:
        extract_q_level_binary_branches(right, q, branches)
    
    return branches  # branch 문자열 리스트
```

**중요 원칙**: ε-only 노드는 branch 벡터에 포함되지 **않음**

##### **d) `extract_perfect_subtree()` - 부분 트리를 문자열로 표현**

```python
def extract_perfect_subtree(node, height):
    if node is None or node[0] == "ε":
        return "."  # ε 노드는 "." 로 표현
    
    label, left, right = node
    
    if height == 0:
        return label  # 리프 노드
    
    # height > 0: 내부 노드
    left_str = extract_perfect_subtree(left, height - 1)
    right_str = extract_perfect_subtree(right, height - 1)
    
    # 예: "A(.,.)" 형태로 반환
    return f"{label}({left_str},{right_str})"
```

**예제** (q=2, height=1):
```
노드 A 루트의 height-1 부분트리:
    A
   / \
  B   C

extract_perfect_subtree(A_node, 1) 반환:
→ "A(B,C)"

Counter에 저장되어 같은 구조 반복 계산
```

---

#### **단계 2: 모든 트리 쌍의 거리 계산**

```python
def run_binary_branch_distance_experiment(trees, q=2):
    # ... (단계 1 완료)
    
    # === 단계 2 ===
    edit_dists, raw_bdists = [], []
    
    # 모든 쌍 (i, j) 반복 (조합 선택)
    for i, j in combinations(range(len(trees)), 2):
        # Edit Distance 계산 (APTED 라이브러리)
        ed = compute_edit_distance(trees[i], trees[j])
        #    ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
        #    tree_utils.py::compute_edit_distance()
        edit_dists.append(ed)
        
        # Binary Branch Distance 계산 (사전 계산된 벡터 사용)
        norm_dist, raw_dist = compute_branch_distance_from_vectors(
            branch_vectors[i], 
            branch_vectors[j], 
            q
        )
        #                      ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
        #                      tree_utils.py::compute_branch_distance_from_vectors()
        
        raw_bdists.append(raw_dist)
        approximate_dists.append(norm_dist)
```

**`compute_edit_distance()` 구현** (`tree_utils.py`):

```python
def compute_edit_distance(t1, t2):
    """APTED 라이브러리를 사용한 Tree Edit Distance 계산"""
    apted1 = tree_to_apted(t1)  # (label, children) → {'name': ..., 'children': ...}
    apted2 = tree_to_apted(t2)
    
    apted = APTED(SimpleConfig())  # APTED 객체 생성
    return apted.compute_edit_distance(apted1, apted2)  # 정수 거리 반환
```

**`compute_branch_distance_from_vectors()` 구현** (`tree_utils.py`):

```python
def compute_branch_distance_from_vectors(count1, count2, q=2):
    # count1, count2: Counter 객체 {branch_name: frequency}
    
    # 모든 unique branch 찾기
    all_branches = set(count1.keys()) | set(count2.keys())
    
    # L1 거리 계산 (Manhattan distance)
    raw_dist = sum(
        abs(count1.get(b, 0) - count2.get(b, 0)) 
        for b in all_branches
    )
    
    # 정규화 (논문의 lower bound)
    normalization = 4 * (q - 1) + 1
    # q=2 → 5, q=3 → 9, q=4 → 13
    normalized_dist = raw_dist / normalization
    
    return normalized_dist, raw_dist
```

**결과**:
- `raw_dist`: 실제 BDist (lower bound 검증용)
- `normalized_dist`: `raw_dist / normalization` (correlation 계산용)

---

#### **단계 3: 상관계수 및 통계 계산**

```python
def run_binary_branch_distance_experiment(trees, q=2):
    # ... (단계 1, 2 완료)
    
    # === 단계 3 ===
    # Pearson & Spearman 상관계수 계산
    from scipy import stats
    
    pearson_r_raw, _ = stats.pearsonr(edit_dists, raw_bdists)
    #                                   ED 값들     BDist 값들
    # → 두 거리 메트릭 간의 선형 상관도 계산
    
    spearman_r_raw, _ = stats.spearmanr(edit_dists, raw_bdists)
    # → Rank-based 상관도 (순서 보존 정도)
    
    # 정규화 factor
    normalization = 4 * (q - 1) + 1
    
    characteristic_dim = len(all_unique_branches)
    # 모든 추출된 unique branch 구조의 개수
```

**반환 값** (dict 형태):

```python
{
    'q': 2,
    'edit_dists': [1, 5, 3, ...],           # List of ED values
    'raw_bdists': [2, 4, 2, ...],           # List of Raw BDist values
    'approximate_dists': [0.4, 0.8, ...],   # Normalized BDist (raw/norm)
    'pearson_r': 0.95,                      # Correlation (normalized)
    'pearson_r_raw': 0.98,                  # Correlation (raw)
    'normalization': 5,                     # 4(q-1)+1
    'characteristic_dim': 512,              # Unique branch count
    'timing': {'total': 1.40}               # Execution time in seconds
}
```

---

### 4️⃣ **Lower Bound 검증: `algorithms.py::check_lower_bound_violations()`**

```python
def check_lower_bound_violations(result):
    """
    논문의 Lower Bound 정리 검증:
    BDist(T1, T2) >= ED(T1, T2)  (Raw BDist 기준)
    """
    edit_dists = result['edit_dists']
    raw_bdists = result['raw_bdists']
    
    # 위반 검사: ED > Raw BDist인 쌍이 있는가?
    violations = edit_dists > raw_bdists
    n_violations = sum(violations)
    
    if n_violations == 0:
        print(f"  ✓ Raw BDist >= ED: PASS (0/{len(edit_dists)} violations)")
    else:
        print(f"  ✗ Raw BDist >= ED: FAIL ({n_violations} violations)")
        # 각 위반의 정도 분석
    
    # 통계 출력
    print(f"    - Mean Raw BDist: {mean(raw_bdists):.2f}")
    print(f"    - Mean Normalized BDist: {mean(raw_bdists/norm):.2f}")
    print(f"    - Correlation (Pearson r): {result['pearson_r_raw']:.4f}")
```

**출력 예시**:
```
  📋 [STRICT LOWER BOUND CHECK] q=2
  ✓ Raw BDist >= ED: PASS (0/190 violations)

  ℹ  [정규화 거리 정보] (correlation 계산용, lower bound 대상 아님)
    - Normalization factor: 5
    - Mean Raw BDist: 93.26
    - Mean Normalized BDist: 18.65 (= 93.26 / 5)
    - Correlation (Pearson r): 0.9822

  📊 거리 분포 통계:
    - Edit Distance:      min=1.0, max=120.0, mean=50.86
    - Raw BDist:          min=2.0, max=232.0, mean=93.26
    - Normalized BDist:   min=0.4, max=46.4, mean=18.65

  ✓✓ Lower Bound 조건 만족 ✓✓
```

---

### 5️⃣ **시각화: `main_branch.py::save_branch_distance_comparison()`**

```python
def save_branch_distance_comparison(result, source='random', output_dir=None):
    """
    BDist vs Edit Distance 산점도 생성
    - 왼쪽: Raw BDist vs ED (y=x 하한, y=norm*x 이론상한 포함)
    - 오른쪽: Normalized BDist vs ED
    """
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    
    x = result['edit_dists']           # X축: Edit Distance
    y = result['raw_bdists']           # Y축: Binary Branch Distance
    
    # === 왼쪽 플롯 ===
    ax = axes[0]
    ax.scatter(x, y, alpha=0.6, s=20)  # s=20: 점 크기 (작게)
    
    # 하한선: y = x (Lower Bound)
    ax.plot([0, max_val], [0, max_val], 'r--', linewidth=2.5, label='y=x (Lower Bound)')
    
    # 상한선: y = normalization * x (Theoretical Upper Bound)
    norm = result['normalization']  # e.g., 5 for q=2
    ax.plot([0, max_val/norm], [0, max_val], 'g--', linewidth=2.5, label=f'y={norm}×x (Theory)')
    
    ax.set_xlabel('Edit Distance (ED)', fontsize=13, fontweight='bold')
    ax.set_ylabel('Binary Branch Distance (BDist)', fontsize=13, fontweight='bold')
    ax.legend(fontsize=11, loc='upper left')
    ax.grid(True, alpha=0.3)
    
    # === 오른쪽 플롯 ===
    ax = axes[1]
    normalized_y = y / norm
    ax.scatter(x, normalized_y, alpha=0.6, s=20, color='purple')
    ax.plot([0, max_val], [0, max_val], 'r--', linewidth=2.5, label='y=x (Lower Bound)')
    # 정규화된 거리도 ED 이상이어야 함
    
    # 파일 저장
    filename = f"bbdist_comparison_q{result['q']}_{source}.png"
    plt.savefig(os.path.join(output_dir, filename), dpi=100, bbox_inches='tight')
    plt.close()
```

**그래프 생성 위치**: `branch_results/{timestamp}/`

**예시 파일명**:
- `bbdist_comparison_q2_random.png`
- `bbdist_comparison_q2_ast.png`
- `bbdist_comparison_q3_random.png`
- ...

---

## 📈 데이터 흐름 다이어그램

```
main_branch.py::main()
    │
    ├─ random.seed(42)
    │
    ├─ [FOR q IN {2, 3, 4}]
    │  │
    │  ├─ run_branch_analysis('random', q)
    │  │  │
    │  │  ├─ random_tree() × 20
    │  │  │  └─ (label, [children]) tuples
    │  │  │
    │  │  ├─ run_binary_branch_distance_experiment(trees, q)
    │  │  │  │
    │  │  │  ├─ precompute_branch_vectors(trees, q)
    │  │  │  │  └─ FOR tree IN trees:
    │  │  │  │     ├─ tree_to_binary_tree(tree)
    │  │  │  │     │  └─ left-child, right-sibling 변환
    │  │  │  │     ├─ normalize_binary_tree(bt)
    │  │  │  │     │  └─ ε 노드로 채워 full binary tree 생성
    │  │  │  │     ├─ extract_q_level_binary_branches(bt, q)
    │  │  │  │     │  └─ FOR non-ε node:
    │  │  │  │     │     └─ extract_perfect_subtree(node, q-1)
    │  │  │  │     │        └─ 높이 (q-1) 완전 이진 트리의 문자열 표현
    │  │  │  │     └─ Counter(branches) → branch_vectors[i]
    │  │  │  │
    │  │  │  ├─ FOR (i, j) IN combinations(range(len(trees)), 2):
    │  │  │  │  ├─ compute_edit_distance(trees[i], trees[j]) → ED
    │  │  │  │  └─ compute_branch_distance_from_vectors(v[i], v[j]) → BDist
    │  │  │  │
    │  │  │  ├─ pearsonr(ED_list, BDist_list)
    │  │  │  └─ RETURN result dict
    │  │  │
    │  │  ├─ check_lower_bound_violations(result)
    │  │  │  └─ RAW BDist >= ED 검증 및 통계 출력
    │  │  │
    │  │  └─ save_branch_distance_comparison(result, 'random', result_dir)
    │  │     └─ 2×1 그래프 저장 (PNG)
    │  │
    │  └─ run_branch_analysis('ast', q) [동일 과정]
    │     ├─ load_trees_from_json('asts.json', 50)
    │     │  └─ AST JSON 파일에서 50개 트리 로드
    │     └─ [나머지 동일]
    │
    └─ PRINT 완료 메시지 및 실행 시간
```

---

## 🔑 핵심 개념 정리

### **1. Tree-to-Binary Tree 변환**
- **목적**: 임의의 다진 트리(n-ary tree)를 이진 트리로 정규화
- **방법**: left-child, right-sibling 표현
  - 첫 번째 자식 → 왼쪽 자식
  - 나머지 자식들 → 오른쪽 형제 체인

### **2. Full Binary Tree 정규화**
- **목적**: 모든 내부 노드가 정확히 2개의 자식을 가지도록 함
- **방법**: 자식이 없는 경우 ε(epsilon) 노드로 채움
- **중요**: ε 노드는 branch vector 계산에서 **제외**됨

### **3. q-Level Binary Branch**
논문 Definition 5 구현:
- **q=2**: 높이 1인 완전 이진 트리 (3개 노드)
- **q=3**: 높이 2인 완전 이진 트리 (7개 노드)
- **q=4**: 높이 3인 완전 이진 트리 (15개 노드)

### **4. Binary Branch Distance (BDist)**
- **계산**: 두 트리의 q-level branch 벡터의 L1 거리 (Manhattan distance)
- **Lower Bound**: BDist ≥ ED (Theorem 3.1/3.2/3.3)
- **정규화**: BDist / [4(q-1)+1] → correlation 계산용

### **5. Characteristic Vector Dimension**
- **의미**: 주어진 트리 집합에서 추출된 **고유한 branch 구조**의 개수
- **변동성**: q 값과 트리 집합에 따라 다름
  - RANDOM: 더 작은 dimension (보다 균일한 구조)
  - AST: 더 작은 dimension (특정 패턴에 집중)

---

## 📊 실행 결과 예시

### **RANDOM_q2 결과**
```
[RANDOM_q2] 20 trees | r=0.9822 | dim=512 | time=1.40s

  📋 [STRICT LOWER BOUND CHECK] q=2
  ✓ Raw BDist >= ED: PASS (0/190 violations)

  ℹ  [정규화 거리 정보]
    - Normalization factor: 5
    - Mean Raw BDist: 93.26
    - Mean Normalized BDist: 18.65 (= 93.26 / 5)
    - Correlation (Pearson r): 0.9822

  📊 거리 분포 통계:
    - Edit Distance:      min=1.0, max=120.0, mean=50.86
    - Raw BDist:          min=2.0, max=232.0, mean=93.26
    - Normalized BDist:   min=0.4, max=46.4, mean=18.65

  ✓✓ Lower Bound 조건 만족 ✓✓
```

### **AST_q2 결과**
```
[AST_q2] 50 trees | r=0.9676 | dim=105 | time=23.56s

  📋 [STRICT LOWER BOUND CHECK] q=2
  ✓ Raw BDist >= ED: PASS (0/1225 violations)
  
  [나머지 통계...]
  
  ✓✓ Lower Bound 조건 만족 ✓✓
```

---

## 📁 파일 구조

```
tree_embedding_examples/
├── main_branch.py                 # 진입점
├── algorithms.py                  # 실험 실행 함수들
├── tree_utils.py                  # 트리 유틸리티
├── asts.json                      # AST 트리 데이터셋
└── branch_results/
    └── {timestamp}/               # e.g., "2026-04-17_15-59-38"
        ├── bbdist_comparison_q2_random.png
        ├── bbdist_comparison_q2_ast.png
        ├── bbdist_comparison_q3_random.png
        ├── bbdist_comparison_q3_ast.png
        ├── bbdist_comparison_q4_random.png
        └── bbdist_comparison_q4_ast.png
```

---

## 🚀 실행 방법

```bash
# 전체 파이프라인 실행
python main_branch.py

# 출력: 
# [q=2]
# [RANDOM_q2] 20 trees | r=0.9822 | dim=512 | time=1.40s
# [STRICT LOWER BOUND CHECK]...
# [AST_q2] 50 trees | r=0.9676 | dim=105 | time=23.56s
# ...
# [q=3], [q=4] 결과들...
# ✓ 완료 (68.62s)
```

---

## 🎯 성능 지표

| Dataset | q | Trees | Pairs | ED Range | BDist Range | Correlation | Violations |
|---------|---|-------|-------|----------|-------------|-------------|-----------|
| RANDOM | 2 | 20 | 190 | [1, 120] | [2, 232] | r=0.9822 | 0/190 |
| AST | 2 | 50 | 1225 | [0, 95] | [0, 155] | r=0.9676 | 0/1225 |
| RANDOM | 3 | 20 | 190 | [1, 120] | [2, 260] | r=0.9748 | 0/190 |
| AST | 3 | 50 | 1225 | [0, 95] | [0, 193] | r=0.9362 | 0/1225 |
| RANDOM | 4 | 20 | 190 | [1, 120] | [2, 260] | r=0.9748 | 0/190 |
| AST | 4 | 50 | 1225 | [0, 95] | [0, 211] | r=0.9182 | 0/1225 |

---

## 📝 주요 함수 요약표

| 모듈 | 함수 | 역할 | 입력 | 출력 |
|-----|------|------|------|------|
| tree_utils | `random_tree()` | 무작위 트리 생성 | - | (label, [children]) |
| tree_utils | `load_trees_from_json()` | AST 로드 | json_file, max_trees | [tree, ...] |
| tree_utils | `tree_to_binary_tree()` | 다진 트리 → 이진 트리 | tree | (label, left, right) |
| tree_utils | `normalize_binary_tree()` | Full binary tree 생성 | btree | normalized_btree |
| tree_utils | `extract_q_level_binary_branches()` | Branch 추출 | btree, q | [branch_str, ...] |
| tree_utils | `extract_perfect_subtree()` | 부분트리 문자열화 | node, height | "branch_str" |
| tree_utils | `precompute_branch_vectors()` | 모든 트리의 branch vector 계산 | trees, q | [Counter, ...] |
| tree_utils | `compute_branch_distance_from_vectors()` | 두 벡터 간 BDist | count1, count2, q | (norm_dist, raw_dist) |
| tree_utils | `compute_edit_distance()` | Edit Distance 계산 | t1, t2 | ED (int) |
| algorithms | `run_binary_branch_distance_experiment()` | 모든 거리 계산 및 통계 | trees, q | result_dict |
| algorithms | `check_lower_bound_violations()` | Lower bound 검증 | result | (print + None) |
| main_branch | `save_branch_distance_comparison()` | 시각화 저장 | result, source, output_dir | filename |
| main_branch | `run_branch_analysis()` | 단일 dataset 분석 | dataset_type, q | result |
| main_branch | `main()` | 전체 파이프라인 | - | (print + save) |

---

**최종 완료**: ✅ 모든 lower bound 조건 만족 (0 violations) + 높은 상관도 (r > 0.91)
