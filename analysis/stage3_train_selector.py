#!/usr/bin/env python3
"""Tahap 3 — Pipeline Decision Tree AI Selector.

Label target = keputusan selector pada EXP-001 (kebijakan rule-derived;
bukan ground-truth empiris). Model dilatih ulang atas fitur citra nyata untuk:
(1) audit interpretabilitas — seberapa setia pohon mereproduksi kebijakan,
(2) feature importance kuantitatif,
(3) artefak model yang dapat direproduksi (seed 42).

Output (results/stages/):
  stage3_model_evaluation.csv     — best params + metrik test
  stage3_confusion_matrix.csv     — confusion matrix (counts + row %)
  stage3_feature_importance.csv   — importance per fitur
  stage3_tree_rules.txt           — export_text pohon
  stage3_predictions.csv          — prediksi vs label pada data uji
  figures/stage3_confusion_matrix.png
  figures/stage3_feature_importance.png
  figures/stage3_decision_tree.png
  ai_selector_model_trained.pkl   — model terlatih (joblib)
"""

import os

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.model_selection import GridSearchCV, StratifiedKFold, train_test_split
from sklearn.metrics import (accuracy_score, classification_report,
                             confusion_matrix, precision_recall_fscore_support)
from sklearn.tree import DecisionTreeClassifier, plot_tree, export_text

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(REPO, "results", "stages")
FIG_DIR = os.path.join(OUT_DIR, "figures")

FEATURES = ["entropy", "size_kb", "glcm_correlation", "glcm_contrast"]
CLASSES = ["UHC", "Blowfish", "Hybrid UHC-Blowfish"]
SEED = 42


