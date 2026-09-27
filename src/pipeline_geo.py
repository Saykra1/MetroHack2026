"""Geo-binding: route → ordered stops with coordinates (organizer GTFS directory), + quality report of rejected raw rows.
Validations carry no stop id (place_id = depot), so stop-level load = route-hour forecast × stop weight.
Weight = 1/N per direction-stop (documented, replaceable by passenger-survey or APC weights)."""
import pandas as pd, duckdb, glob, json, os
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
f = [g for g in glob.glob('spravochniki/*.xlsx') if '10' in os.path.basename(g)][0]
t = pd.read_excel(f, sheet_name=-1)          # trips with coordinates: route, trip, direction, stop_sequence, stop, lat, lon
main = t.groupby(['route_short_name','direction_id']).trip_id.agg(lambda s: s.value_counts().idxmax()).rename('main_trip').reset_index()
st = t.merge(main, left_on=['route_short_name','direction_id','trip_id'], right_on=['route_short_name','direction_id','main_trip'])
st = st[['route_short_name','direction_id','stop_sequence','stop_id','stop_name','stop_lat','stop_lon']].rename(columns={'route_short_name':'route'})
st['weight'] = 1 / st.groupby('route').stop_id.transform('size')
st.sort_values(['route','direction_id','stop_sequence']).to_csv('experiments/route_stops.csv', sep=';', index=False)
con = duckdb.connect()
rej = con.execute("""SELECT
  count(*) FILTER (WHERE vr <> '1') AS failed_validation,
  count(*) FILTER (WHERE ts IS NULL) AS bad_timestamp,
  count(*) FILTER (WHERE rt NOT LIKE '%трамвай%' OR rt IS NULL) AS not_tram,
  count(*) FILTER (WHERE its > TIMESTAMP '2025-12-31') AS future_input_date_ignored,
  count(*) AS total FROM 'experiments/raw.parquet'""").df().iloc[0].to_dict()
rep = {'rejected_or_flagged': {k: int(v) for k, v in rej.items()},
       'routes_with_geometry': sorted(map(int, st.route.unique())), 'stops_bound': int(st.stop_id.nunique()),
       'note': 'routes 17, 25, 26, 28, 50 have no stop geometry in the directory: route-level only'}
json.dump(rep, open('experiments/pipeline_report.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1); print(json.dumps(rep, ensure_ascii=False, indent=1))
