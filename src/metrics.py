"""Brier, ROC-AUC, precision/recall/F1 at a threshold. numpy/pandas only."""
import numpy as np
import pandas as pd


def brier(y, p):
    y, p = np.asarray(y, float), np.asarray(p, float)
    return float(np.mean((p - y) ** 2))


def auc(y, p):
    """ROC-AUC via the rank-sum (Mann-Whitney) formula; tied scores get average ranks.
    NaN if y has only one class."""
    y = np.asarray(y, bool)
    n_pos, n_neg = y.sum(), (~y).sum()
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    ranks = pd.Series(np.asarray(p, float)).rank(method="average").to_numpy()
    return float((ranks[y].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def precision_recall_f1(y, p, threshold):
    """Predict positive when p >= threshold."""
    y = np.asarray(y, bool)
    pred = np.asarray(p, float) >= threshold
    tp, fp, fn = (pred & y).sum(), (pred & ~y).sum(), (~pred & y).sum()
    precision = tp / (tp + fp) if tp + fp else float("nan")
    recall = tp / (tp + fn) if tp + fn else float("nan")
    f1 = 2 * tp / (2 * tp + fp + fn) if tp + fp + fn else float("nan")
    return float(precision), float(recall), float(f1)


def best_f1_threshold(y, p):
    """Threshold (one of the observed scores) with the highest F1 for "p >= threshold".
    Ties go to the higher threshold."""
    y = np.asarray(y, bool)
    p = np.asarray(p, float)
    order = np.argsort(-p, kind="stable")
    p_sorted, y_sorted = p[order], y[order]
    tp = np.cumsum(y_sorted)
    fp = np.cumsum(~y_sorted)
    last_of_value = np.r_[p_sorted[1:] != p_sorted[:-1], True]  # cut only between distinct scores
    tp, fp, thr = tp[last_of_value], fp[last_of_value], p_sorted[last_of_value]
    f1 = 2 * tp / (2 * tp + fp + (y.sum() - tp))
    best = np.flatnonzero(f1 == f1.max())[0]  # thresholds are in descending order
    return float(thr[best])


def summarize(y, p, oblast, threshold=None):
    """One table row for a predictor on the evaluation rows. threshold=None means p is already
    a 0/1 prediction and precision/recall are taken as is (no threshold search)."""
    y = pd.Series(np.asarray(y, bool))
    p = pd.Series(np.asarray(p, float))
    oblast = pd.Series(np.asarray(oblast))
    within = [auc(y[g], p[g]) for g in oblast.groupby(oblast).groups.values()]
    precision, recall, f1 = precision_recall_f1(y, p, 0.5 if threshold is None else threshold)
    return {
        "auc_within_oblast": float(np.nanmean(within)), "n_oblasts_auc": int(np.sum(~np.isnan(within))),
        "brier": brier(y, p), "auc_pooled": auc(y, p),
        "threshold": "raw 0/1" if threshold is None else round(float(threshold), 3),
        "precision": precision, "recall": recall, "f1": f1,
    }


def brier_decomposition(y, p, bins=10):
    """Murphy decomposition with equal-width probability bins:
    Brier ~= reliability - resolution + uncertainty. reliability (lower is better) measures
    miscalibration, resolution (higher is better) how far bin outcomes move away from the base
    rate. The two sides differ by the within-bin spread of p, reported as 'residual'."""
    y = np.asarray(y, float)
    p = np.asarray(p, float)
    k = np.minimum((p * bins).astype(int), bins - 1)
    n, base = len(y), y.mean()
    rel = res = 0.0
    for b in np.unique(k):
        m = k == b
        rel += m.sum() * (p[m].mean() - y[m].mean()) ** 2
        res += m.sum() * (y[m].mean() - base) ** 2
    rel, res, unc = rel / n, res / n, base * (1 - base)
    bs = brier(y, p)
    return {"brier": bs, "reliability": rel, "resolution": res, "uncertainty": unc,
            "residual": bs - (rel - res + unc)}


def reliability_table(y, p, bins=10):
    y = np.asarray(y, float)
    p = np.asarray(p, float)
    k = np.minimum((p * bins).astype(int), bins - 1)
    df = pd.DataFrame({"bin": k, "p": p, "y": y}).groupby("bin").agg(
        mean_predicted=("p", "mean"), observed=("y", "mean"), n=("y", "size"))
    df.index = [f"{b / bins:.1f}-{(b + 1) / bins:.1f}" for b in df.index]
    return df
