import sys
import os
import json
import logging
from functools import wraps
from datetime import datetime
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
    json_path='/home/yunyoung/tree_embedding_examples/analysis_from_RANGO/ast_basic2.json',
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

@log_function_call
def dfs1(ast) -> tuple:
    global dfs_call_count
    dfs_call_count += 1
    
    if isinstance(ast, list):
        if len(ast) == 0:
            return ("", [])
        
        ret = ["", []]
        st_idx = 0
        if not isinstance(ast[0], list):
            tag = ast[0]

            logger.debug("tag: %s", tag)

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
                    return ('KerName', [])

            match tag:# cconstr 순서를 지키려고 함
                case 'Rel' if len(ast) == 2:
                    return (f'Rel_{ast[1]}', [])
                case 'Var':
                    pass
                case 'Meta':
                    assert len(ast) == 2
                    return (f'Meta_{ast[1]}', [])
                case 'Evar':
                    pass
                case 'Sort':
                    assert len(ast) == 2
                    assert isinstance(ast[1], list)
                    sort_type = ast[1][0]
                    assert not isinstance(sort_type, list)
                    return ('Sort', [(sort_type, [])])
                case 'Cast':
                    pass
                case 'Prod':
                    pass
                case 'Lambda':
                    pass
                case 'LetIn':
                    pass
                case 'App':
                    pass
                case 'Const':
                    pass
                case 'Ind':
                    assert len(ast) == 2
                    pass
                case 'Construct':
                    pass
                case 'Case':
                    pass
                case 'Fix':
                    pass
                case 'CoFix':
                    pass
                case 'Proj':
                    pass
                case 'Int':
                    pass
                case 'Float':
                    pass
                case 'Array':
                    pass

            if isinstance(tag, int):
                ret[0] = '_'
            else:
                ret[0] = str(tag)
            st_idx = 1

        for idx in range(st_idx, len(ast)):
            #print("ast: ", ast)
            #print("ast[idx]: ", ast[idx])
            assert isinstance(ast[idx], list) or isinstance(ast[idx], str) or isinstance(ast[idx], int)
            ret[1].append(dfs1(ast[idx]))
            
        return tuple(ret)
    else:
        assert isinstance(ast, str) or isinstance(ast, int)
        if isinstance(ast, int):
            return ('_', [])
        else:
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
def get_trees(limit=-1, flag=False) -> list[any]:
    print("📋 EXTRACTING STRINGS FROM ast_basic2.json")
    print("=" * 50)
    
    eval_results = extract_and_eval(limit=limit, flag=flag)
    eval_list = [r['evaluated'] for r in eval_results if r['status'] == 'success']

    cnts = []
    all_labels = []

    trees = []

    for eval_ele in eval_list:        
        global dfs_call_count
        dfs_call_count = 0  # 각 AST마다 리셋
        
        raw_ast = eval_ele[1]
        
        parsed_ast = dfs1(raw_ast)
        trees.append(parsed_ast)
        #print(f"[📊] DFS 호출 횟수: {dfs_call_count}")
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

    print(f"\n[📊] DFS 호출 횟수 - 평균: {np.mean(cnts):.2f}, 총 AST: {len(cnts)}")
    
    # 모든 등장한 label 출력
    unique_labels = sorted(set(all_labels))
    print(f"\n[🏷️] 모든 등장 Label ({len(unique_labels)}개):")
    for label in unique_labels:
        count = all_labels.count(label)
        print(f"  - <{label}>: {count}회")
    
    print(f"\n[📈] 전체 Label 등장 횟수: {len(all_labels)}")
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
    analysis_dir = os.path.dirname(os.path.abspath(__file__))
    branch_results_dir = os.path.join(analysis_dir, "branch_results")
    output_dir, timestamp = get_timestamp_dir(branch_results_dir)
    
    # 캐시 파일은 analysis_from_RANGO/ 바로 밑에 저장
    cache_file = os.path.join(analysis_dir, "edit_distances_q2.json")
    
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

def dfs2(ast) -> tuple:
    if isinstance(ast, list):
        if len(ast) == 0:
            return ("", [])
        
        ret = ["", []]
        st_idx = 0
        if not isinstance(ast[0], list):
            ret[0] = str(ast[0])
            st_idx = 1

        for idx in range(st_idx, len(ast)):
            #print("ast: ", ast)
            #print("ast[idx]: ", ast[idx])
            assert isinstance(ast[idx], list) or isinstance(ast[idx], str) or isinstance(ast[idx], int)
            ret[1].append(dfs2(ast[idx]))
            
        return tuple(ret)
    else:
        assert isinstance(ast, str) or isinstance(ast, int)
        return (str(ast), [])

@log_function_call
def main2():
    limit = 10
    eval_results = extract_and_eval(limit=limit, flag=False)
    eval_list = [r['evaluated'] for r in eval_results if r['status'] == 'success']
    for idx, eval_elem in enumerate(eval_list):
        print(f"\n{'='*60}")
        print(f"[{idx}] Parsed Tree Structure")
        print(f"{'='*60}")

        raw_ast = eval_elem[1]
        parsed_ast = dfs2(raw_ast)
        pretty_print_tree(parsed_ast)

def pretty_print_sexpr(node, indent=0):
    """Python list S-expression을 tab 들여쓰기로 예쁘게 출력"""
    TAB = "\t"
    prefix = TAB * indent

    if isinstance(node, list):
        if len(node) == 0:
            print(prefix + "[]")
        elif len(node) == 1 and not isinstance(node[0], list):
            print(prefix + f"[{node[0]},]")
        else:
            print(prefix + "[")
            for child in node:
                pretty_print_sexpr(child, indent + 1)
            print(prefix + "]")
    else:
        print(prefix + str(node) + ",")


@log_function_call
def main3():
    limit = 20
    trees = get_trees(limit=limit, flag=False)
    for idx, tree in enumerate(trees):
        print(f"\n{'='*60}")
        print(f"[{idx}] Parsed Tree from dfs1")
        print(f"{'='*60}")
        pretty_print_tree(tree)


if __name__=="__main__":
    # Command line 인자로 logging level 동적 변경
    # 사용법:
    #   python main.py                  (기본: DEBUG)
    #   python main.py --log-level info (INFO 레벨)
    #   python main.py --log-level debug (DEBUG 레벨)
    
    import sys
    
    log_level = logging.DEBUG  # 기본값
    #log_level = logging.INFO
    
    # 로깅 레벨 재설정
    logging.getLogger().setLevel(log_level)
    logger.info(f"Logging level set to: {logging.getLevelName(log_level)}")
    
    main3()
