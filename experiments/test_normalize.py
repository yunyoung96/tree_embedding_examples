#!/usr/bin/env python3
"""리스트 형식 트리 정규화 테스트"""
from sexpdata import Symbol
import sys

# normalize_tree 함수 (main_ast.py와 동일)
def normalize_tree(tree):
    """
    리스트 형식 트리를 (label, children) 튜플로 변환
    """
    # 이미 튜플 형식
    if isinstance(tree, tuple) and len(tree) == 2:
        return tree
    
    # 기본 타입
    if not isinstance(tree, list):
        return (str(tree), [])
    
    # 빈 리스트
    if len(tree) == 0:
        return ("", [])
    
    first = tree[0]
    
    # Symbol이 첫 인자인 경우 
    if isinstance(first, Symbol):
        # Symbol의 이름만 추출
        label = first.val if hasattr(first, 'val') else str(first).strip("Symbol()'\"")
        children = [normalize_tree(child) for child in tree[1:]]
        return (label, children)
    
    # 첫 인자가 리스트/튜플인 경우
    elif isinstance(first, (list, tuple)):
        label = ""
        children = [normalize_tree(child) for child in tree]
        return (label, children)
    
    # 기타 (int, str 등)
    else:
        label = str(first)
        rest = tree[1:] if len(tree) > 1 else []
        children = [normalize_tree(child) for child in rest]
        return (label, children)


def count_nodes(tree):
    """트리의 총 노드 개수 계산"""
    tree = normalize_tree(tree)
    node, children = tree
    return 1 + sum(count_nodes(child) for child in children)


def count_subtrees(tree, depth_limit=5):
    """부분 트리 구조를 특징으로 변환"""
    tree = normalize_tree(tree)  # normalize_tree 호출
    
    def get_subtrees(node, cur_depth=0, prefix=""):
        features = []
        n_label, children = node
        node_sig = f"{prefix}{n_label}#{len(children)}"
        features.append(node_sig)
        
        if cur_depth < depth_limit:
            for i, child in enumerate(children):
                child_features = get_subtrees(child, cur_depth+1, f"{node_sig}-{i}")
                features.extend(child_features)
        
        return features
    
    subtrees = get_subtrees(tree)
    feature_dict = {}
    for st in subtrees:
        feature_dict[st] = feature_dict.get(st, 0) + 1
    
    return feature_dict


if __name__ == "__main__":
    print("=" * 60)
    print("테스트: 리스트 형식 트리 정규화")
    print("=" * 60)
    
    # ast.txt에서 첫 5개 트리만 로드
    with open("ast.txt", 'r') as f:
        for i, line in enumerate(f.readlines()[:5]):
            try:
                print(f"\n[Tree {i}] 로드 중...")
                tree = eval(line.strip())
                print(f"  원본 타입: {type(tree)}, 길이: {len(tree) if isinstance(tree, (list, tuple)) else 'N/A'}")
                
                # 정규화
                norm_tree = normalize_tree(tree)
                print(f"  정규화 완료: {type(norm_tree)}")
                
                # 노드 수
                nodes = count_nodes(tree)
                print(f"  노드 수: {nodes}")
                
                # 부분 트리
                features = count_subtrees(tree)
                print(f"  부분 트리 특징 수: {len(features)}")
                
                print(f"  ✓ Tree {i} 성공")
                
            except Exception as e:
                print(f"  ✗ Tree {i} 실패: {e}")
                import traceback
                traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("✓ 테스트 완료")
    print("=" * 60)
