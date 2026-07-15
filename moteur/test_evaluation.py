import time
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_prep import build_all
from matching import MatchingEngine
from evaluation import split_candidates, evaluate, evaluate_baselines

candidates, offers, ground_truth = build_all(cache=True)
train_ids, test_ids = split_candidates(candidates["candidate_id"], test_size=0.2, seed=42)
print(f"train={len(train_ids)} test={len(test_ids)}")

sample_test = test_ids[:500]

t0 = time.time()
results = evaluate_baselines(MatchingEngine, offers, candidates, ground_truth, sample_test)
print(f"baselines evaluated in {time.time()-t0:.1f}s on {len(sample_test)} test candidates\n")

import json
for name, metrics in results.items():
    print(name, json.dumps(metrics, indent=2))
