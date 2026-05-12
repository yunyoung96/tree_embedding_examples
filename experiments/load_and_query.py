# -*- coding: utf-8 -*-
"""
ChromaDB에 저장된 벡터를 로드하고 유사도 계산하는 예시
main_ast.py 에서 저장한 데이터를 다른 파일에서 사용
"""
import chromadb
import numpy as np
from scipy.spatial.distance import cosine

CHROMADB_PATH = "./chroma_db"

def load_all_results(db_name="tree_embeddings"):
    """ChromaDB에서 모든 결과 로드"""
    client = chromadb.PersistentClient(path=CHROMADB_PATH)
    collection = client.get_or_create_collection(name=db_name)
    
    results = collection.get(include=["embeddings", "metadatas"])
    return results

def get_method_by_name(method_name, db_name="tree_embeddings"):
    """특정 method의 결과 로드"""
    client = chromadb.PersistentClient(path=CHROMADB_PATH)
    collection = client.get_or_create_collection(name=db_name)
    
    results = collection.query(
        where={"method_name": {"$eq": method_name}},
        include=["embeddings", "metadatas"]
    )
    
    return results

def query_similar_methods(query_embedding, top_k=5, db_name="tree_embeddings"):
    """쿼리 벡터와 유사한 method들 찾기"""
    client = chromadb.PersistentClient(path=CHROMADB_PATH)
    collection = client.get_or_create_collection(name=db_name)
    
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["embeddings", "metadatas", "distances"]
    )
    
    return results

def calculate_cosine_similarity(vec1, vec2):
    """두 벡터 사이의 코사인 유사도 계산"""
    distance = cosine(vec1, vec2)
    similarity = 1 - distance
    return similarity

def print_results(results, title="결과"):
    """결과 출력"""
    print(f"\n{'='*70}")
    print(f"📊 {title}")
    print(f"{'='*70}")
    
    for i, (method_name, embedding, metadata) in enumerate(
        zip(results['ids'], results['embeddings'], results['metadatas'])
    ):
        print(f"\n{i+1}. {metadata['method_name']}")
        print(f"   차원: {metadata['vec_dim']}D")
        print(f"   Pearson r: {metadata['pearson_r']:.4f}")
        print(f"   Spearman r: {metadata['spearman_r']:.4f}")
        print(f"   벡터 길이: {len(embedding)}")

def print_similarity_results(results, title="유사도 검색 결과"):
    """유사도 검색 결과 출력"""
    print(f"\n{'='*70}")
    print(f"📊 {title}")
    print(f"{'='*70}")
    
    for i, (method_id, embedding, metadata, distance) in enumerate(
        zip(results['ids'], results['embeddings'], results['metadatas'], results['distances'])
    ):
        similarity = 1 - distance  # 거리를 유사도로 변환
        print(f"\n{i+1}. {metadata['method_name']}")
        print(f"   거리 (Cosine Distance): {distance:.6f}")
        print(f"   유사도 (Cosine Similarity): {similarity:.6f}")
        print(f"   Pearson r: {metadata['pearson_r']:.4f}")
        print(f"   Spearman r: {metadata['spearman_r']:.4f}")

if __name__ == "__main__":
    print("🔍 ChromaDB 로드 및 유사도 검색 예시\n")
    
    # ===================== 1. 모든 결과 로드 =====================
    print("예시 1️⃣: 모든 저장된 결과 로드")
    all_results = load_all_results()
    print(f"✓ 총 {len(all_results['ids'])}개 방법 로드 완료\n")
    print(f"방법들: {[m['method_name'] for m in all_results['metadatas'][:5]]}...")
    
    # ===================== 2. 특정 method 조회 =====================
    print("\n예시 2️⃣: 특정 method 조회 (Weighted Histogram)")
    weighted_result = get_method_by_name("Weighted Histogram")
    if weighted_result['ids']:
        print_results(weighted_result, "Weighted Histogram 조회")
    else:
        print("⚠️  해당 방법을 찾을 수 없습니다")
    
    # ===================== 3. 유사도 검색 =====================
    print("\n예시 3️⃣: 유사한 method 찾기")
    # Weighted Histogram의 벡터를 이용해 유사한 방법들 찾기
    if weighted_result['embeddings']:
        query_vec = weighted_result['embeddings'][0]
        similar = query_similar_methods(query_vec, top_k=5)
        print_similarity_results(similar, "Weighted Histogram과 유사한 방법들 (상위 5개)")
    
    # ===================== 4. 수동으로 벡터 만들어서 검색 =====================
    print("\n예시 4️⃣: 임의의 벡터로 검색")
    # 임의의 쿼리 벡터 생성 (예: 모두 0.5 값)
    num_features = len(all_results['embeddings'][0])
    custom_query = [0.5] * num_features
    custom_similar = query_similar_methods(custom_query, top_k=3)
    print_similarity_results(custom_similar, "임의 벡터와 유사한 방법들 (상위 3개)")
    
    # ===================== 5. 두 벡터 사이의 유사도 수동 계산 =====================
    print("\n예시 5️⃣: 두 method 사이의 코사인 유사도 계산")
    if len(all_results['embeddings']) >= 2:
        vec1 = all_results['embeddings'][0]
        vec2 = all_results['embeddings'][1]
        sim = calculate_cosine_similarity(vec1, vec2)
        print(f"{all_results['metadatas'][0]['method_name']} <-> {all_results['metadatas'][1]['method_name']}")
        print(f"코사인 유사도: {sim:.6f}")
    
    # ===================== 6. 최고 성능 method 찾기 =====================
    print("\n예시 6️⃣: 최고 성능 method (Pearson r 기준)")
    best_idx = np.argmax([m['pearson_r'] for m in all_results['metadatas']])
    best_method = all_results['metadatas'][best_idx]
    print(f"🏆 {best_method['method_name']}")
    print(f"   Pearson r: {best_method['pearson_r']:.4f}")
    print(f"   Spearman r: {best_method['spearman_r']:.4f}")
    
    # ===================== 7. 평균 성능 계산 =====================
    print("\n예시 7️⃣: 평균 성능 통계")
    pearson_values = [m['pearson_r'] for m in all_results['metadatas']]
    spearman_values = [m['spearman_r'] for m in all_results['metadatas']]
    
    print(f"Pearson r - 평균: {np.mean(pearson_values):.4f}, 표준편차: {np.std(pearson_values):.4f}")
    print(f"Spearman r - 평균: {np.mean(spearman_values):.4f}, 표준편차: {np.std(spearman_values):.4f}")
    
    # ===================== 8. 특정 성능 범위의 method 필터링 =====================
    print("\n예시 8️⃣: Pearson r < -0.7인 method들 (강한 음의 상관)")
    strong_methods = [m['method_name'] for m in all_results['metadatas'] if m['pearson_r'] < -0.7]
    print(f"총 {len(strong_methods)}개:")
    for method in strong_methods:
        print(f"  - {method}")
    
    print("\n" + "="*70)
    print("✅ 모든 예시 완료!")
    print("="*70)
