from collections import Counter
from typing import TypeAlias

from apted.helpers import Tree as APTEDTree

try:
    from data_management.ast_types import Ast
except ImportError:
    from ast_types import Ast

Tree: TypeAlias = tuple[str, list["Tree"]]
Branch: TypeAlias = tuple[str, str, str]
BranchVector: TypeAlias = Counter[Branch]
AstNode: TypeAlias = Ast | str | int

def extract_q_level_binary_branches(tree: Tree, q: int = 2) -> list[Branch]:
    #'ε', 
    assert isinstance(tree, tuple) and len(tree) == 2, "트리는 (label, children) 형태여야 합니다."
    assert isinstance(tree[1], list), "children은 리스트여야 합니다."
    
    branches: list[Branch] = []

    def go(root: Tree, right_label: str) -> None:
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

def compute_branch_distance_from_vectors(
    count1: BranchVector,
    count2: BranchVector,
    q: int = 2,
) -> tuple[float, int]:
    """사전 계산된 branch vectors로 거리 계산
    
    Args:
        count1, count2: Counter 객체 (branch -> 빈도)
        q: q-level
    
    Returns:
        (normalized_dist, raw_dist)
    """
    dist = branch_distance_from_vectors(count1, count2)
    
    normalization = 4 * (q - 1) + 1
    normalized_dist = dist / normalization if normalization > 0 else dist
    
    return normalized_dist, dist

def to_apted_tree(tree: Tree) -> APTEDTree:
    label, children = tree
    return APTEDTree(label, *(to_apted_tree(child) for child in children))

def extract_q_level_binary_branch_vector(tree: Tree, q: int = 2) -> BranchVector:
    return Counter(extract_q_level_binary_branches(tree, q=q))

def branch_distance_from_vectors(
    count1: BranchVector,
    count2: BranchVector,
) -> int:
    all_branches = set(count1.keys()) | set(count2.keys())
    return sum(
        abs(count1.get(branch, 0) - count2.get(branch, 0))
        for branch in all_branches
    )

def branch_distance(
    branches1: dict[str, int],
    branches2: dict[str, int],
) -> int:
    all_branches = set(branches1.keys()) | set(branches2.keys())
    return sum(
        abs(branches1.get(branch, 0) - branches2.get(branch, 0))
        for branch in all_branches
    )

def branch_distance_score(
    branches1: dict[str, int],
    branches2: dict[str, int],
) -> float:
    return 1 / (1 + branch_distance(branches1, branches2))

def pretty_print_tree(node, indent=0):
    def display_label(value) -> str:
        return "<empty>" if value == "" else str(value)

    if isinstance(node, tuple) and len(node) == 2:
        label, children = node
        print("  " * indent + f"├─ {display_label(label)}")
        if isinstance(children, list):
            for child in children:
                pretty_print_tree(child, indent + 1)
    else:
        print("  " * indent + f"└─ {display_label(node)}")

