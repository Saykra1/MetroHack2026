import pandas as pd, numpy as np, os
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
ROUTES = [1,5,7,11,12,17,25,26,28,50]

def load_labels():
    tr = pd.read_csv('labels/labels_day_train.csv', sep=';', parse_dates=['date'])
    te = pd.read_csv('labels/labels_day_test.csv', sep=';', parse_dates=['date'])
    d = pd.concat([tr, te])
    grid = full_grid('2025-01-01', '2025-10-31')
    return grid.merge(d, how='left', on=['route','date','hour']).fillna({'boardings': 0})

def full_grid(start, end):
    idx = pd.MultiIndex.from_product([ROUTES, pd.date_range(start, end), range(24)], names=['route','date','hour'])
    return idx.to_frame(index=False)

def wape_score(y, p):
    return max(0.0, 1 - np.abs(y - p).sum() / y.sum())