def main() -> None:
    os.makedirs(FIG_DIR, exist_ok=True)
    df = pd.read_csv(os.path.join(OUT_DIR, "stage1_features.csv"))

    exp1 = pd.read_csv(os.path.join(REPO, "results", "EXP-001",
                                    "raw_batch_results.csv"))
    if "phase" in exp1.columns:
        exp1 = exp1[exp1["phase"] != "warmup"]
    labels = exp1.drop_duplicates("relative_path").set_index("relative_path")
    df["decision"] = df["relative_path"].map(labels["method"])
    df["decision_code"] = df["relative_path"].map(labels["decision_code"])
    df = df.dropna(subset=["decision_code"]).reset_index(drop=True)
    df["decision_code"] = df["decision_code"].astype(int)

    X, y = df[FEATURES].values, df["decision_code"].values
    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.20, stratify=y, random_state=SEED)

    param_grid = {
        "max_depth": [2, 3, 4, 5],
        "min_samples_split": [2, 5, 10],
    }
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    gs = GridSearchCV(
        DecisionTreeClassifier(criterion="gini", random_state=SEED),
        param_grid, scoring="accuracy", cv=cv, n_jobs=-1, refit=False)
    gs.fit(X_tr, y_tr)
    best_params = gs.best_params_
    print(f"[stage3] GridSearchCV best: {best_params} "
          f"(cv acc={gs.best_score_:.4f})")

    clf = DecisionTreeClassifier(
        criterion="gini", random_state=SEED, **best_params).fit(X_tr, y_tr)
    y_hat = clf.predict(X_te)

    acc = accuracy_score(y_te, y_hat)
    prec, rec, f1, _ = precision_recall_fscore_support(
        y_te, y_hat, average="macro", zero_division=0)
    print(f"[stage3] test: n={len(y_te)} acc={acc:.4f} "
          f"P={prec:.4f} R={rec:.4f} F1={f1:.4f}")

    # --- model evaluation csv ---
    eval_rows = [{
        "n_total": len(df), "n_train": len(y_tr), "n_test": len(y_te),
        "split_random_state": SEED, "criterion": "gini",
        "cv_folds": 5, **{f"param_{k}": v for k, v in best_params.items()},
        "cv_best_accuracy": round(gs.best_score_, 4),
        "test_accuracy": round(acc, 4),
        "test_precision_macro": round(prec, 4),
        "test_recall_macro": round(rec, 4),
        "test_f1_macro": round(f1, 4),
    }]
    f_eval = os.path.join(OUT_DIR, "stage3_model_evaluation.csv")
    pd.DataFrame(eval_rows).to_csv(f_eval, index=False)

    # --- confusion matrix ---
    cm = confusion_matrix(y_te, y_hat, labels=[0, 1, 2])
    cm_pct = cm / cm.sum(axis=1, keepdims=True) * 100
    rows = []
    for i, true_c in enumerate(CLASSES):
        for j, pred_c in enumerate(CLASSES):
            rows.append({"true_class": true_c, "pred_class": pred_c,
                         "count": int(cm[i, j]),
                         "row_pct": round(cm_pct[i, j], 2)})
    f_cm = os.path.join(OUT_DIR, "stage3_confusion_matrix.csv")
    pd.DataFrame(rows).to_csv(f_cm, index=False)

    # --- feature importance ---
    imp = pd.DataFrame({
        "feature": FEATURES,
        "importance": np.round(clf.feature_importances_, 6),
    }).sort_values("importance", ascending=False)
    f_imp = os.path.join(OUT_DIR, "stage3_feature_importance.csv")
    imp.to_csv(f_imp, index=False)

    # --- tree rules & predictions ---
    rules = export_text(clf, feature_names=FEATURES, decimals=4)
    with open(os.path.join(OUT_DIR, "stage3_tree_rules.txt"), "w") as fh:
        fh.write(rules)
    preds = pd.DataFrame({
        "true_code": y_te, "pred_code": y_hat,
        "true_class": [CLASSES[i] for i in y_te],
        "pred_class": [CLASSES[i] for i in y_hat],
    })
    preds.to_csv(os.path.join(OUT_DIR, "stage3_predictions.csv"), index=False)

    report = classification_report(y_te, y_hat, target_names=CLASSES,
                                   digits=4, zero_division=0)
    with open(os.path.join(OUT_DIR, "stage3_classification_report.txt"),
              "w") as fh:
        fh.write(f"GridSearchCV params terbaik: {best_params}\n"
                 f"CV accuracy (5-fold): {gs.best_score_:.4f}\n\n{report}")

    # --- model artefact ---
    joblib.dump(clf, os.path.join(OUT_DIR, "ai_selector_model_trained.pkl"))

    # --- figure: confusion matrix heatmap ---
    fig, ax = plt.subplots(figsize=(5.2, 4.4))
    im = ax.imshow(cm_pct, cmap="Greens", vmin=0, vmax=100)
    ax.set_xticks(range(3), ["UHC", "Blowfish", "Hybrid"], rotation=15)
    ax.set_yticks(range(3), ["UHC", "Blowfish", "Hybrid"])
    ax.set_xlabel("Predicted class")
    ax.set_ylabel("True class (selector policy)")
    ax.grid(False)
    for i in range(3):
        for j in range(3):
            color = "white" if cm_pct[i, j] > 55 else "#1a1a1a"
            ax.text(j, i, f"{cm[i, j]}\n{cm_pct[i, j]:.1f}%",
                    ha="center", va="center", fontsize=9, color=color)
    fig.colorbar(im, ax=ax, fraction=0.046, label="Row %")
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "stage3_confusion_matrix.png"),
                dpi=300)
    plt.close(fig)

    # --- figure: feature importance ---
    fig, ax = plt.subplots(figsize=(5.6, 3.2))
    order = np.argsort(clf.feature_importances_)
    ax.barh([FEATURES[i] for i in order],
            clf.feature_importances_[order], color="#16a34a")
    for k, idx in enumerate(order):
        ax.text(clf.feature_importances_[idx] + 0.008, k,
                f"{clf.feature_importances_[idx]:.3f}", va="center",
                fontsize=8.5)
    ax.set_xlabel("Importance (Gini)")
    ax.set_xlim(0, max(clf.feature_importances_) * 1.18)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "stage3_feature_importance.png"),
                dpi=300)
    plt.close(fig)

    # --- figure: decision tree (fit full data untuk visualisasi kebijakan) ---
    full = DecisionTreeClassifier(
        criterion="gini", random_state=SEED, **best_params).fit(X, y)
    fig, ax = plt.subplots(figsize=(13.5, 6.2))
    plot_tree(full, feature_names=FEATURES, class_names=CLASSES,
              filled=True, rounded=True, impurity=False, fontsize=7,
              proportion=True, ax=ax)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "stage3_decision_tree.png"), dpi=300)
    plt.close(fig)

    print(f"\n[stage3] feature importance:\n{imp.to_string(index=False)}")
    print("\n[stage3] confusion matrix (rows=true):")
    print(pd.DataFrame(cm, index=CLASSES, columns=CLASSES).to_string())
    print(f"\n[stage3] tulis output ke {OUT_DIR}")


if __name__ == "__main__":
    main()
