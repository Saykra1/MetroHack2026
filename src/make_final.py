"""One-command reproducible pipeline:
labels → level×shape base with calendar (build_submission) → business rules (adjust) → submission + explain file for the service.
Usage: python src/make_final.py [--no-weather] [--r50] [--r7] [--nov K] [--dec K]"""
import argparse, subprocess, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser()
ap.add_argument('--no-weather', action='store_true'); ap.add_argument('--r50', action='store_true'); ap.add_argument('--r7', action='store_true')
ap.add_argument('--nov', type=float, default=1.0); ap.add_argument('--dec', type=float, default=1.0); ap.add_argument('--name', default='final')
a = ap.parse_args()
subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), 'build_submission.py')], check=True)  # refreshes v02 explain
import adjust as A
steps = list(A.BEST_V08)   # anchor shape + clean level, NY night, route 5 (from 16.12 18h), r50/r7 weekends from 15.11
if a.nov != 1: steps.append((A.scale, {'k': a.nov, 'start': '2025-11-01', 'end': '2025-11-30'}))
if a.dec != 1: steps.append((A.scale, {'k': a.dec, 'start': '2025-12-01', 'end': '2025-12-31'}))
if not a.no_weather: steps.append((A.weather, {}))
E = A.build(steps)
A.save(E, a.name)
E['date'] = E.date.dt.strftime('%Y-%m-%d')
if 'weather_mult' not in E: E['weather_mult'] = 1.0
new5 = (E.route == 5) & (E.base == 0) & (E.prediction > 0)       # new route: base taken from proxy route 28 × 0.5
E.loc[new5, 'base'] = E.loc[new5, 'prediction'] / E.loc[new5, 'weather_mult'].where(E.route != 5, 1.0)
E['rules_mult'] = (E.prediction / (E.base * E.special_mult * E.weather_mult)).where(E.base > 0, 1.0).round(4)
E['note'] = ''
E.loc[new5, 'note'] = 'new route 5 from 2025-12-16: profile of route 28 x0.5'
E.loc[(E.date == '2025-12-31') & (E.hour >= 20), 'note'] = 'free fare New Year night'
E[['route','date','hour','base','special_mult','weather_mult','rules_mult','prediction','note']].round(3).to_csv(f'submissions/{a.name}_explain.csv', sep=';', index=False)
print('steps:', [f.__name__ for f, _ in steps])
