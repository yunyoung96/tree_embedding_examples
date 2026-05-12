import sys
import os
import json
import logging
import io
from functools import wraps
from datetime import datetime
from contextlib import redirect_stdout
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from experiments.tree_utils import random_tree
from experiments.algorithms import (
    run_binary_branch_distance_experiment,
    print_binary_branch_distance_results,
    check_lower_bound_violations,
    save_binary_branch_distance_plot
)

# ==================== Logging Configuration ====================
# DEBUG 레벨 활성화 (파일명, 함수명, 라인 번호 포함)
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(levelname)s] [%(filename)s:%(funcName)s:%(lineno)d] %(message)s'
)
logger = logging.getLogger(__name__)

# 외부 라이브러리의 DEBUG 로그 억제
logging.getLogger('matplotlib.font_manager').setLevel(logging.WARNING)
logging.getLogger('matplotlib').setLevel(logging.WARNING)

# INFO 레벨로 변경하려면 아래 주석을 해제하고 위의 basicConfig를 주석 처리하세요
# logging.basicConfig(
#     level=logging.INFO,
#     format='[%(levelname)s] [%(filename)s:%(funcName)s:%(lineno)d] %(message)s'
# )
# logger = logging.getLogger(__name__)

logger.debug("Logging configured with DEBUG level")

ANALYSIS_DIR = os.path.dirname(os.path.abspath(__file__))

