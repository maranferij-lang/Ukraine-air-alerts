"""Plain logistic regression fitted by Newton's method (IRLS), numpy only.

Design: starts_7d (linear), 24 hour-of-day dummies (they take the role of the intercept) and
oblast dummies (first oblast dropped). A 1e-6 ridge term only keeps the Newton step numerically
safe; it does not change the fit in any visible way.

Matrix products go through _matmul. On Apple silicon, numpy's Accelerate BLAS can leave stray
floating-point flags after a correct product, which numpy then reports as "divide by zero /
overflow / invalid value encountered in matmul". _matmul ignores those flags for the product
only and raises if the product really holds inf or NaN, so a real numerical problem still stops
the run. The sigmoid is outside the guard: an overflow in exp would still warn.
"""
import numpy as np


def _matmul(a, b):
    with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
        out = a @ b
    if not np.all(np.isfinite(out)):
        raise FloatingPointError("logistic regression: a matrix product has inf or NaN values")
    return out


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
        p = 1 / (1 + np.exp(-_matmul(X, w)))
        grad = _matmul(X.T, p - y) + l2 * w
        hess = _matmul((X * (p * (1 - p))[:, None]).T, X) + l2 * np.eye(len(w))
        step = np.linalg.solve(hess, grad)
        w -= step
        if np.max(np.abs(step)) < tol:
            return w, it
    raise RuntimeError("logistic regression did not converge")


def predict(X, w):
    return 1 / (1 + np.exp(-_matmul(X, w)))
