"""Train failure-risk classifier on roadsense_simulated data (NOT real motorcycle data).
Split BEFORE any scaling; report recall/precision/F1/PR-AUC, not accuracy (failures are rare)."""
import numpy as np, joblib, os
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, average_precision_score
rng = np.random.default_rng(42); n = 10000
X = np.c_[rng.normal(92, 8, n), rng.normal(3800, 900, n), rng.normal(13.8, .35, n), np.abs(rng.normal(1, .35, n)), rng.random(n)]
y = ((X[:, 0] > 108) | (X[:, 2] < 12.6) | (X[:, 3] > 2.2)).astype(int)   # threshold-labelled: a limitation, documented
Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=.2, stratify=y, random_state=42)
m = RandomForestClassifier(300, class_weight="balanced", random_state=42).fit(Xtr, ytr)
print(classification_report(yte, m.predict(Xte)))
print("PR-AUC:", round(average_precision_score(yte, m.predict_proba(Xte)[:, 1]), 3))
out = os.path.join(os.path.dirname(__file__), "..", "backend", "app", "ml_models", "risk.joblib")
joblib.dump(m, out); print("saved", out)