def log_function_call(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        logging.info(f"{func.__name__} called")
        try:
            return func(*args, **kwargs)
        finally:
            logging.info(f"{func.__name__} finished")
    return wrapper

dfs_call_count = 0
@log_function_call
def extract_and_eval(
    json_path=os.path.join(ANALYSIS_DIR, 'ast_basic2.json'),
    limit=10,
    flag=False,
):
    """ast_basic2.json에서 모든 string 추출 및 eval (구조: project -> file -> proof -> [strings])

    flag=True이면 target_keywords 기반 필터링 루틴을 사용한다.
    flag=False이면 키워드 검사를 하지 않고 순서대로 읽는다.
    """
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    eval_results = []
    idx = 0
    target_keywords = (
        'MPfile', 'MPdot', 'MPbound',
        'Rel', 'Var', 'Meta', 'Evar', 'Sort', 'Cast', 'Prod', 'Lambda',
        'LetIn', 'App', 'Const', 'Ind', 'Construct', 'Case', 'Fix',
        'CoFix', 'Proj', 'Int', 'Float', 'Array'
    )
    keyword_counts = {keyword: 0 for keyword in target_keywords}
    
    # project_key -> file_name_key -> proof_name_key -> [strings]
    for project_key, files in data.items():
        for file_idx, (file_name, proofs) in enumerate(files.items(), start=1):
            logger.info(f"Checking file {file_idx}/{len(files)}: {project_key} / {file_name}")
            for proof_name, string_list in proofs.items():
                logger.info(f"Checking proof: {project_key} / {file_name} / {proof_name}")
                for string in string_list:
                    if flag:
                        if limit != -1 and all(count >= limit for count in keyword_counts.values()):
                            break
                        
                        matched_keywords = [
                            keyword
                            for keyword in target_keywords
                            if keyword in string and (limit == -1 or keyword_counts[keyword] < limit)
                        ]
                        if not matched_keywords:
                            continue
                    else:
                        if limit != -1 and idx >= limit:
                            break
                        matched_keywords = []
                    
                    try:
                        result = eval(string)
                        eval_results.append({
                            'index': idx,
                            'project': project_key,
                            'file': file_name,
                            'proof': proof_name,
                            'original_string': string,
                            'evaluated': result,
                            'type': type(result).__name__,
                            'status': 'success'
                        })
                    except Exception as e:
                        eval_results.append({
                            'index': idx,
                            'project': project_key,
                            'file': file_name,
                            'proof': proof_name,
                            'original_string': string,
                            'evaluated': None,
                            'type': 'eval_failed',
                            'error': str(e),
                            'status': 'failed'
                        })
                    for keyword in matched_keywords:
                        keyword_counts[keyword] += 1
                    idx += 1
                if not flag and limit != -1 and idx >= limit:
                    break
            if not flag and limit != -1 and idx >= limit:
                break
        if flag and limit != -1 and all(count >= limit for count in keyword_counts.values()):
            break
        if not flag and limit != -1 and idx >= limit:
            break
    
    if flag:
        logger.info(f"Keyword counts: {keyword_counts}")
    
    successful = sum(1 for r in eval_results if r['status'] == 'success')
    print(f"[✓] {successful}/{len(eval_results)} 성공")
    
    return eval_results

def dfs_with_filtering(ast, var_ids=None) -> tuple:
    if var_ids is None:
        var_ids = {}

    global dfs_call_count
    dfs_call_count += 1
    
    if isinstance(ast, list):
        if len(ast) == 0:
            return ("", [])
        
        ret = ["", []]
        st_idx = 0


        def default_elimination(tag, new_st_idx):
            nonlocal st_idx
            ret[0] = str(tag)
            st_idx = new_st_idx

        def ind_ref_label(ind_ref):
            assert isinstance(ind_ref, list) and len(ind_ref) == 2
            mutind, ind_idx = ind_ref
            assert isinstance(mutind, list) and len(mutind) >= 2
            assert mutind[0] == 'MutInd'
            kername = mutind[1]
            assert isinstance(kername, list) and len(kername) == 3
            assert kername[0] == 'KerName'
            assert isinstance(kername[2], list) and kername[2][0] == 'Id'
            return f"{kername[2][1]}_{ind_idx}"

        def case_branch_body(branch):
            assert isinstance(branch, list) and len(branch) >= 2
            return branch[-1]

        def binder_label(binder):
            assert isinstance(binder, list) and len(binder) >= 1
            binder_name = binder[0]
            assert isinstance(binder_name, list) and binder_name[0] == 'binder_name'
            name = binder_name[1]
            if isinstance(name, list) and len(name) == 2 and name[0] == 'Name':
                ident = name[1]
                if isinstance(ident, list) and len(ident) == 2 and ident[0] == 'Id':
                    return f"Name_{ident[1]}"
            return "Name"

        def recursive_defs(defs):
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
                    default_elimination(tag=tag,new_st_idx=1)
                case 'Prod':
                    assert len(ast) == 4
                    default_elimination(tag=tag,new_st_idx=2)
                case 'Lambda':
                    assert len(ast) == 4
                    default_elimination(tag=tag,new_st_idx=2)
                case 'LetIn':
                    assert len(ast) == 5
                    default_elimination(tag=tag,new_st_idx=2)
                case 'App':
                    assert len(ast) == 3
                    default_elimination(tag=tag,new_st_idx=1)
                case 'Const':
                    assert len(ast) == 2
                    constant = ast[1][0]
                    assert isinstance(constant, list)
                    assert constant[0] == 'Constant'
                    assert isinstance(constant[1], list)
                    return ("Const", [dfs_with_filtering(constant[1], var_ids)])
                case 'Ind':
                    assert len(ast) == 2
                    default_elimination(tag=tag,new_st_idx=1)
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
                    default_elimination(tag=tag,new_st_idx=2)
                    assert len(ast) == 5
                case _:
                    default_elimination(tag=tag, new_st_idx=1)

            if isinstance(tag, int):
                ret[0] = '_'

        for idx in range(st_idx, len(ast)):
            #print("ast: ", ast)
            #print("ast[idx]: ", ast[idx])
            assert isinstance(ast[idx], list) or isinstance(ast[idx], str) or isinstance(ast[idx], int)
            ret[1].append(dfs_with_filtering(ast[idx], var_ids))
            
        return tuple(ret)
    else:
        assert isinstance(ast, str) or isinstance(ast, int)
        if isinstance(ast, int):
            return ('_', [])
        else:
            return (str(ast), [])

def dfs_without_filtering(ast) -> tuple:
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

@log_function_call
def collect_labels(parsed_tree):
    """parsed tree를 순회하면서 모든 label 수집"""
    labels = []
    
    @log_function_call
    def traverse(node):
        if isinstance(node, tuple) and len(node) == 2:
            label, children = node
            labels.append(label)
            if isinstance(children, list):
                for child in children:
                    traverse(child)
    
    traverse(parsed_tree)
    return labels

@log_function_call
def get_trees(limit=-1, flag=False, include_names=False, use_filtering_dfs=True) -> list[any]:
    print("📋 EXTRACTING STRINGS FROM ast_basic2.json")
    print("=" * 50)
    
    eval_results = extract_and_eval(limit=limit, flag=flag)
    successful_results = [r for r in eval_results if r['status'] == 'success']

    cnts = []
    all_labels = []

    trees = []
    dfs = dfs_with_filtering if use_filtering_dfs else dfs_without_filtering
    logger.info("Using DFS parser: %s", dfs.__name__)

    for result in successful_results:
        global dfs_call_count
        dfs_call_count = 0  # 각 AST마다 리셋

        eval_ele = result['evaluated']
        raw_ast = eval_ele[1]
        tactic = eval_ele[4]
        
        parsed_ast = dfs(raw_ast)
        if include_names:
            trees.append((result['proof'], tactic, parsed_ast))
        else:
            trees.append(parsed_ast)
        cnts.append(dfs_call_count)

        if limit < 20 and limit != -1:
            print(">>> eval_ele", eval_ele)
            print(">>> raw_ast", raw_ast)
            print(">>> parsed", parsed_ast)
            print("-" * 50)
        
        # 해당 parsed tree에서 모든 label 수집
        labels = collect_labels(parsed_ast)
        all_labels.extend(labels)
    
    import numpy as np

    logger.info("[📊] DFS 호출 횟수 - 평균: %.2f, 총 AST: %d", np.mean(cnts), len(cnts))
    
    # 모든 등장한 label 출력
    unique_labels = sorted(set(all_labels))
    logger.info("[🏷️] 모든 등장 Label (%d개):", len(unique_labels))
    for label in unique_labels:
        count = all_labels.count(label)
        logger.info("  - <%s>: %d회", label, count)
    
    logger.info("[📈] 전체 Label 등장 횟수: %d", len(all_labels))
    return trees

@log_function_call
def get_timestamp_dir(base_dir):
    """타임스탐프 기반 디렉토리 생성 및 반환"""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_dir = os.path.join(base_dir, timestamp)
    os.makedirs(output_dir, exist_ok=True)
    return output_dir, timestamp

@log_function_call
def load_cached_distances(cache_file):
    """캐시 파일에서 edit distance 로드
    
    Returns:
        dict: {(i,j): distance} 형태, 파일이 없으면 None
    """
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # JSON에서는 키가 string이므로 tuple로 변환
            cached_distances = {tuple(map(int, k.strip('()').split(','))): v for k, v in data.items()}
            logger.info(f"✓ Loaded cached distances from {cache_file} ({len(cached_distances)} pairs)")
            return cached_distances
        except Exception as e:
            logger.warning(f"Failed to load cache file {cache_file}: {e}")
            return None
    return None

@log_function_call
def save_cached_distances(pair_indices, edit_dists, cache_file):
    """edit distance를 캐시 파일로 저장"""
    cache_data = {}
    for (i, j), dist in zip(pair_indices, edit_dists):
        key = f"({i},{j})"
        cache_data[key] = dist
    
    try:
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, indent=2)
        logger.info(f"✓ Saved edit distances to {cache_file} ({len(cache_data)} pairs)")
    except Exception as e:
        logger.warning(f"Failed to save cache file {cache_file}: {e}")


