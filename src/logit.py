"""Plain logistic regression fitted by Newton's method (IRLS), numpy only.

Design: starts_7d (linear), 24 hour-of-day dummies (they take the role of the intercept) and
oblast dummies (first oblast dropped). A 1e-6 ridge term only keeps the Newton step numerically
safe; it does not change the fit in any visible way.
"""
import numpy as np


def design(features, oblasts):
    oblasts = sorted(oblasts)
    starts = features["starts_7d"].to_numpy(float)[:, None]
    hours = (features["hour"].to_numpy()[:, None] == np.arange(24)).astype(float)
    obl = (features["oblast"].astype(str).to_numpy()[:, None] == np.array(oblasts[1:])).astype(float)
    return np.hstack([starts, hours, obl])


def fit(X, y, l2=1e-6, max_iter=50, tol=1e-8):
    y = np.asarray(y, float)
    w = np.zeros(X.shape[1])
    for it in range(1, max_iter + 1):
        p = 1 / (1 + np.exp(-(X @ w)))
        grad = X.T @ (p - y) + l2 * w
        hess = (X * (p * (1 - p))[:, None]).T @ X + l2 * np.eye(len(w))
        step = np.linalg.solve(hess, grad)
        w -= step
        if np.max(np.abs(step)) < tol:
            return w, it
    raise RuntimeError("logistic regression did not converge")


def predict(X, w):
    return 1 / (1 + np.exp(-(X @ w)))