def dfs_with_filtering(ast: AstNode, var_ids: dict[str, int] | None = None) -> Tree:
    if var_ids is None:
        var_ids = {}
    
    if isinstance(ast, list):
        if len(ast) == 0:
            return ("", [])
        
        ret = ["", []]
        st_idx = 0
        ed_idx = len(ast)

        def default_elimination(
            tag: str | int,
            new_st_idx: int,
            new_ed_idx: int,
        ) -> None:
            nonlocal st_idx, ed_idx
            ret[0] = str(tag)
            st_idx = new_st_idx
            ed_idx = new_ed_idx

        def ind_ref_label(ind_ref: Ast) -> str:
            assert isinstance(ind_ref, list) and len(ind_ref) == 2
            mutind, ind_idx = ind_ref
            assert isinstance(mutind, list) and len(mutind) >= 2
            assert mutind[0] == 'MutInd'
            kername = mutind[1]
            assert isinstance(kername, list) and len(kername) == 3
            assert kername[0] == 'KerName'
            assert isinstance(kername[2], list) and kername[2][0] == 'Id'
            return f"{kername[2][1]}_{ind_idx}"

        def case_branch_body(branch: Ast) -> AstNode:
            assert isinstance(branch, list) and len(branch) >= 2
            return branch[-1]

        def binder_label(binder: Ast) -> str:
            assert isinstance(binder, list) and len(binder) >= 1
            binder_name = binder[0]
            assert isinstance(binder_name, list) and binder_name[0] == 'binder_name'
            name = binder_name[1]
            if isinstance(name, list) and len(name) == 2 and name[0] == 'Name':
                ident = name[1]
                if isinstance(ident, list) and len(ident) == 2 and ident[0] == 'Id':
                    return f"Name_{ident[1]}"
            return "Name"

        def recursive_defs(defs: Ast) -> list[Tree]:
            assert isinstance(defs, list) and len(defs) == 3
            binders, types, bodies = defs
            assert len(binders) == len(types) == len(bodies)
            return [
                (
                    f"Def_{binder_label(binder)}",
                    [
                        ("Type", [dfs_with_filtering(typ, var_ids)]),
                        ("Body", [dfs_with_filtering(body, var_ids)]),
                    ],
                )
                for binder, typ, body in zip(binders, types, bodies)
            ]

        if not isinstance(ast[0], list):
            tag = ast[0]

            match tag:
                # just ID
                case 'Id':
                    assert len(ast) == 2
                    return ('Id', [])

                # binder
                case 'binder_relevance' if len(ast) == 2:
                    return (f"{tag}_{ast[1]}", [])

                # kernel name
                case 'KerName':
                    assert len(ast) == 3
                    assert ast[2][0] == 'Id'
                    Id = ast[2][1]
                    return (f'KerName_{Id}', [])
                case 'MutInd':
                    assert len(ast) >= 2
                    return (
                        "MutInd",
                        [
                            dfs_with_filtering(child, var_ids)
                            for child in ast[1:]
                            if child != []
                        ],
                    )

            match tag:# cconstr 순서를 지키려고 함
                case 'Rel':
                    assert len(ast) == 2
                    return (f'Rel_{ast[1]}', [])
                case 'Var':
                    assert len(ast) == 2
                    assert ast[1][0] == 'Id'
                    var_name = ast[1][1]
                    if var_name not in var_ids:
                        var_ids[var_name] = len(var_ids) + 1
                    return (f'Var_{var_ids[var_name]}', [])
                case 'Meta':
                    assert len(ast) == 2
                    return (f'Meta_{ast[1]}', [])
                case 'Evar':
                    return ('Evar', [])
                case 'Sort':
                    assert len(ast) == 2
                    if isinstance(ast[1], list):
                        sort_type = ast[1][0]
                    else:
                        sort_type = ast[1]
                    assert not isinstance(sort_type, list)
                    return (f'Sort_{sort_type}', [])
                case 'Cast':
                    assert len(ast) == 4
                    default_elimination(tag=tag, new_st_idx=1, new_ed_idx=len(ast))
                case 'Prod':
                    assert len(ast) == 4
                    default_elimination(tag=tag, new_st_idx=2, new_ed_idx=len(ast))
                case 'Lambda':
                    assert len(ast) == 4
                    default_elimination(tag=tag, new_st_idx=2, new_ed_idx=len(ast))
                case 'LetIn':
                    assert len(ast) == 5
                    default_elimination(tag=tag, new_st_idx=2, new_ed_idx=len(ast))
                case 'App':
                    assert len(ast) == 3
                    return (
                        "App",
                        [
                            dfs_with_filtering(ast[1], var_ids),
                            (
                                "Parameters",
                                [
                                    dfs_with_filtering(param, var_ids)
                                    for param in ast[2]
                                ],
                            ),
                        ],
                    )
                case 'Const':
                    assert len(ast) == 2
                    constant = ast[1][0]
                    assert isinstance(constant, list)
                    assert constant[0] == 'Constant'
                    assert isinstance(constant[1], list)
                    return ("Const", [dfs_with_filtering(constant[1], var_ids)])
                case 'Ind':
                    assert len(ast) == 2
                    ind_ref, _instance = ast[1]
                    assert isinstance(ind_ref, list) and len(ind_ref) == 2
                    mutind, ind_idx = ind_ref
                    assert isinstance(mutind, list)
                    assert isinstance(ind_idx, str)
                    if (
                        len(mutind) >= 2
                        and mutind[0] == "MutInd"
                        and isinstance(mutind[1], list)
                        and len(mutind[1]) == 3
                        and mutind[1][0] == "KerName"
                        and isinstance(mutind[1][2], list)
                        and len(mutind[1][2]) == 2
                        and mutind[1][2][0] == "Id"
                    ):
                        return (f"Ind_MutInd_{mutind[1][2][1]}_{ind_idx}", [])
                    return (
                        "Ind",
                        [
                            (
                                "",
                                [
                                    dfs_with_filtering(mutind, var_ids),
                                    (ind_idx, []),
                                ],
                            )
                        ],
                    )
                case 'Construct':
                    assert len(ast) == 2
                    construct_type = ast[1][0][0]
                    construct_indx = ast[1][0][1]
                    assert isinstance(construct_type, list)
                    return (f"Construct_{construct_indx}", [dfs_with_filtering(construct_type, var_ids)])
                case 'Case':
                    assert len(ast) == 8
                    ci_ind = ast[1][0]
                    assert ci_ind[0] == 'ci_ind'
                    case_label = ind_ref_label(ci_ind[1])
                    predicate = ast[4]
                    scrutinee = ast[6]
                    branches = ast[7]

                    return (
                        f"Case_{case_label}",
                        [
                            ("Return", [dfs_with_filtering(predicate, var_ids)]),
                            ("Scrutinee", [dfs_with_filtering(scrutinee, var_ids)]),
                            (
                                "Branches",
                                [
                                    dfs_with_filtering(case_branch_body(branch), var_ids)
                                    for branch in branches
                                ],
                            ),
                        ],
                    )
                case 'Fix':
                    assert len(ast) == 2
                    return ("Fix", recursive_defs(ast[1][1]))
                case 'CoFix':
                    assert len(ast) == 2
                    return ("CoFix", recursive_defs(ast[1][1]))
                case 'Proj':
                    assert len(ast) == 3

                    proj_ind = ast[1][0][0]
                    assert proj_ind[0] == 'proj_ind'
                    proj_arg = ast[1][0][3]
                    assert proj_arg[0] == 'proj_arg'
                    proj_name = ast[1][0][4]
                    assert proj_name[0] == 'proj_name'
                    assert isinstance(proj_name[1], list)
                    assert proj_name[1][0] == 'Id'
                    proj_label = proj_name[1][1]

                    return (
                        f"Proj_{proj_label}",
                        [
                            dfs_with_filtering(proj_ind[1], var_ids),
                            dfs_with_filtering(proj_arg[1], var_ids),
                        ],
                    )
                case 'Int':
                    return ("Int", [])
                case 'Float':
                    return ("Float", [])
                case 'Array':
                    default_elimination(tag=tag, new_st_idx=2, new_ed_idx=len(ast))
                    assert len(ast) == 5
                case _:
                    default_elimination(tag=tag, new_st_idx=1, new_ed_idx=len(ast))

            if isinstance(tag, int):
                ret[0] = '_'

        for idx in range(st_idx, ed_idx):
            assert isinstance(ast[idx], list) or isinstance(ast[idx], str) or isinstance(ast[idx], int)
            ret[1].append(dfs_with_filtering(ast[idx], var_ids))
            
        return tuple(ret)
    else:
        assert isinstance(ast, str) or isinstance(ast, int)
        if isinstance(ast, int):
            return ('_', [])
        else:
            return (str(ast), [])

def dfs_without_filtering(ast: AstNode) -> Tree:
    if isinstance(ast, list):
        if len(ast) == 0:
            return ("", [])
        
        ret = ["", []]
        st_idx = 0
        if not isinstance(ast[0], list):
            ret[0] = str(ast[0])
            st_idx = 1

        for idx in range(st_idx, len(ast)):
            assert isinstance(ast[idx], list) or isinstance(ast[idx], str) or isinstance(ast[idx], int)
            ret[1].append(dfs_without_filtering(ast[idx]))
            
        return tuple(ret)
    else:
        assert isinstance(ast, str) or isinstance(ast, int)
        return (str(ast), [])
