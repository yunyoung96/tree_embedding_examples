"""
메인 실행 파일: AST 트리 기반 실험
"""
import random
import numpy as np
import time
import os

from tree_utils import load_trees_from_json, count_nodes
from algorithms import (
    build_vocabulary_from_trees, run_experiment, save_heatmap,
    run_binary_branch_distance_experiment, print_binary_branch_distance_results,
    save_binary_branch_distance_plot
)


def main():
    """메인 실험 함수"""
    random.seed(42)
    start_time = time.time()
    
    # 결과 디렉토리 생성
    result_dir = 'ast_results'
    if not os.path.exists(result_dir):
        os.makedirs(result_dir)
        print(f"✓ 결과 디렉토리 생성: {result_dir}/")
    
    print("\n" + "="*80)
    print("🚀 트리 임베딩 방법 비교 분석 (AST 트리)")
    print("="*80)
    
    # ==================== Stage 1: AST 로드 ====================
    print("\n[Stage 1/6] 🔄 AST 트리 로드\n")
    stage1_start = time.time()
    
    print("  AST 파일에서 트리 로드 중...")
    trees = load_trees_from_json("/home/yunyoung/tree_embedding_examples/experiments/asts.json", max_trees=50)
    
    if not trees:
        print("❌ 트리 로드 실패!")
        return
    
    avg_nodes = np.mean([count_nodes(tree) for tree in trees])
    stage1_time = time.time() - stage1_start
    print(f"✓ {len(trees)}개 AST 트리 로드 완료 (평균 노드: {avg_nodes:.1f})")
    print(f"  소요 시간: {stage1_time:.2f}초\n")
    
    results = []
    
    # ==================== Stage 2: Vocabulary 구축 ====================
    print("[Stage 2/6] 🔤 Vocabulary 구축\n")
    stage2_start = time.time()
    
    vocab = build_vocabulary_from_trees(trees)
    stage2_time = time.time() - stage2_start
    print(f"✓ Vocabulary 구축 완료 (크기: {len(vocab)})")
    print(f"  소요 시간: {stage2_time:.2f}초\n")
    
    # ==================== Stage 3: Tree 기반 방법 ====================
    print("[Stage 3/6] 🔧 Tree 기반 임베딩 방법 (18개)\n")
    stage3_start = time.time()
    
    tree_methods = [
        "Recursive Decomposition",
        "Fixed Vocab Tree Kernel",
        "Positional Encoding",
        "Hierarchical Encoding",
        "Contextualized Embedding",
        "Tree String Encoding",
        "DFS Path Encoding",
        "Node Degree Statistics",
        "Subtree Histogram",
        "Multi-Level Aggregation",
        "Tree Signature",
        "Random Walk",
        "Siamese Pattern",
        "Weighted Histogram",
        "Spectral Encoding",
        "Attention Encoding",
        "Tree LSTM",
        "Hyperbolic Embedding"
    ]
    
    for i, method in enumerate(tree_methods, 1):
        method_start = time.time()
        result = run_experiment(method, trees, "tree", vocab=vocab)
        method_time = time.time() - method_start
        if result:
            results.append(result)
            timing = result.get('timing', {})
            embed_time = timing.get('embedding', 0)
            ed_time = timing.get('edit_distance', 0)
            print(f"  [{i:2d}/18] {method:30s} r={result['pearson_r']:>7.4f} (임베딩:{embed_time:5.2f}s ED:{ed_time:5.2f}s 합계:{method_time:6.2f}s)")
    
    stage3_time = time.time() - stage3_start
    print(f"  Stage 3 총 소요 시간: {stage3_time:.2f}초\n")
    
    # ==================== Stage 4: BERT 기반 방법 ====================
    print("[Stage 4/6] 🤖 Transformer 기반 임베딩 (4개)\n")
    stage4_start = time.time()
    
    bert_models = [
        "bert-base-uncased",
        "bert-large-uncased",
        "distilbert-base-uncased",
        "roberta-base",
    ]
    
    for i, model in enumerate(bert_models, 1):
        model_start = time.time()
        result = run_experiment(model, trees, "bert", vocab=None)
        model_time = time.time() - model_start
        if result:
            results.append(result)
            model_short = model.split('/')[-1]
            timing = result.get('timing', {})
            embed_time = timing.get('embedding', 0)
            ed_time = timing.get('edit_distance', 0)
            print(f"  [{i}/4] {model_short:30s} r={result['pearson_r']:>7.4f} (임베딩:{embed_time:5.2f}s ED:{ed_time:5.2f}s 합계:{model_time:6.2f}s)")
    
    stage4_time = time.time() - stage4_start
    print(f"  Stage 4 총 소요 시간: {stage4_time:.2f}초\n")
    
    # ==================== Stage 5: 히트맵 저장 ====================
    print(f"[Stage 5/6] 📊 결과 시각화 ({len(results)}개)\n")
    stage5_start = time.time()
    for i, r in enumerate(results, 1):
        save_heatmap(r, source='ast', output_dir=result_dir)
        print(f"  [{i:2d}/{len(results)}] {r['name']:35s} → {result_dir}/ast_{r['name'].replace('/', '_').replace(' ', '_')}.png")
    stage5_time = time.time() - stage5_start
    print(f"  소요 시간: {stage5_time:.2f}초\n")
    
    # ==================== Stage 6: Binary Branch Distance 실험 ====================
    print(f"[Stage 6/6] 📐 Binary Branch Distance 분석\n")
    stage6_start = time.time()
    
    print("  Binary Branch Distance 계산 중 (q=2)...")
    bbdist_result = run_binary_branch_distance_experiment(trees, q=2)
    
    if bbdist_result:
        print_binary_branch_distance_results(bbdist_result)
        plot_filename = save_binary_branch_distance_plot(bbdist_result, source='ast', output_dir=result_dir)
        print(f"  ✓ 그래프 저장: {result_dir}/{plot_filename}\n")
        stage6_time = time.time() - stage6_start
        print(f"  소요 시간: {stage6_time:.2f}초\n")
    else:
        stage6_time = 0
        print("  ⚠️  Binary Branch Distance 계산 실패\n")
    
    # ==================== 최종 분석 ====================
    print("="*80)
    print("📋 성능 분석 (Edit Distance 기준)")
    print("="*80)
    print("해석: 음수가 좋음! (ED↑ 시 Similarity↓ = 음의 상관)\n")
    
    print(f"{'방법':<30}{'Pearson r':>12}{'Spearman r':>12}")
    print("-" * 60)
    
    sorted_results = sorted(results, key=lambda x: x['pearson_r'])
    for r in sorted_results:
        method_name = r['name']
        print(f"{method_name:<30}{r['pearson_r']:>12.4f}{r['spearman_r']:>12.4f}")
    print("-" * 60)
    
    # ==================== 최고 성능 방법 ====================
    print("\n" + "="*80)
    print("🏆 최종 결과")
    print("="*80)
    
    best = sorted_results[0]  # 가장 음수인 것이 최고
    
    print(f"\n✨ 최고 성능: {best['name']}")
    print(f"   Pearson r  = {best['pearson_r']:.4f}")
    print(f"   Spearman r = {best['spearman_r']:.4f}")
    print(f"   임베딩 차원 = {best['vec_dim']}D")
    
    print(f"\n📊 상위 5개 방법:")
    for i, r in enumerate(sorted_results[:5], 1):
        print(f"  {i}. {r['name']:<35} Pearson r={r['pearson_r']:>7.4f}")
    
    # ==================== 전체 시간 ====================
    total_time = time.time() - start_time
    print("\n" + "="*80)
    print("⏱️  실행 시간 요약")
    print("="*80)
    print(f"  Stage 1 (AST 로드):       {stage1_time:>8.2f}초")
    print(f"  Stage 2 (Vocabulary):     {stage2_time:>8.2f}초")
    print(f"  Stage 3 (Tree 방법):      {stage3_time:>8.2f}초")
    print(f"  Stage 4 (BERT 방법):      {stage4_time:>8.2f}초")
    print(f"  Stage 5 (시각화):         {stage5_time:>8.2f}초")
    print(f"  Stage 6 (Binary Branch):  {stage6_time:>8.2f}초")
    print("-" * 40)
    print(f"  전체 소요 시간:           {total_time:>8.2f}초")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
