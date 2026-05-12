# 트리 임베딩 프로젝트 - 리팩토링 가이드

## 📁 새로운 파일 구조

### 핵심 모듈 (3개 파일)

#### 1. `tree_utils.py` 
**트리 생성, 로드, 변환 유틸리티**

```python
# 랜덤 트리 생성
from tree_utils import random_tree
tree = random_tree(max_depth=4, max_branch=4)

# 트리 데이터 로드
from tree_utils import load_trees_from_json
trees = load_trees_from_json("asts.json", max_trees=100)

# 트리 처리
from tree_utils import compute_edit_distance, count_nodes
ed = compute_edit_distance(tree1, tree2)
nodes = count_nodes(tree)
```

**주요 함수:**
- `random_tree()` - 랜덤 트리 생성
- `load_trees_from_json()` - JSON 파일에서 AST 로드
- `compute_edit_distance()` - 트리 편집 거리 계산
- `count_nodes()` - 노드 개수 계산
- `tree_to_sequence()` - 트리를 괄호 표기법 문자열로 변환
- `normalize_tree()` - 트리 정규화


#### 2. `algorithms.py`
**모든 임베딩 알고리즘 및 실험 함수**

```python
# 실험 실행
from algorithms import run_experiment, build_vocabulary_from_trees, save_heatmap

vocab = build_vocabulary_from_trees(trees)
result = run_experiment("Recursive Decomposition", trees, "tree", vocab=vocab)
save_heatmap(result)
```

**포함된 임베딩 방법 (21개):**
1. Recursive Decomposition
2. Fixed Vocab Tree Kernel
3. Positional Encoding
4. Hierarchical Encoding
5. Contextualized Embedding
6. Tree String Encoding
7. DFS Path Encoding
8. Node Degree Statistics
9. Subtree Histogram
10. Multi-Level Aggregation
11. Tree Signature
12. Random Walk
13. Siamese Pattern
14. Weighted Histogram
15. Spectral Encoding
16. Attention Encoding
17. Tree LSTM
18. Hyperbolic Embedding
19. BERT-based (bert-base-uncased, bert-large-uncased, distilbert-base-uncased, roberta-base)

**주요 함수:**
- `get_tree_embedding()` - 메서드 선택
- `run_experiment()` - 실험 실행
- `build_vocabulary_from_trees()` - Vocabulary 구축
- `save_heatmap()` - 결과 시각화


#### 3. `tree_utils.py`
**트리 유틸리티**

---

### 실행 파일 (2개)

#### 1. `main_refactored.py` ✨ 새로운 메인 파일
**랜덤 트리로 실험**

```bash
python main_refactored.py
```

- 깔끔한 구조
- 알고리즘 패키지화
- 트리 생성/로드 로직 분리
- 150개 랜덤 트리로 모든 방법 비교

#### 2. `main_ast_refactored.py` ✨ 새로운 AST 메인 파일
**AST 트리로 실험**

```bash
python main_ast_refactored.py
```

- `asts.json` 파일에서 트리 로드
- 실제 소스코드 기반 AST 분석
- 동일한 실험 구조

---

## 🔄 기존 파일과의 비교

### Before (기존 구조)
```
main.py          (1058줄) - 모든 기능이 혼재
  ├── 트리 생성 로직
  ├── 모든 알고리즘 (21개 임베딩 방법)
  ├── 실험 코드
  └── 결과 분석

main_ast.py      (1607줄) - 알고리즘 중복
```

### After (새로운 구조)
```
tree_utils.py    (140줄) - 트리 처리 집중
  ├── 랜덤 트리 생성
  ├── AST 로드
  └── 트리 변환/계산

algorithms.py    (700줄) - 모든 알고리즘
  ├── 21개 임베딩 방법
  ├── 실험 함수
  └── 시각화

main_refactored.py        (80줄) - 실험 로직
  └── 랜덤 트리 기반

main_ast_refactored.py    (80줄) - 실험 로직
  └── AST 기반
```

---

## 💡 사용 방법

### 1. 기본 사용 (랜덤 트리)
```python
from tree_utils import random_tree, compute_edit_distance
from algorithms import run_experiment

# 트리 생성
tree1 = random_tree()
tree2 = random_tree()

# 편집 거리 계산
ed = compute_edit_distance(tree1, tree2)

# 임베딩 실험
result = run_experiment("Recursive Decomposition", [tree1, tree2], "tree")
print(f"Pearson r: {result['pearson_r']}")
```

### 2. AST 트리 로드 및 분석
```python
from tree_utils import load_trees_from_json
from algorithms import build_vocabulary_from_trees, run_experiment

# AST 로드
trees = load_trees_from_json("asts.json", max_trees=100)

# Vocabulary 구축
vocab = build_vocabulary_from_trees(trees)

# 실험 실행
result = run_experiment("Positional Encoding", trees, "tree", vocab=vocab)
```

### 3. 전체 실험 실행
```bash
# 랜덤 트리 실험
python main_refactored.py

# AST 트리 실험
python main_ast_refactored.py
```

---

## 📊 주요 개선 사항

### ✅ 코드 품질
- **중복 제거**: 동일한 임베딩 함수 1회만 구현
- **모듈화**: 기능별 분리 (생성, 알고리즘, 실행)
- **가독성**: 각 파일의 책임 명확화

### ✅ 유지보수성
- **새 방법 추가**: `algorithms.py`에 함수 추가만 하면 자동 연동
- **트리 처리 변경**: `tree_utils.py`에서 한 곳만 수정
- **실험 구조 변경**: `main_*.py`에서만 수정

### ✅ 확장성
- 새로운 임베딩 방법 추가 용이
- 다양한 데이터 소스 지원 (`random_tree`, `load_trees_from_json`)
- 실험 매개변수 유연하게 조정

### ✅ 성능
- 불필요한 함수 중복 제거로 메모리 절감
- 명확한 구조로 디버깅 시간 단축

---

## 🔧 기술 스택

- **Python 3.x**
- **PyTorch** - 벡터 연산
- **NumPy** - 수치 계산
- **SciPy** - 통계 함수
- **Transformers** - BERT/RoBERTa 모델
- **APTED** - 트리 편집 거리
- **Matplotlib/Seaborn** - 시각화

---

## 📝 참고

### 원본 파일
- `main.py` - 기존 랜덤 트리 구현 (참고용으로 유지)
- `main_ast.py` - 기존 AST 트리 구현 (참고용으로 유지)

### 새로운 파일 (권장)
- `main_refactored.py` - ✨ 리팩토링된 버전
- `main_ast_refactored.py` - ✨ 리팩토링된 버전
- `tree_utils.py` - ✨ 새로운 유틸리티
- `algorithms.py` - ✨ 새로운 알고리즘 모듈

---

## 🚀 시작하기

```bash
# 1. 의존성 설치 (필요시)
pip install torch transformers apted scikit-learn scipy

# 2. 랜덤 트리로 빠른 테스트
python main_refactored.py

# 3. 실제 AST 데이터로 분석 (asts.json 필요)
python main_ast_refactored.py
```

---

**Happy coding!** 🎉
