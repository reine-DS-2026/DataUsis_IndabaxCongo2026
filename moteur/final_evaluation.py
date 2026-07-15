import time
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_prep import build_all
from matching import MatchingEngine, DEFAULT_WEIGHTS
from evaluation import evaluate

DONNEES_GENEREES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "donnees_generees")

import pandas as pd

candidates, offers, ground_truth = build_all(cache=True)
test_ids = pd.read_parquet(os.path.join(DONNEES_GENEREES, "split_test.parquet"))["candidate_id"].values
print("test set size:", len(test_ids))

engine = MatchingEngine(offers, candidates, weights=DEFAULT_WEIGHTS)

t0 = time.time()
metrics = evaluate(engine, test_ids, ground_truth, k_list=(5, 10))
print(f"evaluated full test set in {time.time()-t0:.1f}s")
print(json.dumps(metrics, indent=2))

with open(os.path.join(DONNEES_GENEREES, "evaluation_final.json"), "w") as f:
    json.dump({"weights": DEFAULT_WEIGHTS, "test_size": len(test_ids), "metrics": metrics}, f, indent=2)
print("\nsaved to donnees_generees/evaluation_final.json")
