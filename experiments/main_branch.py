"""
Binary Branch Distance 분석 전용 스크립트
Edit Distance와 Branch Edit Distance의 상관관계만 표시
"""
import random
import numpy as np
import time
import os
import json
import matplotlib.pyplot as plt
from datetime import datetime

from tree_utils import random_tree, load_trees_from_json, count_nodes
from algorithms import (
    run_binary_branch_distance_experiment,
    print_binary_branch_distance_results,
    check_lower_bound_violations,
    _debug_tracer
)


def save_branch_distance_comparison(result, source='random', output_dir=None):
    """
    Edit Distance vs Binary Branch Distance 비교 그래프 저장
    y=x 선과 함께 lower bound 관계를 시각화
    
    Args:
        result: Binary Branch Distance 실험 결과 dict
        source: 데이터 소스 ('random' 또는 'ast')
        output_dir: 출력 디렉토리
    """
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    
    x = np.array(result['edit_dists'])
    y = np.array(result['raw_bdists'])
    
    # ========== 왼쪽 플롯: y=x 기준선 포함 ==========
    ax = axes[0]
    ax.scatter(x, y, alpha=0.6, s=20, color='blue', label='Observed (BDist, ED)')
    
    # y=x 선 그리기 (lower bound)
    max_val = max(max(x), max(y)) * 1.05
    ax.plot([0, max_val], [0, max_val], 'r--', linewidth=2.5, label='y=x (Lower Bound)')
    
    # y=normalization*x 선 그리기 (theoretical bound)
    norm = result['normalization']
    if max_val > 0:
        ax.plot([0, max_val/norm], [0, max_val], 'g--', linewidth=2.5, 
                label=f'y={norm}×x (Theory)')
    
    ax.set_xlabel('Edit Distance (ED)', fontsize=13, fontweight='bold')
    ax.set_ylabel('Binary Branch Distance (BDist)', fontsize=13, fontweight='bold')
    ax.set_title(f'Binary Branch Distance vs Edit Distance\n(Lower Bound Relationship)', 
                 fontsize=13, fontweight='bold')
    ax.legend(fontsize=11, loc='upper left')
    ax.grid(True, alpha=0.3)
    
    # ========== 오른쪽 플롯: 정규화된 거리 ==========
    ax = axes[1]
    normalized_y = y / norm
    ax.scatter(x, normalized_y, alpha=0.6, s=20, color='purple', label='Normalized BDist')
    
    # y=x 선
    ax.plot([0, max_val], [0, max_val], 'r--', linewidth=2.5, label='y=x (Lower Bound)')
    
    ax.set_xlabel('Edit Distance (ED)', fontsize=13, fontweight='bold')
    ax.set_ylabel('Normalized BDist / {}'.format(norm), fontsize=13, fontweight='bold')
    ax.set_title(f'Normalized Binary Branch Distance\n(should be ≥ ED)', 
                 fontsize=13, fontweight='bold')
    ax.legend(fontsize=11, loc='upper left')
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    # 파일명 구성 - q 값을 명확하게 포함
    q_value = result['q']
    source_suffix = f"_{source}" if source else ""
    filename = f"bbdist_comparison_q{q_value}{source_suffix}.png"
    
    # 디렉토리 경로 포함
    if output_dir:
        filepath = os.path.join(output_dir, filename)
    else:
        filepath = filename
    
    plt.savefig(filepath, dpi=100, bbox_inches='tight')
    plt.close()
    
    return filename


