"""Parse ЦОДД road-load posts (t.me/DtOperativno) into
research/traffic_moscow_2025.csv  (one row per post with a score/speed: date,hour,score,speed_kmh,source_url)
research/traffic_moscow_2025_daily.csv (date, max_score, min_speed, n_posts, reported)
Run from hach_metro: python experiments/traffic/build_traffic.py
"""
import json, re, os
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
W = {'один': 1, 'одного': 1, 'два': 2, 'три': 3, 'четыре': 4, 'пять': 5, 'шесть': 6, 'семь': 7,
     'восемь': 8, 'девять': 9, 'десять': 10}
rows = []
for l in open(os.path.join(HERE, 'dtop_messages.jsonl'), encoding='utf-8'):
    m = json.loads(l); t = m['text']
    sc = re.search(r'(\d{1,2})\s*(?:-|–)?\s*балл', t) or re.search(r'(' + '|'.join(W) + r')\s+балл', t, re.I)
    sp = re.search(r'[Сс]редняя скорость[^0-9]{0,60}?(\d{1,2})\s*км/ч', t)
    if not (sc or sp):
        continue
    score = None
    if sc:
        g = sc.group(1).lower(); score = int(g) if g.isdigit() else W[g]
        if not 0 <= score <= 10: score = None
    ts = pd.Timestamp(m['dt']).tz_convert('Europe/Moscow')
    rows.append({'date': ts.date(), 'hour': ts.hour, 'minute': ts.minute, 'score': score,
                 'speed_kmh': int(sp.group(1)) if sp else None,
                 'source_url': f"https://t.me/DtOperativno/{m['id']}"})
P = pd.DataFrame(rows)
P['date'] = pd.to_datetime(P.date)
P = P[(P.date >= '2025-01-01') & (P.date <= '2025-12-31')].sort_values(['date', 'hour', 'minute'])
root = os.path.join(HERE, '..', '..', 'research')
P.drop(columns='minute').to_csv(os.path.join(root, 'traffic_moscow_2025.csv'), index=False)
D = P.groupby('date').agg(max_score=('score', 'max'), min_speed=('speed_kmh', 'min'), n_posts=('source_url', 'size'),
                          first_hour=('hour', 'min'))
D = D.reindex(pd.date_range('2025-01-01', '2025-12-31', name='date'))
D['reported'] = D.n_posts.notna().astype(int); D['n_posts'] = D.n_posts.fillna(0).astype(int)
D.to_csv(os.path.join(root, 'traffic_moscow_2025_daily.csv'))
print(len(P), 'posts;', D.reported.sum(), 'days reported;', D.max_score.notna().sum(), 'days with score')
print(D.max_score.value_counts().sort_index().to_string())
print(D.groupby(D.index.month).agg(rep=('reported', 'sum'), sc=('max_score', 'mean')).round(2).T.to_string())
print(D.groupby(D.index.dayofweek).agg(rep=('reported', 'mean'), sc=('max_score', 'mean')).round(2).T.to_string())