@log_function_call
def main1():
    logger.info("="*70)
    logger.info("STARTING ANALYSIS FROM RANGO")
    logger.info("="*70)
    
    # 타임스탐프 기반 출력 디렉토리 생성 (analysis_from_RANGO/branch_results 밑에 저장)
    branch_results_dir = os.path.join(ANALYSIS_DIR, "branch_results")
    output_dir, timestamp = get_timestamp_dir(branch_results_dir)
    
    # 캐시 파일은 analysis_from_RANGO/ 바로 밑에 저장
    cache_file = os.path.join(ANALYSIS_DIR, "edit_distances_q2.json")
    
    logger.info(f"Output directory: {output_dir}")
    logger.info(f"Cache file: {cache_file}")
    
    logger.info("[Step 1/3] Loading and parsing AST trees...")
    trees = get_trees(limit=100)
    logger.info(f"[Step 1/3] ✓ Loaded {len(trees)} trees")
    print(f"\n📊 총 트리 개수: {len(trees)}")
    
    # Binary Branch Distance 실험
    logger.info("[Step 2/3] Running Binary Branch Distance experiment...")
    print("\n" + "="*50)
    print("🔬 Binary Branch Distance 실험 시작")
    print("="*50)
    
    # 캐시된 거리 로드
    cached_distances = load_cached_distances(cache_file)
    
    result = run_binary_branch_distance_experiment(trees, q=2, cached_distances=cached_distances)
    logger.info("[Step 2/3] ✓ Binary Branch Distance experiment completed")
    
    # 새로 계산된 거리가 있으면 캐시에 저장
    if cached_distances is None:
        save_cached_distances(result['pair_indices'], result['edit_dists'], cache_file)
    
    print_binary_branch_distance_results(result)
    
    # Lower Bound 체크
    logger.info("[Step 3/3] Checking lower bound violations...")
    print("\n" + "="*50)
    check_lower_bound_violations(result)
    logger.info("[Step 3/3] ✓ Lower bound check passed")
    
    # 시각화 (timestamped 디렉토리에 저장)
    logger.debug("Generating visualization plot...")
    print("\n" + "="*50)
    filename = save_binary_branch_distance_plot(result, source='ast', output_dir=output_dir)
    logger.debug(f"Plot saved in: {output_dir}")
    print(f"✓ 결과 저장 (2개 subplot 포함 1개 figure):")
    print(f"  - {os.path.join(output_dir, filename)}")
    
    logger.info("="*70)
    logger.info("ANALYSIS COMPLETED SUCCESSFULLY")
    logger.info("="*70)

