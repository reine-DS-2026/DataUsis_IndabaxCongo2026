import time
import sys
import os
import json
import itertools

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_prep import build_all
from matching import MatchingEngine
from evaluation import evaluate

candidates, offers, ground_truth = build_all(cache=True)

import numpy as np
rng = np.random.RandomState(42)
ids = np.array(sorted(candidates["candidate_id"]))
rng.shuffle(ids)
n = len(ids)
n_test = int(n * 0.2)
n_val = int(n * 0.2)
test_ids = ids[:n_test]
val_ids = ids[n_test:n_test + n_val]
train_ids = ids[n_test + n_val:]
print(f"train={len(train_ids)} val={len(val_ids)} test={len(test_ids)}")

val_sample = val_ids[:800]

grid = []
for w_texte in [0.2, 0.4, 0.5, 0.6, 0.7, 0.8, 1.0]:
    remaining = round(1 - w_texte, 2)
    for split in [0.5]:
        w_sect = round(remaining * split, 2)
        w_struct = round(remaining - w_sect, 2)
        grid.append({"secteur_localisation": w_sect, "texte": w_texte, "structure": w_struct})
# add asymmetric splits too
for w_texte in [0.5, 0.6, 0.7]:
    remaining = round(1 - w_texte, 2)
    grid.append({"secteur_localisation": round(remaining * 0.7, 2), "texte": w_texte,
                 "structure": round(remaining * 0.3, 2)})
    grid.append({"secteur_localisation": round(remaining * 0.3, 2), "texte": w_texte,
                 "structure": round(remaining * 0.7, 2)})

results = []
t0 = time.time()
for weights in grid:
    engine = MatchingEngine(offers, candidates, weights=weights)
    metrics = evaluate(engine, val_sample, ground_truth, k_list=(5, 10))
    results.append({"weights": weights, **metrics})
    print(weights, "ndcg@10=", round(metrics["ndcg@10"], 4))

print(f"\ngrid search done in {time.time()-t0:.1f}s")

best = max(results, key=lambda r: r["ndcg@10"])
print("\nBEST:", json.dumps(best, indent=2))

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "donnees_generees", "weight_calibration.json"), "w") as f:
    json.dump({"grid_results": results, "best": best,
               "val_sample_size": len(val_sample)}, f, indent=2)

# Save the splits for reuse by other scripts (anti-leakage protocol: fixed once).
import pandas as pd
pd.DataFrame({"candidate_id": train_ids}).to_parquet(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "donnees_generees", "split_train.parquet"))
pd.DataFrame({"candidate_id": val_ids}).to_parquet(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "donnees_generees", "split_val.parquet"))
pd.DataFrame({"candidate_id": test_ids}).to_parquet(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "donnees_generees", "split_test.parquet"))
print("\nsplits saved")
