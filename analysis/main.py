import sys
import os
import json
import logging
import io
from functools import wraps
from contextlib import redirect_stdout
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import tree_utils
from tree_utils import dfs_with_filtering, dfs_without_filtering

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

def iter_ast_record_strings(proof_records):
    if isinstance(proof_records, list):
        return proof_records
    if isinstance(proof_records, dict):
        records = []
        thm_record = proof_records.get("astinfo_for_thm")
        if thm_record is not None:
            records.append(thm_record)
        records.extend(proof_records.get("astinfos_for_tactics", []))
        return records
    raise TypeError(f"Unsupported proof record shape: {type(proof_records).__name__}")

def log_function_call(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        logging.info(f"{func.__name__} called")
        try:
            return func(*args, **kwargs)
        finally:
            logging.info(f"{func.__name__} finished")
    return wrapper

@log_function_call
def extract_and_eval(
    json_path=os.path.join(ANALYSIS_DIR, 'ast_basic2.json'),
    limit=10,
):
    """ast_basic2.json에서 모든 string 추출 및 eval (구조: project -> file -> proof -> [strings])
    """
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    eval_results = []
    idx = 0
    
    # project_key -> file_name_key -> proof_name_key -> [strings] or grouped AST records
    for project_key, files in data.items():
        for file_idx, (file_name, proofs) in enumerate(files.items(), start=1):
            logger.info(f"Checking file {file_idx}/{len(files)}: {project_key} / {file_name}")
            for proof_name, proof_records in proofs.items():
                logger.info(f"Checking proof: {project_key} / {file_name} / {proof_name}")
                for string in iter_ast_record_strings(proof_records):
                    if limit != -1 and idx >= limit:
                        break
                    
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
                    idx += 1
                if limit != -1 and idx >= limit:
                    break
            if limit != -1 and idx >= limit:
                break
        if limit != -1 and idx >= limit:
            break
    
    successful = sum(1 for r in eval_results if r['status'] == 'success')
    print(f"[✓] {successful}/{len(eval_results)} 성공")
    
    return eval_results

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
def get_trees(
    limit=-1,
    include_names=False,
    use_filtering_dfs=True,
    json_path=None,
) -> list[any]:
    if json_path is None:
        json_path = os.path.join(ANALYSIS_DIR, 'ast_basic2.json')

    print(f"📋 EXTRACTING STRINGS FROM {json_path}")
    print("=" * 50)
    
    eval_results = extract_and_eval(json_path=json_path, limit=limit)
    successful_results = [r for r in eval_results if r['status'] == 'success']

    cnts = []
    all_labels = []

    trees = []
    dfs = dfs_with_filtering if use_filtering_dfs else dfs_without_filtering
    logger.info("Using DFS parser: %s", dfs.__name__)

    for result in successful_results:
        eval_ele = result['evaluated']
        raw_ast = eval_ele[1]
        tactic = eval_ele[4]
        goal_string = eval_ele[5] if len(eval_ele) > 5 else ''
        
        parsed_ast = dfs(raw_ast)
        if include_names:
            trees.append((result['proof'], tactic, goal_string, parsed_ast))
        else:
            trees.append(parsed_ast)

        if limit < 20 and limit != -1:
            print(">>> eval_ele", eval_ele)
            print(">>> raw_ast", raw_ast)
            print(">>> goal_string", goal_string)
            print(">>> parsed", parsed_ast)
            print("-" * 50)
        
        # 해당 parsed tree에서 모든 label 수집
        labels = collect_labels(parsed_ast)
        all_labels.extend(labels)
    
    return trees

def pretty_print_tree(node, indent=0):
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
def main(json_path=None):
    limit = 20
    use_filtering_dfs = True
    trees = get_trees(
        limit=limit,
        include_names=True,
        use_filtering_dfs=use_filtering_dfs,
        json_path=json_path,
    )
    for idx, (proof_name, tactic, goal_string, tree) in enumerate(trees):
        tree_output = io.StringIO()
        with redirect_stdout(tree_output):
            pretty_print_tree(tree)
        logger.debug(
            "\n%s\n[%d] %s | tactic: %s\n%s\n%s\n%s",
            "="*60,
            idx,
            proof_name,
            tactic,
            f"goal:\n{goal_string}" if goal_string else "goal: <empty>",
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
    
    #json_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ANALYSIS_DIR, 'ast_library_basic2.v.json')
    json_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ANALYSIS_DIR, 'ast_library_simple.v.json')
    main(json_path=json_path)