def pretty_print_tree(node, indent=0):
    """트리 구조를 들여쓰기로 예쁘게 출력"""
    if isinstance(node, tuple) and len(node) == 2:
        label, children = node
        print("  " * indent + f"├─ {label}")
        if isinstance(children, list):
            for i, child in enumerate(children):
                is_last = i == len(children) - 1
                pretty_print_tree(child, indent + 1)
    else:
        print("  " * indent + f"└─ {node}")

@log_function_call
def main():
    limit = 20
    use_filtering_dfs = True
    trees = get_trees(
        limit=limit,
        flag=False,
        include_names=True,
        use_filtering_dfs=use_filtering_dfs,
    )
    for idx, (proof_name, tactic, tree) in enumerate(trees):
        tree_output = io.StringIO()
        with redirect_stdout(tree_output):
            pretty_print_tree(tree)
        logger.debug(
            "\n%s\n[%d] %s | tactic: %s\n%s\n%s",
            "="*60,
            idx,
            proof_name,
            tactic,
            "="*60,
            tree_output.getvalue().rstrip(),
        )


if __name__=="__main__":
    import sys
    
    log_level = logging.DEBUG  # 기본값
    #log_level = logging.INFO
    
    # 로깅 레벨 재설정
    logging.getLogger().setLevel(log_level)
    logger.info(f"Logging level set to: {logging.getLevelName(log_level)}")
    
    main()
