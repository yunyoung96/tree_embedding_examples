"""
메인 실행 파일: AST 트리 기반 실험
"""
import random
import numpy as np

from tree_utils import load_trees_from_json, count_nodes
from algorithms import (
    build_vocabulary_from_trees, run_experiment, save_heatmap
)


def main():
    """메인 실험 함수"""
    random.seed(42)
    
    print("\n" + "="*80)
    print("🚀 트리 임베딩 방법 비교 분석 (AST 트리)")
    print("="*80)
    
    # ==================== AST 트리 로드 ====================
    print("\n📍 시나리오: AST 트리 기반 유사도 평가\n")
    
    # JSON 파일에서 트리 로드
    print("🔄 AST 파일에서 트리 로드 중...")
    trees = load_trees_from_json("/home/yunyoung/tree_embedding_examples/experiments/asts.json", max_trees=150)
    
    if not trees:
        print("❌ 트리 로드 실패!")
        return
    
    avg_nodes = np.mean([count_nodes(tree) for tree in trees])
    print(f"✓ {len(trees)}개 AST 트리 로드 완료 (평균 노드: {avg_nodes:.1f})")
    
    results = []
    
    # ==================== Tree 기반 임베딩 방법 ====================
    print("\n🔧 Tree 기반 방법들 실험 중...\n")
    
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
    
    # Fixed Vocab 구축
    vocab = build_vocabulary_from_trees(trees)
    
    for method in tree_methods:
        result = run_experiment(method, trees, "tree", vocab=vocab)
        if result:
            results.append(result)
            print(f"  ✓ {method:30s} → Pearson r={result['pearson_r']:>7.4f}")
    
    # ==================== BERT 기반 방법 ====================
    print("\n🤖 Transformer 기반 방법들 실험 중...\n")
    
    bert_models = [
        "bert-base-uncased",
        "bert-large-uncased",
        "distilbert-base-uncased",
        "roberta-base",
    ]
    
    for model in bert_models:
        result = run_experiment(model, trees, "bert", vocab=None)
        if result:
            results.append(result)
            model_short = model.split('/')[-1]
            print(f"  ✓ {model_short:30s} → Pearson r={result['pearson_r']:>7.4f}")
    
    # ==================== 히트맵 저장 ====================
    print("\n📊 히트맵 저장 중...")
    for r in results:
        save_heatmap(r)
    print(f"  ✓ {len(results)}개 방법 히트맵 저장 완료")
    
    # ==================== 결과 분석 ====================
    print("\n" + "="*80)
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
    
    print("\n" + "="*80)


if __name__ == "__main__":
    main()
