"""The three model families of round 22 (LightGBM, XGBoost, CatBoost), their fixed tuning grids, and final-fit / predict / save / load helpers.

The grids are the ones written in PROCESS_LOG.md (Round 22 protocol); scripts/dev_folds.py runs them, scripts/train_v3.py trains the selected one, scripts/score_v3.py scores it.
"""
import lightgbm as lgb
import numpy as np
import pandas as pd

LGB = {"L1": {},
       "L2": {"num_leaves": 15, "min_data_in_leaf": 400},
       "L3": {"num_leaves": 63, "min_data_in_leaf": 200},
       "L4": {"num_leaves": 31, "min_data_in_leaf": 200, "feature_fraction": 0.7, "bagging_fraction": 0.7, "bagging_freq": 1, "lambda_l2": 10}}
XGB = {"X1": {"max_depth": 6, "min_child_weight": 1},
       "X2": {"max_depth": 4, "min_child_weight": 50},
       "X3": {"max_depth": 8, "min_child_weight": 100, "subsample": 0.8, "colsample_bytree": 0.8},
       "X4": {"max_depth": 6, "min_child_weight": 50, "reg_lambda": 10, "subsample": 0.8}}
CAT = {"C1": {"depth": 6, "l2_leaf_reg": 3},
       "C2": {"depth": 4, "l2_leaf_reg": 3},
       "C3": {"depth": 8, "l2_leaf_reg": 10},
       "C4": {"depth": 6, "l2_leaf_reg": 20, "rsm": 0.7}}
GRIDS = {"lgb": LGB, "xgb": XGB, "cat": CAT}
EXT = {"lgb": "txt", "xgb": "json", "cat": "cbm"}


def lgb_params(name, threads):
    from scripts.evaluate import PARAMS
    return {**PARAMS, "num_threads": threads, **LGB[name]}


def xgb_params(name, threads):
    return {"objective": "binary:logistic", "eval_metric": "logloss", "tree_method": "hist", "eta": 0.05, "nthread": threads, "seed": 0, **XGB[name]}


def cat_params(name, threads):
    return {"learning_rate": 0.1, "loss_function": "Logloss", "random_seed": 0, "thread_count": threads, "verbose": 0, "allow_writing_files": False, **CAT[name]}


def _cat_frame(X):
    X = X.copy()
    X["oblast"] = X["oblast"].astype(str)
    return X, [list(X.columns).index("oblast")]


def fit_final(fam, name, X, y, trees, threads=4):
    """Fit on all of X with a fixed number of trees (no early stopping)."""
    if fam == "lgb":
        return lgb.train(lgb_params(name, threads), lgb.Dataset(X, y), num_boost_round=trees)
    if fam == "xgb":
        import xgboost as xgb
        return xgb.train(xgb_params(name, threads), xgb.DMatrix(X, label=y, enable_categorical=True), num_boost_round=trees)
    from catboost import CatBoostClassifier, Pool
    Xc, cat = _cat_frame(X)
    m = CatBoostClassifier(iterations=trees, **cat_params(name, threads))
    m.fit(Pool(Xc, y, cat_features=cat))
    return m


def predict(fam, model, X):
    if fam == "lgb":
        return model.predict(X)
    if fam == "xgb":
        import xgboost as xgb
        return model.predict(xgb.DMatrix(X, enable_categorical=True))
    from catboost import Pool
    Xc, cat = _cat_frame(X)
    return model.predict_proba(Pool(Xc, cat_features=cat))[:, 1]


def save(fam, model, path):
    if fam == "lgb":
        model.save_model(str(path))
    elif fam == "xgb":
        model.save_model(str(path))
    else:
        model.save_model(str(path))


def load(fam, path):
    if fam == "lgb":
        return lgb.Booster(model_file=str(path))
    if fam == "xgb":
        import xgboost as xgb
        b = xgb.Booster()
        b.load_model(str(path))
        return b
    from catboost import CatBoostClassifier
    m = CatBoostClassifier()
    m.load_model(str(path))
    return m
