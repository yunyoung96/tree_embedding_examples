#!/usr/bin/env python3
"""q=2 Lower Bound Violation 디버깅"""
import sys
sys.path.insert(0, '/home/yunyoung/tree_embedding_examples')

from experiments.tree_utils import *
from experiments.algorithms import *
import numpy as np

print("="*60)
print("Q=2 Lower Bound Violation 분석")
print("="*60)

# 작은 샘플로 테스트
random.seed(42)
trees = [random_tree() for _ in range(5)]

print(f"\n[트리 정보]")
for i, t in enumerate(trees):
    print(f"  트리 {i}: {count_nodes(t)} 노드")

print(f"\n[q=2 분석]")
for i, j in combinations(range(len(trees)), 2):
    ed = compute_edit_distance(trees[i], trees[j])
    norm_dist, raw_dist = compute_binary_branch_distance(trees[i], trees[j], q=2)
    
    ratio = raw_dist / ed if ed > 0 else 0
    bound = 5
    status = "✓" if raw_dist <= bound * ed else "✗"
    
    print(f"트리({i},{j}): ED={ed:3d}, BDist={raw_dist:4d}, 비율={ratio:.2f} (bound=5) {status}")

print("\n[결론]")
print("이론 (Theorem 3.2): BDist ≤ 5×ED")
print("현실: 많은 쌍에서 이를 초과함")
print("→ 구현 또는 이론 해석 재검토 필요")
