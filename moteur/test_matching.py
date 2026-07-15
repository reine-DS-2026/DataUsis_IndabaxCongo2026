import time
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_prep import build_all
from matching import MatchingEngine

t0 = time.time()
candidates, offers, ground_truth = build_all(cache=True)
print(f"data loaded in {time.time()-t0:.1f}s")

t0 = time.time()
engine = MatchingEngine(offers, candidates)
print(f"engine fit in {time.time()-t0:.1f}s")

sample_id = candidates.iloc[0]["candidate_id"]
print("\nCandidat test:", sample_id)
print(candidates.loc[candidates.candidate_id == sample_id, [
    "qualification_metier", "secteur_metier", "metier_vise", "departement", "mobilite", "objectif"
]].to_string())

t0 = time.time()
recs = engine.recommend(sample_id, k=10)
print(f"\nrecommend in {time.time()-t0:.3f}s")
print(recs[["rank", "offer_id", "intitule", "secteur_offre", "lieu", "score_final"]].to_string())

print("\nGround truth pour ce candidat:")
print(ground_truth[ground_truth.candidate_id == sample_id])

print("\nExplication termes pour top-1:")
top1 = recs.iloc[0]["offer_id"]
print(engine.explain_terms(sample_id, top1))

# Test batch timing on 200 candidates
t0 = time.time()
for cid in candidates["candidate_id"].iloc[:200]:
    engine.recommend(cid, k=10)
dt = time.time() - t0
print(f"\n200 recommandations en {dt:.2f}s -> {dt/200*1000:.1f} ms/candidat -> "
      f"estimation totale 41298 candidats: {dt/200*41298/60:.1f} min")
