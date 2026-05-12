"""
트리 생성/로드/변환 유틸리티 모듈
"""
import random
import numpy as np
from apted import APTED, Config

LABEL_POOL = [f"L{i}" for i in range(4)]

def tree_to_sequence(node, children):
    """트리를 괄호 표기법 문자열로 변환"""
    if not children:
        return f"({node})"
    child_strs = " ".join(tree_to_sequence(c, gc) for c, gc in children)
    return f"({node} {child_strs})"


def random_tree(max_depth=4, max_branch=4, cur_depth=0):
    """
    랜덤 트리 생성
    
    Args:
        max_depth: 최대 깊이
        max_branch: 최대 분기수
        cur_depth: 현재 깊이 (재귀용)
    
    Returns:
        (label, children) 형태의 트리
    """
    label = random.choice(LABEL_POOL)
    if cur_depth >= max_depth or random.random() < 0.2:
        return (label, [])
    num_children = random.randint(1, max_branch)
    children = [random_tree(max_depth, max_branch, cur_depth+1) for _ in range(num_children)]
    return (label, children)


def tree_to_apted(tree, _is_first_call=True):
    """
    트리를 APTED 라이브러리 형식으로 변환
    
    Args:
        tree: (label, children) 형태의 트리
        _is_first_call: 첫 호출 여부 (정규화 필요 여부)
    
    Returns:
        {'name': label, 'children': [...]} 형식의 딕셔너리
    """
    if _is_first_call:
        tree = normalize_tree(tree)
    
    label, children = tree
    return {'name': label, 'children': [tree_to_apted(c, _is_first_call=False) for c in children]}


def normalize_tree(tree):
    """
    트리를 정규화 (이미 정규화되었으면 그대로 반환)
    
    Args:
        tree: (label, children) 형태의 트리
    
    Returns:
        정규화된 트리
    """
    # 이미 정규화되었으면 그대로 반환
    if tree is None:
        return tree
    
    label, children = tree
    
    # children이 없으면 그대로 반환
    if not children:
        return (label, [])
    
    # children 재귀적으로 정규화
    normalized_children = [normalize_tree(child) for child in children]
    return (label, normalized_children)


class SimpleConfig(Config):
    """APTED 라이브러리용 설정"""
    def rename(self, node1, node2):
        return 0 if node1['name'] == node2['name'] else 1
    
    def children(self, node):
        return node['children']


def compute_edit_distance(t1, t2):
    """
    두 트리의 편집 거리 계산
    
    Args:
        t1, t2: (label, children) 형태의 트리
    
    Returns:
        편집 거리 (정수)
    """
    return APTED(tree_to_apted(t1), tree_to_apted(t2), SimpleConfig()).compute_edit_distance()


def count_nodes(tree):
    """
    트리의 총 노드 개수 계산
    
    Args:
        tree: (label, children) 형태의 트리
    
    Returns:
        노드 개수 (정수)
    """
    tree = normalize_tree(tree)
    node, children = tree
    return 1 + sum(count_nodes(child) for child in children)


# ==================== AST 로드 함수 ====================
def parse_ast_to_tree(ast_node):
    """
    JSON AST 구조를 (label, [children]) 형태의 tree로 변환
    
    Args:
        ast_node: JSON에서 읽은 AST 노드 (dict 또는 list 또는 기본형)
    
    Returns:
        (label, children) 형태의 트리
    """
    if isinstance(ast_node, dict):
        # {"v": "label"} 형태 - leaf node
        label = ast_node.get("v", "node")
        return (label, [])
    
    elif isinstance(ast_node, list):
        if len(ast_node) == 0:
            return ("empty", [])
        
        # [{"v": "label"}, child1, child2, ...] 형태
        first = ast_node[0]
        if isinstance(first, dict) and "v" in first:
            label = first["v"]
            children = []
            for child in ast_node[1:]:
                if isinstance(child, (dict, list)):
                    parsed_child = parse_ast_to_tree(child)
                    if parsed_child:
                        children.append(parsed_child)
            return (label, children)
        else:
            # 첫 번째가 dict가 아니면 재귀적으로 처리
            if first:
                return parse_ast_to_tree(first)
            else:
                return ("empty", [])
    
    else:
        return (str(ast_node), [])