def run_branch_analysis(dataset_type='random', trees=None, max_trees=None, q=2, timestamp=None):
    assert q == 2
    """Binary Branch Distance 분석 실행"""
    _debug_tracer.enter("run_branch_analysis")
    _debug_tracer.log("START", "run_branch_analysis", "main_branch.py", "dataset_type", dataset_type)
    _debug_tracer.log("START", "run_branch_analysis", "main_branch.py", "q", q)
    
    result_dir = f'branch_results/{timestamp}'
    os.makedirs(result_dir, exist_ok=True)
    _debug_tracer.log("SETUP", "run_branch_analysis", "main_branch.py", "result_dir", result_dir)
    
    # 트리 생성/로드
    if trees is None:
        if dataset_type == 'random':
            random.seed(42)
            trees = [random_tree() for _ in range(100)]
            _debug_tracer.log("TREE_CREATION", "run_branch_analysis", "main_branch.py", "trees_created", len(trees))
        else:
            trees = load_trees_from_json('/home/yunyoung/tree_embedding_examples/experiments/asts.json', max_trees=50)
            _debug_tracer.log("TREE_LOAD", "run_branch_analysis", "main_branch.py", "trees_loaded", len(trees) if trees else 0)
        if not trees:
            _debug_tracer.exit("run_branch_analysis")
            return None
    
    _debug_tracer.log("PRE_ANALYSIS", "run_branch_analysis", "main_branch.py", "n_trees", len(trees))
    print(f"[{dataset_type.upper()}_q{q}] {len(trees)} trees | ", end='', flush=True)
    
    # Binary Branch Distance 계산
    _debug_tracer.enter("run_binary_branch_distance_experiment")
    result = run_binary_branch_distance_experiment(trees, q=q)
    _debug_tracer.exit("run_binary_branch_distance_experiment")
    
    if not result:
        print("Failed")
        _debug_tracer.exit("run_branch_analysis")
        return None
    
    _debug_tracer.log("POST_ANALYSIS", "run_branch_analysis", "main_branch.py", "n_pairs", len(result['edit_dists']))
    _debug_tracer.log("RESULTS", "run_branch_analysis", "main_branch.py", "pearson_r_raw", f"{result['pearson_r_raw']:.4f}")
    
    elapsed = result['timing']['total']
    r = result['pearson_r_raw']
    char_dim = result.get('characteristic_dim', 0)
    print(f"r={r:.4f} | dim={char_dim} | time={elapsed:.2f}s")
    
    # Lower Bound 엄격 검사
    _debug_tracer.enter("check_lower_bound_violations")
    try:
        check_lower_bound_violations(result)
        _debug_tracer.log("VALIDATION", "run_branch_analysis", "main_branch.py", "lower_bound_check", "PASSED")
    except AssertionError as e:
        _debug_tracer.exit("check_lower_bound_violations")
        _debug_tracer.log("ERROR", "run_branch_analysis", "main_branch.py", "lower_bound_check", "FAILED")
        _debug_tracer.exit("run_branch_analysis")
        raise  # 오류를 상위로 전파하여 프로그램 강제 종료
    _debug_tracer.exit("check_lower_bound_violations")
    
    # 그래프 저장
    _debug_tracer.enter("save_branch_distance_comparison")
    save_branch_distance_comparison(result, source=dataset_type, output_dir=result_dir)
    _debug_tracer.log("GRAPH", "run_branch_analysis", "main_branch.py", "graph_saved", True)
    _debug_tracer.exit("save_branch_distance_comparison")
    
    _debug_tracer.exit("run_branch_analysis")
    return result


def main():
    _debug_tracer.enter("main")
    _debug_tracer.log("START", "main", "main_branch.py", "program", "started")
    
    start_time = time.time()
    # 타임스탬프 생성 (날짜-시간)
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    _debug_tracer.log("SETUP", "main", "main_branch.py", "timestamp", timestamp)
    
    for q in [ 2 ]:
        _debug_tracer.log("LOOP", "main", "main_branch.py", "current_q", q)
        try:
            run_branch_analysis('random', max_trees=50, q=q, timestamp=timestamp)
        except AssertionError as e:
            _debug_tracer.log("FATAL_ERROR", "main", "main_branch.py", "error_type", "AssertionError")
            print(f"\n❌ PROGRAM TERMINATED: {e}")
            _debug_tracer.exit("main")
            raise SystemExit(1)  # 프로그램 강제 종료
    
    # 최종 요약
    elapsed = time.time() - start_time
    _debug_tracer.log("COMPLETE", "main", "main_branch.py", "total_time", f"{elapsed:.2f}s")
    print(f"\n✓ 완료 ({elapsed:.2f}s)")
    _debug_tracer.exit("main")

def mini_main():
    import ast
    with open('tree.txt', 'r') as f:
        data_string = f.read().strip()
    parsed_data = ast.literal_eval(data_string)    
    

