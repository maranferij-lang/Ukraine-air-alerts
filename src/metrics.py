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
