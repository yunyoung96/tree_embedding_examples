"""
트리 임베딩 알고리즘 모듈
모든 임베딩 방법과 실험 함수 포함
"""
import torch
import random
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from itertools import combinations
import torch.nn.functional as F
from scipy import stats
from transformers import AutoTokenizer, AutoModel
import warnings

warnings.filterwarnings('ignore')

from .tree_utils import (
    tree_to_sequence, compute_edit_distance, count_nodes, normalize_tree,
    precompute_branch_vectors, compute_branch_distance_from_vectors, random_tree
)

# ==================== DEBUG TRACING 시스템 ====================
class DebugTracer:
    """함수 호출 깊이를 추적하여 들여쓰기된 로그 출력"""
    def __init__(self):
        self.depth = 0
    
    def log(self, stage, func_name, file_name, var_name, var_value):
        """
        디버그 로그 출력
        형식: (함수이름, 파일위치, stage, 변수명=값)
        """
        indent = "  " * self.depth
        print(f"{indent}[{func_name}({file_name})] {stage} | {var_name}={var_value}")
    
    def enter(self, func_name):
        """함수 진입 시 호출"""
        indent = "  " * self.depth
        print(f"{indent}→ {func_name}")
        self.depth += 1
    
    def exit(self, func_name):
        """함수 종료 시 호출"""
        self.depth -= 1

_debug_tracer = DebugTracer()



# ==================== 방법 1: Tree Kernel 기반 임베딩 ====================
def count_subtrees(tree, depth_limit=5):
    """트리의 부분 트리 구조를 특징으로 변환"""
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


def tree_kernel_embedding(trees, max_features=128):
    """트리 커널 기반 임베딩"""
    feature_to_idx = {}
    tree_features = []
    
    for tree in trees:
        features = count_subtrees(tree)
        tree_features.append(features)
        for feat in features:
            if feat not in feature_to_idx:
                feature_to_idx[feat] = len(feature_to_idx)
    
    embeddings = []
    for features in tree_features:
        vec = np.zeros(len(feature_to_idx))
        for feat, count in features.items():
            vec[feature_to_idx[feat]] = count
        embeddings.append(vec)
    
    from sklearn.decomposition import PCA
    embeddings = np.array(embeddings)
    n_components = min(embeddings.shape[0]-1, embeddings.shape[1], max_features)
    if n_components > 0 and embeddings.shape[1] > max_features:
        pca = PCA(n_components=n_components)
        embeddings = pca.fit_transform(embeddings)
    
    return torch.tensor(embeddings, dtype=torch.float32)


# ==================== 방법 2: Recursive Decomposition ====================
def recursive_tree_embedding(tree, embed_dim=128, depth=0, max_depth=8):
    """트리를 재귀적으로 분해하여 임베딩 생성"""
    node_label, children = tree
    label_hash = hash(node_label) % 97
    
    node_feat = np.zeros(embed_dim)
    node_feat[0] = depth / max_depth
    node_feat[1] = len(children) / 5
    node_feat[2 + (label_hash % (embed_dim-2))] = 1.0
    
    if not children or depth >= max_depth:
        return node_feat
    
    child_embeds = np.array([recursive_tree_embedding(c, embed_dim, depth+1, max_depth) for c in children])
    child_mean = child_embeds.mean(axis=0)
    child_max = child_embeds.max(axis=0)
    combined = (node_feat + child_mean + 0.5 * child_max) / 2.5
    combined = combined / (np.linalg.norm(combined) + 1e-8)
    
    return combined


# ==================== 방법 3: Structural Hashing ====================
def structural_hash_embedding(tree, embed_dim=128):
    """트리의 구조를 해시 함수로 변환"""
    def tree_hash(node, depth=0):
        n_label, children = node
        if not children:
            return hash((n_label, 0, depth)) % 256
        child_hashes = tuple(sorted([tree_hash(c, depth+1) for c in children]))
        return hash((n_label, child_hashes, depth)) % 256
    
    vec = np.zeros(embed_dim)
    h = tree_hash(tree)
    for i in range(embed_dim):
        h = (h * 2654435761) % 2**32
        vec[i] = (h % 256) / 256.0
    
    return vec / (np.linalg.norm(vec) + 1e-8)


# ==================== 방법 4: Edit Distance MDS ====================
def edit_distance_embedding(trees):
    """Edit Distance 기반 MDS 임베딩"""
    n = len(trees)
    dist_matrix = np.zeros((n, n))
    for i in range(n):
        for j in range(i+1, n):
            d = compute_edit_distance(trees[i], trees[j])
            dist_matrix[i, j] = d
            dist_matrix[j, i] = d
    
    from sklearn.manifold import MDS
    mds = MDS(n_components=128, dissimilarity='precomputed')
    embeddings = mds.fit_transform(dist_matrix)
    return torch.tensor(embeddings, dtype=torch.float32)


# ==================== 방법 5: Fixed Vocabulary ====================
def build_vocabulary_from_trees(trees, max_vocab=300):
    """기존 트리들에서 vocabulary 구축"""
    vocab = {}
    for tree in trees:
        features = count_subtrees(tree)
        for feat, count in features.items():
            vocab[feat] = vocab.get(feat, 0) + count
    
    sorted_vocab = sorted(vocab.items(), key=lambda x: x[1], reverse=True)
    return {feat: i for i, (feat, _) in enumerate(sorted_vocab[:max_vocab])}


