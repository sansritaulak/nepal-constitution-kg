import networkx as nx
import pickle
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import LabelEncoder
import numpy as np
import random

# Load the graph
graph_path = "data/processed/constitution_graph.gpickle"
with open(graph_path, "rb") as f:
    G = pickle.load(f)

print(f"Loaded graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

# Encode node labels (Article, Part, Schedule, etc.) as numerical features
# This helps the model learn that Articles tend to link to specific types
label_encoder = LabelEncoder()
all_labels = [data.get('label', 'Unknown') for _, data in G.nodes(data=True)]
label_encoder.fit(all_labels)

def get_node_label_id(u):
    label = G.nodes[u].get('label', 'Unknown')
    return label_encoder.transform([label])[0]

# Generate samples
edges = list(G.edges())
nodes = list(G.nodes())
non_edges = []
random.seed(42)

# Generate negative samples
while len(non_edges) < len(edges):
    u, v = random.sample(nodes, 2)
    if u != v and not G.has_edge(u, v):
        non_edges.append((u, v))

# Feature extraction function
def compute_features(u, v):
    # Structural features
    cn = len(list(nx.common_neighbors(G, u, v)))
    
    # Jaccard
    jaccard = 0.0
    preds = nx.jaccard_coefficient(G, [(u, v)])
    for _, _, p in preds:
        jaccard = p
        
    # Preferential Attachment
    pref = 0.0
    preds = nx.preferential_attachment(G, [(u, v)])
    for _, _, p in preds:
        pref = p
        
    # Metadata features (Node types)
    u_label = get_node_label_id(u)
    v_label = get_node_label_id(v)
    
    return [cn, jaccard, pref, u_label, v_label]

X, y = [], []
for u, v in edges:
    X.append(compute_features(u, v))
    y.append(1)
for u, v in non_edges:
    X.append(compute_features(u, v))
    y.append(0)

X = np.array(X)
y = np.array(y)

# 2. Perform Triple Split (Train: 60%, Val: 20%, Test: 20%)
# First, split into Train and a 'Temporary' set (which will become Val + Test)
X_train, X_temp, y_train, y_temp = train_test_split(
    X, y, test_size=0.4, random_state=42, stratify=y
)

# Now, split the 'Temporary' set in half to get Validation and Test
X_val, X_test, y_val, y_test = train_test_split(
    X_temp, y_temp, test_size=0.5, random_state=42, stratify=y_temp
)

# 3. Train Model
model = LogisticRegression(max_iter=1000)
model.fit(X_train, y_train)

# 4. Evaluation Summary
def get_auc(features, labels):
    probs = model.predict_proba(features)[:, 1]
    return roc_auc_score(labels, probs)

train_auc = get_auc(X_train, y_train)
val_auc = get_auc(X_val, y_val)
test_auc = get_auc(X_test, y_test)

print("-" * 30)
print(f"SUMMARY SCORES (AUC)")
print("-" * 30)
print(f"Training AUC:   {train_auc:.4f} (The 'Learning' score)")
print(f"Validation AUC: {val_auc:.4f} (Used for tuning)")
print(f"Test AUC:       {test_auc:.4f} (The 'Final Exam' score)")
print("-" * 30)

# Predict on new candidates
sample_size = min(2000, len(non_edges))
sampled_candidates = random.sample(non_edges, sample_size)
predictions = []

for u, v in sampled_candidates:
    feat = np.array([compute_features(u, v)])
    prob = model.predict_proba(feat)[0][1]
    predictions.append((u, v, prob))

# Display Top 20
top_20 = sorted(predictions, key=lambda x: x[2], reverse=True)[:5]

print("\nTop 5 Predicted Missing References:")
print(f"{'Source Node':<30} | {'Target Node':<30} | Prob")
print("-" * 75)
for u, v, prob in top_20:
    # Get titles from node attributes
    u_title = G.nodes[u].get("title", "No title")
    v_title = G.nodes[v].get("title", "No title")
    
    # Format: Article:1 ('Title Name')
    u_display = f"{u} ('{u_title[:20]}...')" if len(u_title) > 20 else f"{u} ('{u_title}')"
    v_display = f"{v} ('{v_title[:20]}...')" if len(v_title) > 20 else f"{v} ('{v_title}')"
    
    print(f"{u_display:<30} | {v_display:<30} | {prob:.3f}")