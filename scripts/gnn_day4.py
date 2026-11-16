import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.data import Data
from torch_geometric.nn import GCNConv, SAGEConv
from torch_geometric.utils import negative_sampling, train_test_split_edges
from sentence_transformers import SentenceTransformer
import networkx as nx
import pickle
import pandas as pd
import numpy as np
from sklearn.metrics import roc_auc_score, f1_score
import time

print("Loading data...")
with open("data/processed/day4_graph_dense.gpickle", "rb") as f:
    G = pickle.load(f)
articles_df = pd.read_json("data/processed/day4_articles_dense.json", lines=True)

# 1. Generate Text Embeddings
print("Generating text embeddings...")
embedder = SentenceTransformer('all-MiniLM-L6-v2')
texts = (articles_df['title'].fillna("") + " " + articles_df['text'].fillna("")).tolist()
embeddings = embedder.encode(texts, show_progress_bar=True)
x = torch.tensor(embeddings, dtype=torch.float)

# 2. Setup Node Mapping & Edge Index
node_list = sorted(G.nodes())
node_to_idx = {node: i for i, node in enumerate(node_list)}
edge_list = []
for u, v in G.edges():
    if u in node_to_idx and v in node_to_idx:
        edge_list.append([node_to_idx[u], node_to_idx[v]])

edge_index = torch.tensor(edge_list, dtype=torch.long).t().contiguous()

# 3. Create Data Object and Split Edges for Link Prediction
data = Data(x=x, edge_index=edge_index)
# train_test_split_edges splits edges into pos_train, pos_test and generates negative samples
data = train_test_split_edges(data)

# 4. GNN Encoder Class
class Net(torch.nn.Module):
    def __init__(self, in_channels, hidden_channels, out_channels, model_type="SAGE"):
        super(Net, self).__init__()
        ConvLayer = SAGEConv if model_type == "SAGE" else GCNConv
        self.conv1 = ConvLayer(in_channels, hidden_channels)
        self.conv2 = ConvLayer(hidden_channels, out_channels)

    def encode(self, x, edge_index):
        x = self.conv1(x, edge_index).relu()
        return self.conv2(x, edge_index)

    def decode(self, z, pos_edge_index, neg_edge_index):
        edge_index = torch.cat([pos_edge_index, neg_edge_index], dim=-1)
        # Dot product between node embeddings to calculate link probability
        logits = (z[edge_index[0]] * z[edge_index[1]]).sum(dim=-1)
        return logits

def get_link_labels(pos_edge_index, neg_edge_index):
    E = pos_edge_index.size(1) + neg_edge_index.size(1)
    link_labels = torch.zeros(E, dtype=torch.float)
    link_labels[:pos_edge_index.size(1)] = 1.
    return link_labels

# 5. Training and Comparison Loop
def run_experiment(model_type):
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model = Net(x.shape[1], 128, 64, model_type=model_type).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
    
    data_idx = data.to(device)
    
    start_time = time.time()
    for epoch in range(1, 101):
        model.train()
        optimizer.zero_grad()
        # Message passing uses training edges only, so validation/test edges stay unseen
        z = model.encode(data_idx.x, data_idx.train_pos_edge_index)
        
        # Binary cross-entropy on positive training edges and freshly sampled negatives (new negatives every epoch)
        neg_edge_index = negative_sampling(data_idx.train_pos_edge_index, num_nodes=data_idx.num_nodes)
        
        logits = model.decode(z, data_idx.train_pos_edge_index, neg_edge_index)
        labels = get_link_labels(data_idx.train_pos_edge_index, neg_edge_index).to(device)
        
        loss = F.binary_cross_entropy_with_logits(logits, labels)
        loss.backward()
        optimizer.step()
        
    inference_start = time.time()
    model.eval()
    with torch.no_grad():
        z = model.encode(data_idx.x, data_idx.train_pos_edge_index)
        results = model.decode(z, data_idx.test_pos_edge_index, data_idx.test_neg_edge_index)
        labels = get_link_labels(data_idx.test_pos_edge_index, data_idx.test_neg_edge_index)
        
        auc = roc_auc_score(labels.cpu(), results.cpu())
        preds = (results.sigmoid() > 0.5).float()
        f1 = f1_score(labels.cpu(), preds.cpu())
    
    inf_cost = (time.time() - inference_start) * 1000 # in ms
    print(f"{model_type} -> AUC: {auc:.4f}, F1: {f1:.4f}, Inf Cost: {inf_cost:.2f}ms")

print("\n=== Comparing Performance ===")
run_experiment("GCN")
run_experiment("SAGE")

torch.save(x, "data/processed/article_features.pt") 