def fixed_vocab_tree_embedding(tree, vocab):
    """고정 vocabulary로 embedding"""
    features = count_subtrees(tree)
    vec = np.zeros(len(vocab))
    for feat, count in features.items():
        if feat in vocab:
            vec[vocab[feat]] = count
    
    norm = np.linalg.norm(vec)
    if norm > 1e-8:
        vec = vec / norm
    else:
        vec = np.ones(len(vocab)) / np.sqrt(len(vocab))
    
    return vec


# ==================== 방법 6-21: 추가 임베딩 방법들 ====================
def positional_tree_encoding(tree, embed_dim=256):
    """경로 기반 임베딩"""
    vec = np.zeros(embed_dim)
    path_hashes = []
    
    def dfs(node, path):
        n_label, children = node
        path_hash = hash(tuple(path + [n_label])) % (embed_dim // 2)
        path_hashes.append(path_hash)
        for i, child in enumerate(children):
            dfs(child, path + [f"{n_label}_{i}"])
    
    dfs(tree, [])
    for ph in path_hashes:
        vec[ph] += 1.0
        vec[(ph + 1) % embed_dim] += 0.5
    
    return vec / (np.linalg.norm(vec) + 1e-8)


def hierarchical_tree_embedding(tree, embed_dim=256, max_depth=10):
    """계층적 임베딩"""
    vec = np.zeros(embed_dim)
    level_info = [[] for _ in range(max_depth)]
    
    def dfs(node, depth):
        n_label, children = node
        if depth >= max_depth:
            return
        level_info[depth].append({'label': n_label, 'num_children': len(children)})
        for child in children:
            dfs(child, depth + 1)
    
    dfs(tree, 0)
    for depth in range(max_depth):
        if level_info[depth]:
            num_nodes = len(level_info[depth])
            avg_children = np.mean([info['num_children'] for info in level_info[depth]])
            idx_base = (depth * embed_dim) // max_depth
            if idx_base < embed_dim:
                vec[idx_base] = num_nodes / 10.0
            if idx_base + 1 < embed_dim:
                vec[idx_base + 1] = avg_children / 5.0
    
    return vec / (np.linalg.norm(vec) + 1e-8)


def contextualized_tree_embedding(tree, embed_dim=256):
    """컨텍스트 기반 임베딩"""
    vec = np.zeros(embed_dim)
    node_contexts = []
    
    def dfs(node, parent_info, sibling_count):
        n_label, children = node
        context = (hash(n_label) % 97, hash(parent_info) % 97 if parent_info else 0, sibling_count, len(children))
        node_contexts.append(context)
        for i, child in enumerate(children):
            dfs(child, n_label, len(children))
    
    dfs(tree, None, 0)
    for ctx in node_contexts:
        h = hash(ctx) % embed_dim
        vec[h] += 1.0
    
    total_nodes = len(node_contexts)
    vec[0] = total_nodes / 50.0
    vec[1] = total_nodes / np.log(total_nodes + 2)
    
    return vec / (np.linalg.norm(vec) + 1e-8)


def tree_string_encoding(tree, embed_dim=256):
    """문자열 기반 임베딩"""
    seq = tree_to_sequence(*tree)
    vec = np.zeros(embed_dim)
    
    for i, char in enumerate(seq):
        h = (hash(char) + i * 7) % embed_dim
        vec[h] += 1.0
    
    vec[0] = len(seq) / 100.0
    return vec / (np.linalg.norm(vec) + 1e-8)


def dfs_path_encoding(tree, embed_dim=256):
    """DFS 경로 기반 임베딩"""
    paths = []
    
    def dfs(node, path):
        n_label, children = node
        paths.append((n_label, tuple(path)))
        for i, child in enumerate(children):
            dfs(child, path + [f"{n_label}_{i}"])
    
    dfs(tree, [])
    
    vec = np.zeros(embed_dim)
    for label, path in paths:
        path_hash = hash(path) % embed_dim
        label_hash = hash(label) % embed_dim
        vec[path_hash] += 1.0
        vec[label_hash] += 0.5
    
    vec[0] = len(paths) / 50.0
    return vec / (np.linalg.norm(vec) + 1e-8)


def node_degree_encoding(tree, embed_dim=256):
    """노드 차수 기반 임베딩"""
    degrees = []
    
    def dfs(node):
        n_label, children = node
        degrees.append(len(children))
        for child in children:
            dfs(child)
    
    dfs(tree)
    
    vec = np.zeros(embed_dim)
    if degrees:
        for deg in degrees:
            idx = min(deg, embed_dim - 1)
            vec[idx] += 1.0
        vec[0] = np.mean(degrees) / 5.0
        vec[1] = np.std(degrees) / 5.0 if len(degrees) > 1 else 0
        vec[2] = max(degrees) / 10.0
        vec[3] = len(degrees) / 50.0
    
    return vec / (np.linalg.norm(vec) + 1e-8)


def subtree_histogram_encoding(tree, embed_dim=256):
    """서브트리 히스토그램 임베딩"""
    subtree_counts = {}
    
    def count_subtrees_local(node):
        n_label, children = node
        subtree_counts[n_label] = subtree_counts.get(n_label, 0) + 1
        for child in children:
            count_subtrees_local(child)
    
    count_subtrees_local(tree)
    
    vec = np.zeros(embed_dim)
    for label, count in subtree_counts.items():
        h = hash(label) % embed_dim
        vec[h] += count / 10.0
    
    total_nodes = sum(subtree_counts.values())
    vec[0] = total_nodes / 50.0
    vec[1] = len(subtree_counts) / 20.0
    
    return vec / (np.linalg.norm(vec) + 1e-8)


def multi_level_aggregation(tree, embed_dim=256, num_levels=5):
    """다중 레벨 집계 임베딩"""
    vec = np.zeros(embed_dim)
    
    def dfs_with_level(node, level):
        n_label, children = node
        level_idx = min(level, num_levels - 1) * (embed_dim // num_levels)
        h = (hash(n_label) + level) % (embed_dim // num_levels)
        if level_idx + h < embed_dim:
            vec[level_idx + h] += 1.0
        for child in children:
            dfs_with_level(child, level + 1)
    
    dfs_with_level(tree, 0)
    return vec / (np.linalg.norm(vec) + 1e-8)


def tree_signature_encoding(tree, embed_dim=256):
    """트리 시그니처 임베딩"""
    vec = np.zeros(embed_dim)
    
    def get_tree_metrics(node):
        n_label, children = node
        if not children:
            return 1, 0, 1, 0
        child_metrics = [get_tree_metrics(c) for c in children]
        sizes = [m[0] for m in child_metrics]
        heights = [m[1] for m in child_metrics]
        
        total_size = 1 + sum(sizes)
        max_height = 1 + max(heights)
        max_width = max(len(children), max([m[2] for m in child_metrics]))
        imbalance = np.std(sizes) / (np.mean(sizes) + 1e-8)
        
        return total_size, max_height, max_width, imbalance
    
    size, height, width, imbalance = get_tree_metrics(tree)
    
    vec[0] = size / 50.0
    vec[1] = height / 20.0
    vec[2] = width / 20.0
    vec[3] = imbalance / 5.0
    if height > 0:
        vec[4] = size / (height * width + 1)
    
    repetitions = embed_dim // 5
    for i in range(1, repetitions):
        vec[5*i:5*(i+1)] = vec[:5]
    
    return vec / (np.linalg.norm(vec) + 1e-8)


def random_walk_encoding(tree, embed_dim=256, num_walks=10):
    """무작위 보행 임베딩"""
    vec = np.zeros(embed_dim)
    adj_list = {}
    
    def build_adj(node, parent=None):
        n_label, children = node
        node_id = id(node)
        if node_id not in adj_list:
            adj_list[node_id] = []
        if parent is not None:
            adj_list[node_id].append(parent)
            parent_id = id(parent)
            if parent_id not in adj_list:
                adj_list[parent_id] = []
            adj_list[parent_id].append(node)
        
        for child in children:
            build_adj(child, node)
    
    build_adj(tree)
    
    all_nodes = list(adj_list.keys())
    if len(all_nodes) > 0:
        for _ in range(num_walks):
            current = random.choice(all_nodes)
            walk = [current]
            for _ in range(5):
                neighbors = adj_list.get(current, [])
                if neighbors:
                    current = id(random.choice(neighbors))
                    walk.append(current)
            walk_hash = hash(tuple(walk)) % embed_dim
            vec[walk_hash] += 1.0
    
    return vec / (np.linalg.norm(vec) + 1e-8)


def siamese_pattern_encoding(tree, embed_dim=256):
    """Siamese 패턴 임베딩"""
    vec = np.zeros(embed_dim)
    
    def get_structure_pattern(node):
        n_label, children = node
        if not children:
            return f"L:{n_label}"
        child_patterns = sorted([get_structure_pattern(c) for c in children])
        return f"N:{n_label}(" + ",".join(child_patterns) + ")"
    
    pattern = get_structure_pattern(tree)
    for i in range(0, len(pattern), 10):
        chunk = pattern[i:i+10]
        h = hash(chunk) % embed_dim
        vec[h] += 1.0
    
    vec[0] = len(pattern.split(":")) / 50.0
    return vec / (np.linalg.norm(vec) + 1e-8)


def weighted_subtree_histogram_encoding(tree, embed_dim=256):
    """가중치가 적용된 서브트리 히스토그램"""
    subtree_counts = {}
    
    def count_subtrees_weighted(node, depth=0, weight_factor=1.0):
        n_label, children = node
        depth_weight = weight_factor / (1.0 + depth * 0.3)
        key = (n_label, depth)
        subtree_counts[key] = subtree_counts.get(key, 0) + depth_weight
        for child in children:
            count_subtrees_weighted(child, depth + 1, weight_factor)
    
    count_subtrees_weighted(tree)
    
    vec = np.zeros(embed_dim)
    for (label, depth), count in subtree_counts.items():
        h = (hash(label) + depth * 7) % embed_dim
        vec[h] += count / 10.0
    
    total_weighted = sum(subtree_counts.values())
    vec[0] = total_weighted / 50.0
    vec[1] = len(subtree_counts) / 20.0
    
    return vec / (np.linalg.norm(vec) + 1e-8)


def spectral_tree_encoding(tree, embed_dim=256):
    """스펙트럼 임베딩"""
    nodes = []
    
    def collect_nodes(node, parent_idx=-1):
        idx = len(nodes)
        nodes.append((node, parent_idx))
        n_label, children = node
        for child in children:
            collect_nodes(child, idx)
    
    collect_nodes(tree)
    n = len(nodes)
    
    deg = np.zeros(n)
    adj = np.zeros((n, n))
    
    for i, (node, parent_idx) in enumerate(nodes):
        n_label, children = node
        child_count = len(children)
        deg[i] = child_count
        if parent_idx >= 0:
            adj[i, parent_idx] = 1
            adj[parent_idx, i] = 1
            deg[i] += 1
            deg[parent_idx] += 1
    
    L = np.diag(deg) - adj
    
    try:
        eigenvalues = np.linalg.eigvalsh(L)
        eigenvalues = np.sort(np.abs(eigenvalues))
    except:
        eigenvalues = np.zeros(n)
    
    vec = np.zeros(embed_dim)
    for i, ev in enumerate(eigenvalues[:embed_dim]):
        vec[i] = ev / (np.linalg.norm(eigenvalues) + 1e-8)
    
    return vec / (np.linalg.norm(vec) + 1e-8)


def attention_tree_encoding(tree, embed_dim=256):
    """Attention 기반 임베딩"""
    vec = np.zeros(embed_dim)
    node_contexts = []
    
    def dfs_with_attention(node, parent_depth=0):
        n_label, children = node
        
        if children:
            child_scores = np.ones(len(children))
            for i, child in enumerate(children):
                c_label, c_children = child
                child_scores[i] = 1.0 + len(c_children) * 0.3
            
            attention_weights = child_scores / (child_scores.sum() + 1e-8)
            
            for i, (child, attn_weight) in enumerate(zip(children, attention_weights)):
                ctx_key = (hash(n_label), hash(child[0]), attn_weight)
                node_contexts.append(ctx_key)
        
        ctx = (hash(n_label), parent_depth, len(children))
        node_contexts.append(ctx)
        
        for child in children:
            dfs_with_attention(child, parent_depth + 1)
    
    dfs_with_attention(tree)
    
    for ctx in node_contexts:
        h = hash(ctx) % embed_dim
        vec[h] += 1.0
    
    vec[0] = len(node_contexts) / 50.0
    return vec / (np.linalg.norm(vec) + 1e-8)


def tree_lstm_encoding(tree, embed_dim=256):
    """Tree LSTM 스타일 임베딩"""
    vec = np.zeros(embed_dim)
    
    def dfs_lstm_style(node, depth=0, branch_idx=0):
        n_label, children = node
        i_feat = (hash(n_label) + depth * 31) % (embed_dim // 2)
        vec[i_feat] += 1.0
        
        if not children:
            return np.zeros(embed_dim // 4)
        
        child_features = []
        for i, child in enumerate(children):
            child_feat = dfs_lstm_style(child, depth + 1, i)
            child_features.append(child_feat)
        
        if child_features:
            child_features = np.array(child_features)
            child_avg = np.mean(np.abs(child_features), axis=0)
            for j in range(min(len(child_avg), embed_dim // 4)):
                if child_avg[j] > 0.1:
                    vec[(depth * embed_dim // 4 + j) % embed_dim] += child_avg[j]
        
        return np.ones(embed_dim // 4) * (len(children) / 5.0)
    
    dfs_lstm_style(tree)
    return vec / (np.linalg.norm(vec) + 1e-8)


def hyperbolic_tree_encoding(tree, embed_dim=256, curvature=-1.0):
    """Hyperbolic 임베딩"""
    c = abs(curvature)
    
    def tree_to_hyperbolic_embeddings(node, depth=0, parent_pos=None):
        n_label, children = node
        radial = np.tanh(depth / (np.sqrt(c) + 1e-8)) if depth > 0 else 0.0
        
        label_hash = hash(n_label) % embed_dim
        angle = (label_hash / embed_dim) * 2 * np.pi
        
        node_embedding = np.zeros(embed_dim)
        node_embedding[0] = radial
        
        for i in range(1, min(embed_dim, int(embed_dim * 0.3))):
            node_embedding[i] = np.sin(angle + i * 0.1) * (1 - radial)
            node_embedding[i + int(embed_dim * 0.3)] = np.cos(angle + i * 0.1) * (1 - radial)
        
        child_embeddings = []
        if children:
            for child_idx, child in enumerate(children):
                child_emb = tree_to_hyperbolic_embeddings(child, depth + 1, node_embedding)
                child_embeddings.append(child_emb)
        
        if child_embeddings:
            child_mean = np.mean(child_embeddings, axis=0)
            node_embedding += child_mean * 0.3
        
        norm = np.linalg.norm(node_embedding)
        if norm > 0.99:
            node_embedding = node_embedding / (norm / 0.95)
        
        return node_embedding
    
    root_emb = tree_to_hyperbolic_embeddings(tree)
    vec = np.zeros(embed_dim)
    vec[:len(root_emb)] = root_emb
    
    return vec / (np.linalg.norm(vec) + 1e-8)


def bert_embedding(model_name, trees):
    """BERT 모델 임베딩"""
    seqs = [tree_to_sequence(*tree) for tree in trees]
    try:
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModel.from_pretrained(model_name)
        model.eval()
        
        if torch.backends.mps.is_available():
            model = model.to('cpu')
        
        inputs = tokenizer(seqs, return_tensors="pt", truncation=True, max_length=512, padding=True)
        
        with torch.no_grad():
            outputs = model(**inputs)
            tree_vecs = outputs.last_hidden_state[:, 0, :]
        
        del model
        torch.cuda.empty_cache() if torch.cuda.is_available() else None
        
        return tree_vecs
    except Exception as e:
        return None


def get_tree_embedding(method_name, trees, vocab=None):
    """임베딩 함수 선택"""
    embed_dim = 128
    
    embedding_map = {
        "Recursive Decomposition": lambda t: torch.tensor(np.array([recursive_tree_embedding(x, embed_dim=embed_dim) for x in t]), dtype=torch.float32),
        "Fixed Vocab Tree Kernel": lambda t: torch.tensor(np.array([fixed_vocab_tree_embedding(x, vocab) for x in t]), dtype=torch.float32),
        "Positional Encoding": lambda t: torch.tensor(np.array([positional_tree_encoding(x, embed_dim=embed_dim) for x in t]), dtype=torch.float32),
        "Hierarchical Encoding": lambda t: torch.tensor(np.array([hierarchical_tree_embedding(x, embed_dim=embed_dim) for x in t]), dtype=torch.float32),
        "Contextualized Embedding": lambda t: torch.tensor(np.array([contextualized_tree_embedding(x, embed_dim=embed_dim) for x in t]), dtype=torch.float32),
        "Tree String Encoding": lambda t: torch.tensor(np.array([tree_string_encoding(x, embed_dim=embed_dim) for x in t]), dtype=torch.float32),
        "DFS Path Encoding": lambda t: torch.tensor(np.array([dfs_path_encoding(x, embed_dim=embed_dim) for x in t]), dtype=torch.float32),
        "Node Degree Statistics": lambda t: torch.tensor(np.array([node_degree_encoding(x, embed_dim=embed_dim) for x in t]), dtype=torch.float32),
        "Subtree Histogram": lambda t: torch.tensor(np.array([subtree_histogram_encoding(x, embed_dim=embed_dim) for x in t]), dtype=torch.float32),
        "Multi-Level Aggregation": lambda t: torch.tensor(np.array([multi_level_aggregation(x, embed_dim=embed_dim) for x in t]), dtype=torch.float32),
        "Tree Signature": lambda t: torch.tensor(np.array([tree_signature_encoding(x, embed_dim=embed_dim) for x in t]), dtype=torch.float32),
        "Random Walk": lambda t: torch.tensor(np.array([random_walk_encoding(x, embed_dim=embed_dim) for x in t]), dtype=torch.float32),
        "Siamese Pattern": lambda t: torch.tensor(np.array([siamese_pattern_encoding(x, embed_dim=embed_dim) for x in t]), dtype=torch.float32),
        "Weighted Histogram": lambda t: torch.tensor(np.array([weighted_subtree_histogram_encoding(x, embed_dim=embed_dim) for x in t]), dtype=torch.float32),
        "Spectral Encoding": lambda t: torch.tensor(np.array([spectral_tree_encoding(x, embed_dim=embed_dim) for x in t]), dtype=torch.float32),
        "Attention Encoding": lambda t: torch.tensor(np.array([attention_tree_encoding(x, embed_dim=embed_dim) for x in t]), dtype=torch.float32),
        "Tree LSTM": lambda t: torch.tensor(np.array([tree_lstm_encoding(x, embed_dim=embed_dim) for x in t]), dtype=torch.float32),
        "Hyperbolic Embedding": lambda t: torch.tensor(np.array([hyperbolic_tree_encoding(x, embed_dim=embed_dim) for x in t]), dtype=torch.float32),
    }
    return embedding_map.get(method_name, lambda t: bert_embedding(method_name, t) if method_name.startswith("bert-") or method_name.startswith("distilbert-") or method_name == "roberta-base" else None)


def run_experiment(method_name, trees, method_type="tree", vocab=None):
    """통합 실험 함수"""
    import time
    start_time = time.time()
    
    try:
        # Step 1: 임베딩 생성
        step1_start = time.time()
        if method_type == "tree":
            embed_fn = get_tree_embedding(method_name, trees, vocab)
            tree_vecs = embed_fn(trees)
            if tree_vecs is None:
                return None
        else:
            tree_vecs = bert_embedding(method_name, trees)
            if tree_vecs is None:
                return None
        step1_time = time.time() - step1_start
        
        # Step 2: 벡터 정규화 및 유사도 계산
        step2_start = time.time()
        vec_dim = tree_vecs.shape[1]
        normed = F.normalize(tree_vecs, p=2, dim=1)
        sim_matrix = torch.mm(normed, normed.t())
        step2_time = time.time() - step2_start
        
        # Step 3: Edit Distance 계산
        step3_start = time.time()
        edit_dists, cos_sims = [], []
        num_pairs = len(list(combinations(range(len(trees)), 2)))
        for idx, (i, j) in enumerate(combinations(range(len(trees)), 2)):
            ed = compute_edit_distance(trees[i], trees[j])
            cs = sim_matrix[i, j].item()
            edit_dists.append(ed)
            cos_sims.append(cs)
        step3_time = time.time() - step3_start
        
        # Step 4: 상관계수 계산
        step4_start = time.time()
        pearson_r, _ = stats.pearsonr(edit_dists, cos_sims)
        spearman_r, _ = stats.spearmanr(edit_dists, cos_sims)
        step4_time = time.time() - step4_start
        
        total_time = time.time() - start_time
        
        return {
            'name': method_name,
            'type': method_type,
            'vec_dim': vec_dim,
            'edit_dists': edit_dists,
            'cos_sims': cos_sims,
            'pearson_r': pearson_r,
            'spearman_r': spearman_r,
            'timing': {
                'embedding': step1_time,
                'normalize': step2_time,
                'edit_distance': step3_time,
                'correlation': step4_time,
                'total': total_time
            }
        }
    except Exception as e:
        return None


def save_heatmap(result, source='random', output_dir=None):
    """
    결과를 히트맵으로 PNG에 저장
    
    Args:
        result: 실험 결과 dict
        source: 데이터 소스 ('random' 또는 'ast')
        output_dir: 출력 디렉토리 (None이면 현재 디렉토리)
    """
    plt.figure(figsize=(9, 6))
    edit_dists = result['edit_dists']
    cos_sims = result['cos_sims']
    
    h, xedges, yedges = np.histogram2d(edit_dists, cos_sims, bins=15)
    ax = sns.heatmap(h.T, cmap="viridis", cbar_kws={'label': 'Pair Count'})
    
    num_xticks = 6
    xtick_indices = np.linspace(0, len(xedges)-2, num_xticks, dtype=int)
    xtick_pos = np.array(xtick_indices) + 0.5
    xtick_labels = [f"{xedges[i]:.0f}" for i in xtick_indices]
    ax.set_xticks(xtick_pos)
    ax.set_xticklabels(xtick_labels, rotation=0)
    
    num_yticks = 6
    ytick_indices = np.linspace(0, len(yedges)-2, num_yticks, dtype=int)
    ytick_pos = np.array(ytick_indices) + 0.5
    ytick_labels = [f"{yedges[i]:.3f}" for i in ytick_indices]
    ax.set_yticks(ytick_pos)
    ax.set_yticklabels(ytick_labels, rotation=0)
    
    ax.set_xlabel("Tree Edit Distance")
    ax.set_ylabel("Cosine Similarity")
    title = f"{result['name']} ({result['vec_dim']}D)\nr={result['pearson_r']:.4f}"
    ax.set_title(title)
    
    # 소스에 따라 파일명 구분
    source_prefix = f"{source}_" if source else ""
    filename = f"result_{source_prefix}{result['name'].replace('/', '_').replace(' ', '_')}.png"
    
    # 디렉토리 경로 포함
    if output_dir:
        import os
        filepath = os.path.join(output_dir, filename)
    else:
        filepath = filename
    
    plt.savefig(filepath, dpi=100, bbox_inches='tight')
    plt.close()


# ==================== Binary Branch Distance 실험 (논문 기반) ====================
def run_binary_branch_distance_experiment(trees, q=2, cached_distances=None):
    """Binary Branch Distance 계산 (q-level 지원) - 벡터 사전 계산 및 캐시 지원
    
    Args:
        trees: 비교할 트리 리스트
        q: q-level 파라미터
        cached_distances: {(i,j): edit_distance} 형태의 미리 계산된 edit distance dict
                         None이면 새로 계산
    """
    import time
    import logging
    logger = logging.getLogger(__name__)
    
    start_time = time.time()
    logger.debug(f"[Stage 1/4] Starting Binary Branch Distance experiment with q={q}, trees={len(trees)}")

    # 1단계: 모든 트리의 branch vectors 미리 계산
    logger.debug(f"[Stage 1/4] Precomputing branch vectors for {len(trees)} trees...")
    branch_vectors = precompute_branch_vectors(trees, q)
    logger.debug(f"[Stage 1/4] ✓ Branch vectors computed")
    
    # === 디버깅: branch vector 예시 출력 (상위 2개 트리만) ===
    logger.debug("[DEBUG] Example branch vectors (q=%d):" % q)
    for idx, bv in enumerate(branch_vectors[:2]):
        logger.debug(f"  Tree {idx}: {dict(list(bv.items())[:5])} ... (total {len(bv)} unique branches)")
    
    # Characteristic vector dimension 계산
    logger.debug("[Stage 1/4] Computing characteristic dimension...")
    all_unique_branches = set()
    for count in branch_vectors:
        all_unique_branches.update(count.keys())
    characteristic_dim = len(all_unique_branches)
    logger.debug(f"[Stage 1/4] ✓ Characteristic dimension: {characteristic_dim}")
    
    # 2단계: 쌍의 거리 계산 (저장된 벡터 사용 또는 캐시 사용)
    if cached_distances is not None:
        logger.info(f"[Stage 2/4] Using cached distances - skipping tree edit distance computation ({len(cached_distances)} pairs)")
    else:
        logger.info(f"[Stage 2/4] Computing pairwise distances (no cache found)...")
    logger.debug(f"[Stage 2/4] Processing {len(trees) * (len(trees) - 1) // 2} tree pairs...")
    
    edit_dists, approximate_dists, raw_bdists = [], [], []
    pair_indices = []  # 트리 쌍 인덱스 저장
    total_pairs = len(trees) * (len(trees) - 1) // 2
    for pair_count, (i, j) in enumerate(combinations(range(len(trees)), 2)):
        # 캐시된 거리가 있으면 사용, 없으면 계산
        if cached_distances is not None and (i, j) in cached_distances:
            ed = cached_distances[(i, j)]
        else:
            ed = compute_edit_distance(trees[i], trees[j])
        
        edit_dists.append(ed)
        norm_dist, raw_dist = compute_branch_distance_from_vectors(branch_vectors[i], branch_vectors[j], q)
        approximate_dists.append(norm_dist)
        raw_bdists.append(raw_dist)
        pair_indices.append((i, j))  # 트리 쌍 인덱스 저장
        
        if (pair_count + 1) % max(1, total_pairs // 5) == 0:
            logger.debug(f"[Stage 2/4] Progress: {pair_count + 1}/{total_pairs} pairs computed")
    logger.debug(f"[Stage 2/4] ✓ All {total_pairs} pairwise distances computed")
    
    # 3단계: 상관계수 계산
    logger.debug("[Stage 3/4] Computing correlation coefficients...")
    normalization = 4 * (q - 1) + 1
    pearson_r, _ = stats.pearsonr(edit_dists, approximate_dists)
    spearman_r, _ = stats.spearmanr(edit_dists, approximate_dists)
    pearson_r_raw, _ = stats.pearsonr(edit_dists, raw_bdists)
    spearman_r_raw, _ = stats.spearmanr(edit_dists, raw_bdists)
    logger.debug(f"[Stage 3/4] ✓ Correlations computed: Pearson={pearson_r_raw:.4f}, Spearman={spearman_r_raw:.4f}")
    
    # 4단계: 결과 반환
    logger.debug("[Stage 4/4] Preparing results...")
    total_time = time.time() - start_time
    logger.debug(f"[Stage 4/4] ✓ Total execution time: {total_time:.2f}s")
    logger.debug(f"[Stage 4/4] ✓ Binary Branch Distance experiment completed successfully")
    
    return {
        'q': q,
        'edit_dists': edit_dists,
        'raw_bdists': raw_bdists,
        'approximate_dists': approximate_dists,
        'pearson_r': pearson_r,
        'spearman_r': spearman_r,
        'pearson_r_raw': pearson_r_raw,
        'spearman_r_raw': spearman_r_raw,
        'normalization': normalization,
        'characteristic_dim': characteristic_dim,
        'timing': {'total': total_time},
        'trees': trees,  # 트리들 저장
        'pair_indices': pair_indices  # 쌍 인덱스 저장
    }


def print_binary_branch_distance_results(result):
    """핵심 결과만 출력"""
    if result is None:
        return
    q = result['q']
    norm = result['normalization']
    pairs = len(result['edit_dists'])
    r = result['pearson_r_raw']
    
    print(f"\n[q={q}] {pairs} pairs | Pearson r={r:.4f} | Norm={norm}")


def save_binary_branch_distance_plot(result, source='random', output_dir=None):
    """
    Binary Branch Distance 결과를 시각화 (2개 subplot을 1개 figure에)
    BDist_Q(T, T') ≤ [4×(q−1) + 1] × ED(T, T')를 2가지 방식으로 표현
    
    Args:
        result: Binary Branch Distance 실험 결과 dict
        source: 데이터 소스 ('random' 또는 'ast')
        output_dir: 출력 디렉토리 (None이면 현재 디렉토리)
    
    Returns:
        저장된 figure 파일명
    """
    import os
    
    # 데이터 준비
    x = np.array(result['edit_dists'])
    y = np.array(result['raw_bdists'])
    norm = result['normalization']
    
    # ===== 2개 subplot을 1개 figure에 배치 =====
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7))
    
    # ===== Subplot 1: BDist vs EDist (BDist ≤ norm×EDist) =====
    ax1.scatter(x, y, alpha=0.5, s=30, label='Observed BDist')
    
    # y=x 선 (reference)
    max_val = max(max(x), max(y))
    ax1.plot([0, max_val], [0, max_val], 'r--', linewidth=2, label='y=x')
    
    # y=norm*x 선 (bound line)
    ax1.plot([0, max_val/norm], [0, max_val], 'g--', linewidth=2, 
             label=f'y={norm}×x (Bound: BDist ≤ {norm}×EDist)')
    
    ax1.set_xlabel('Edit Distance (ED)', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Binary Branch Distance (BDist)', fontsize=12, fontweight='bold')
    ax1.set_title(f'Expression 1: BDist ≤ {norm}×EDist (q={result["q"]})', 
                   fontsize=12, fontweight='bold')
    ax1.legend(fontsize=10, loc='upper left')
    ax1.grid(True, alpha=0.3)
    
    # ===== Subplot 2: BDist/norm vs EDist (BDist/norm ≤ EDist) =====
    y_normalized = y / norm
    
    ax2.scatter(x, y_normalized, alpha=0.5, s=30, label=f'Observed BDist/{norm}')
    
    # y=x 선 (bound line)
    max_val2 = max(max(x), max(y_normalized))
    ax2.plot([0, max_val2], [0, max_val2], 'r--', linewidth=2, 
             label=f'y=x (Bound: BDist/{norm} ≤ EDist)')
    
    ax2.set_xlabel('Edit Distance (ED)', fontsize=12, fontweight='bold')
    ax2.set_ylabel(f'Normalized BDist / {norm}', fontsize=12, fontweight='bold')
    ax2.set_title(f'Expression 2: BDist/{norm} ≤ EDist (q={result["q"]})', 
                   fontsize=12, fontweight='bold')
    ax2.legend(fontsize=10, loc='upper left')
    ax2.grid(True, alpha=0.3)
    
    # 전체 제목
    fig.suptitle(f'Binary Branch Distance Bound Verification\nPearson r={result["pearson_r_raw"]:.4f}, Spearman ρ={result["spearman_r_raw"]:.4f}',
                 fontsize=13, fontweight='bold', y=1.02)
    
    plt.tight_layout()
    
    # 파일명 구성
    source_prefix = f"{source}_" if source else ""
    filename = f"bbdist_{source_prefix}q{result['q']}_bounds.png"
    filepath = os.path.join(output_dir, filename) if output_dir else filename
    fig.savefig(filepath, dpi=100, bbox_inches='tight')
    plt.close(fig)
    
    return filename


def check_lower_bound_violations(result):
    """
    논문의 lower bound 조건을 엄격하게 검사: Raw BDist >= ED
    
    Lower Bound (Theorem 3.1/3.2/3.3):
    - BDist(T1, T2) >= ED(T1, T2) (정규화 전, raw 거리)
    
    NOTE: 정규화된 거리는 correlation 계산용이므로 lower bound 검증 대상이 아님
    
    위반이 발생하면 AssertionError를 발생시켜 프로그램 강제 종료
    위반 트리들은 상세히 출력됨
    
    Args:
        result: run_binary_branch_distance_experiment 결과
    """
    edit_dists = np.array(result['edit_dists'])
    raw_bdists = np.array(result['raw_bdists'])
    approximate_dists = np.array(result['approximate_dists'])
    norm = result['normalization']
    q = result['q']
    trees = result.get('trees')
    pair_indices = result.get('pair_indices')
    
    print(f"\n  📋 [STRICT LOWER BOUND CHECK] q={q}")
    
    # 1. Raw BDist >= ED 검사 (주요 검증 항목)
    const = 4 * (q - 1) + 1
    violations_raw = const * edit_dists < raw_bdists
    n_violations_raw = np.sum(violations_raw)
    
    if n_violations_raw == 0:
        print(f"  ✓ Raw BDist >= ED: PASS (0/{len(edit_dists)} violations)")
    else:
        print(f"  ✗ Raw BDist >= ED: FAIL ({n_violations_raw}/{len(edit_dists)} violations)")
        if len(violations_raw) > 0 and np.any(violations_raw):
            violation_amounts = edit_dists[violations_raw] - raw_bdists[violations_raw]
            max_violation_amount = np.max(violation_amounts)
            print(f"    - Max violation amount: {max_violation_amount:.4f}")
            # 상위 3개 위반 항목 표시 (상세)
            top_indices = np.argsort(violation_amounts)[-3:][::-1]
            for idx, k in enumerate(top_indices):
                actual_idx = np.where(violations_raw)[0][k]
                ed = edit_dists[actual_idx]
                bd = raw_bdists[actual_idx]
                print(f"    - {idx+1}. Pair {actual_idx}: ED={ed:.1f}, BDist={bd:.1f}, Δ={ed-bd:.4f}")
                
                # 해당 트리 쌍 출력
                if trees and pair_indices:
                    tree_i_idx, tree_j_idx = pair_indices[actual_idx]
                    tree_i = trees[tree_i_idx]
                    tree_j = trees[tree_j_idx]
                    print(f"       └─ Tree {tree_i_idx}: {tree_i}")
                    print(f"       └─ Tree {tree_j_idx}: {tree_j}")
    
    # 2. 정규화된 거리는 상관계수 계산용 (참고정보만 제시)
    print(f"\n  ℹ  [정규화 거리 정보] (correlation 계산용, lower bound 대상 아님)")
    print(f"    - Normalization factor: {norm}")
    
    # 정규화된 거리의 분포 확인
    avg_normalized = np.mean(approximate_dists)
    avg_raw = np.mean(raw_bdists)
    print(f"    - Mean Raw BDist: {avg_raw:.2f}")
    print(f"    - Mean Normalized BDist: {avg_normalized:.2f} (= {avg_raw:.2f} / {norm})")
    print(f"    - Correlation (Pearson r): {result.get('pearson_r_raw', 0):.4f}")
    
    # 3. 거리 분포 통계
    print(f"\n  📊 거리 분포 통계:")
    print(f"    - Edit Distance:      min={np.min(edit_dists):.1f}, max={np.max(edit_dists):.1f}, mean={np.mean(edit_dists):.2f}")
    print(f"    - Raw BDist:          min={np.min(raw_bdists):.1f}, max={np.max(raw_bdists):.1f}, mean={np.mean(raw_bdists):.2f}")
    print(f"    - Normalized BDist:   min={np.min(approximate_dists):.1f}, max={np.max(approximate_dists):.1f}, mean={np.mean(approximate_dists):.2f}")
    
    # 4. 종합 결론
    if n_violations_raw == 0:
        print(f"\n  ✓✓ Lower Bound 조건 만족 ✓✓")
    else:
        print(f"\n  ✗✗ Lower Bound 위반 발생 - 알고리즘 검토 필요 ✗✗")
        raise AssertionError(
            f"[CRITICAL] Lower Bound Violation 감지!\n"
            f"  - q={q}, violations={n_violations_raw}/{len(edit_dists)}\n"
            f"  - Max violation: {np.max(edit_dists[violations_raw] - raw_bdists[violations_raw]):.4f}\n"
            f"  - 알고리즘 구현을 검토하고 수정해주세요."
        )