def extract_all_strings_from_asts_json(json_path='asts.json', save_results=True):
    """
    asts.json에서 모든 string 값들을 재귀적으로 추출하고 eval한 후 리스트로 반환
    
    Args:
        json_path: asts.json 파일 경로
        save_results: 결과를 파일로 저장할지 여부
    
    Returns:
        (all_strings, eval_results) 튜플
        - all_strings: 모든 추출된 string 리스트
        - eval_results: eval 결과 딕셔너리 리스트
    """
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    all_strings = []
    eval_results = []
    
    def find_strings(obj):
        """재귀적으로 모든 string 찾기"""
        if isinstance(obj, str):
            all_strings.append(obj)
        elif isinstance(obj, dict):
            for v in obj.values():
                find_strings(v)
        elif isinstance(obj, list):
            for item in obj:
                find_strings(item)
    
    # 모든 항목에서 string 추출
    if isinstance(data, list):
        for item in data:
            find_strings(item)
    else:
        find_strings(data)
    
    # 각 string을 eval 시도
    print(f"[INFO] asts.json에서 {len(all_strings)}개의 string 발견")
    
    for idx, string in enumerate(all_strings):
        try:
            # eval 시도
            result = eval(string)
            eval_results.append({
                'index': idx,
                'original_string': string,
                'evaluated': result,
                'type': type(result).__name__,
                'status': 'success'
            })
        except Exception as e:
            # eval 실패한 경우
            eval_results.append({
                'index': idx,
                'original_string': string,
                'evaluated': None,
                'type': 'eval_failed',
                'error': str(e),
                'status': 'failed'
            })
    
    print(f"[INFO] 총 {len(eval_results)}개 string 처리 완료")
    successful_count = sum(1 for r in eval_results if r['status'] == 'success')
    failed_count = sum(1 for r in eval_results if r['status'] == 'failed')
    print(f"       - eval 성공: {successful_count}")
    print(f"       - eval 실패: {failed_count}")
    
    # 결과 저장
    if save_results:
        output_path = 'extracted_strings_eval_results.json'
        # JSON 직렬화를 위해 evaluated 필드를 문자열로 변환
        json_safe_results = []
        for r in eval_results:
            json_safe_results.append({
                'index': r['index'],
                'original_string': r['original_string'],
                'evaluated_str': str(r['evaluated']) if r['evaluated'] is not None else None,
                'type': r['type'],
                'status': r['status'],
                'error': r.get('error', None)
            })
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(json_safe_results, f, indent=2, ensure_ascii=False)
        print(f"\n💾 결과 저장: {output_path}")
    
    return all_strings, eval_results
    



if __name__ == "__main__":
    import sys
    
    # 커맨드라인 인자 확인
    if len(sys.argv) > 1 and sys.argv[1] == "--extract-strings":
        # asts.json에서 모든 string 추출 및 eval
        print("=" * 60)
        print("📋 EXTRACTING ALL STRINGS FROM asts.json")
        print("=" * 60)
        all_strings, eval_results = extract_all_strings_from_asts_json()
        
        # 결과 출력
        print("\n🔍 EVALUATION RESULTS SUMMARY:")
        print(f"  Total strings: {len(all_strings)}")
        print(f"  Successfully evaluated: {sum(1 for r in eval_results if r['type'] != 'eval_failed')}")
        print(f"  Failed to evaluate: {sum(1 for r in eval_results if r['type'] == 'eval_failed')}\n")
        
        # 상위 10개 성공한 결과 샘플 출력
        successful = [r for r in eval_results if r['type'] != 'eval_failed']
        print("📊 TOP 10 SUCCESSFULLY EVALUATED SAMPLES:")
        for i, result in enumerate(successful[:10], 1):
            eval_val = result['evaluated']
            if isinstance(eval_val, (list, dict)):
                preview = str(eval_val)[:80]
            else:
                preview = str(eval_val)[:80]
            print(f"  {i}. Type: {result['type']}")
            print(f"     Preview: {preview}")
            if len(preview) == 80:
                print(f"     ...")
        
        # 평가 결과 리스트 저장
        eval_list = [r['evaluated'] for r in eval_results if r['type'] != 'eval_failed']
        print(f"\n💾 Successfully evaluated {len(eval_list)} items")
        print(f"   평가된 데이터를 리스트에 저장했습니다: eval_list")
        
    else:
        # 기본 동작: Binary Branch Distance 분석 실행
        main()