def load_trees_from_json(json_file, max_trees=None):
    """
    JSON 파일에서 AST를 읽어서 labeled tree로 변환
    
    Args:
        json_file: JSON 파일 경로
        max_trees: 로드할 최대 트리 개수 (None이면 전체)
    
    Returns:
        트리 리스트
    """
    import json
    
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    trees = []
    for i, item in enumerate(data):
        if max_trees and len(trees) >= max_trees:
            break
        
        if "ast" in item and item["ast"]:
            try:
                tree = parse_ast_to_tree(item["ast"])
                if tree and count_nodes(tree) > 1:  # 유효한 tree만 추가
                    trees.append(tree)
            except Exception as e:
                continue
    
    return trees

def extract_q_level_binary_branches(tree, q=2):
    #'ε', 
    assert isinstance(tree, tuple) and len(tree) == 2, "트리는 (label, children) 형태여야 합니다."
    assert isinstance(tree[1], list), "children은 리스트여야 합니다."
    
    branches = []

    def go(root, right_label):
        #1. current label 
        label, children  = root
        #2. left label
        left_label = 'ε'  # padding label
        if children:
            left_label = children[0][0]  # 첫 번째 자식의 라벨
        #3. right label is known from argument
        
        #combining
        branches.append((label, left_label, right_label))
        
        ln = len(children)
        for idx, child in enumerate(children):
            if idx == ln - 1:
                go(child, 'ε')
            else:
                go(child, children[idx+1][0])

    go(tree, 'ε')  # 루트 노드의 오른쪽 자식은 padding
    return branches

def extract_perfect_subtree(node, height):
    """
    노드를 루트로 하는 높이 height인 부분트리를 문자열로 표현
    
    Args:
        node: (label, left_child, right_child) 형태의 노드
        height: 원하는 부분트리의 높이
    
    Returns:
        트리 구조를 나타내는 문자열 (ε과 None은 "."로 표현)
    """
    if node is None or node[0] == "ε" or node[0] is None:
        # ε 노드와 None placeholder는 "."로 표현
        return "."
    
    label, left, right = node
    
    if height == 0:
        # 리프 노드는 라벨만 표현
        return str(label)
    
    # height > 0: 내부 노드, left와 right subtree 표현
    left_str = extract_perfect_subtree(left, height - 1)
    right_str = extract_perfect_subtree(right, height - 1)
    
    # 양쪽이 모두 padding이면 라벨만 표현
    if left_str == "." and right_str == ".":
        return str(label)
    
    return f"{label}({left_str},{right_str})"


def compute_binary_branch_distance(t1, t2, q=2):
    """
    논문의 q-level binary branch distance 계산
    BDist_Q(T, T') / [4(q-1) + 1] → approximate edit distance
    
    Args:
        t1, t2: (label, children) 형태의 트리
        q: q-level (기본값 2)
    
    Returns:
        normalized binary branch distance (normalized lower bound)
    """
    
    # q-level binary branch 추출
    branches1 = extract_q_level_binary_branches(t1, q)
    branches2 = extract_q_level_binary_branches(t2, q)
    
    # branch 빈도 계산
    from collections import Counter
    count1 = Counter(branches1)
    count2 = Counter(branches2)
    
    # L1 distance 계산
    all_branches = set(count1.keys()) | set(count2.keys())
    dist = 0
    for branch in all_branches:
        dist += abs(count1.get(branch, 0) - count2.get(branch, 0))
    
    # 정규화 (lower bound)
    normalization = 4 * (q - 1) + 1
    normalized_dist = dist / normalization if normalization > 0 else dist
    
    return normalized_dist, dist


def precompute_branch_vectors(trees, q=2):
    """모든 트리의 q-level branch count 벡터 사전 계산
    
    Args:
        trees: 트리 리스트
        q: q-level
    
    Returns:
        각 트리의 branch Counter 리스트
    """
    from collections import Counter
    branch_vectors = []
    
    for i, tree in enumerate(trees):
        # q-level branch 추출
        #print(f"tree {i}: ", tree)
        branches = extract_q_level_binary_branches(tree, q)
        #print(f"tree {i} branches: ", branches)
        # Counter 생성 및 저장
        count = Counter(branches)
        branch_vectors.append(count)
    
    return branch_vectors


def compute_branch_distance_from_vectors(count1, count2, q=2):
    """사전 계산된 branch vectors로 거리 계산
    
    Args:
        count1, count2: Counter 객체 (branch -> 빈도)
        q: q-level
    
    Returns:
        (normalized_dist, raw_dist)
    """
    all_branches = set(count1.keys()) | set(count2.keys())
    dist = sum(abs(count1.get(b, 0) - count2.get(b, 0)) for b in all_branches)
    
    normalization = 4 * (q - 1) + 1
    normalized_dist = dist / normalization if normalization > 0 else dist
    
    return normalized_dist, dist
