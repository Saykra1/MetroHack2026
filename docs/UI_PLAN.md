# UI redesign plan — «Трамвай: прогноз загрузки»

## 1. Diagnosis (current UI, 27.09)
- One long scroll page (~7,000 px): filters → KPIs → **corrections panel (976 px)** → map → top stops → hourly chart → fleet → anomalies → model → heatmap → table.
- The main question of a dispatcher ("where and when will trams be overcrowded, how many vehicles do I need?") is answered only after 2–3 screens of scrolling.
- No navigation: jury and users cannot see at a glance what the product can do.
- The what-if panel is always expanded although it is used occasionally.
- Visual: cards look alike, weak hierarchy (same header size for everything), status colours scattered.

## 2. Users and scenarios
| # | Who | Scenario | Needs in ≤ 1 screen |
|---|---|---|---|
| S1 | Duty dispatcher, morning | "What's the load today/tomorrow, where is the risk?" | date + route, KPIs, map with hotspots, list of risky hours, hourly curve |
| S2 | Fleet planner | "How many trams per route per hour, where to add/remove?" | fleet chart, recommendations, plan by P90 |
| S3 | Planner / analyst | "What if rain / closure / festival?" | corrections with before → after, from any screen |
| S4 | Analyst | "Month / year view, anomalies, export" | heatmap, month/year chart, anomaly list, table, CSV/XLSX |
| S5 | Jury / manager | "How does the model work, can I trust it?" | model card, validation, sources with links |
| S6 | Anyone on a phone (390 px) | quick check of S1 | single column, bottom tabs, no horizontal scroll |
| S7 | Anyone | ask in words | assistant (cat) available everywhere |

## 3. Information architecture
App shell = header (brand, global filters, theme, export) + **5 views** (hash routing `#overview`, no reload) + floating assistant + **what-if drawer**.

| View | Content (existing components moved, not rewritten) | Scenario |
|---|---|---|
| **Обзор** | KPI row · map (2/3 width) + right rail «Внимание»: top risky hours (P(overflow)), top stops · hourly chart with 80 % band | S1, S6 |
| **Выпуск** | fleet chart + recommendations + P90 toggle | S2 |
| **Аналитика** | horizon day/month/year chart · heatmap · route table · export | S4 |
| **ИИ-аномалии** | anomaly detector list + history markers | S4, S5 |
| **Модель** | how it works, validation (fold table, LB), sources with links, explain factors | S5 |
| **Сценарий** (drawer, right side, from any view) | corrections panel; button in header shows «Сценарий: N активных», result line «было → стало» | S3 |

Global filters (route, date, horizon, hours, model) stay in the header and apply to every view.

## 4. Visual system
- Tokens (already in style.css): extend with elevation levels (surface-0/1/2), 8-px spacing scale, type scale 12/14/16/20/28/40.
- Hierarchy: page title per view (20 px), card titles 16 px with icon + one-line subtitle («что это и зачем»).
- Status palette used consistently: red = overflow risk, amber = watch, green = spare capacity, blue = forecast, grey = fact; legend on the map and chart.
- KPI cards: big number, unit, context line, colour only for risk.
- Motion: 150–200 ms fade/slide between views and for the drawer; respects `prefers-reduced-motion`.
- Empty/loading: skeleton + lying cat (already implemented).
- Accessibility: contrast ≥ 4.5:1 (already checked), focus rings, tabs are real `<button role="tab">`, drawer traps focus and closes on Esc.

## 5. Responsive
- ≥ 1200 px: left sidebar navigation (icons + labels), map + rail side by side.
- 768–1199 px: top tab bar, rail under the map.
- < 768 px: bottom tab bar (5 icons), filters collapse into a «Фильтры» sheet, drawer full-screen, assistant full-screen.

## 6. Implementation (low-risk)
- Branch `ui-redesign`; merge into `ml-ai` only after checks. `main` untouched.
- Keep all element ids and app.js logic; move sections into view containers in index.html; add ~120 lines JS (router, drawer, rail) + CSS.
- On view switch: `chart.resize()` / `map.invalidateSize()` (ResizeObserver already present).
- Time-box: 2 h; if not green by 21:30 → keep current UI (bug fix already shipped).

## 7. Acceptance checks
1. pytest -q green (67+), e2e: every view × light/dark × 1440/390 px, no JS errors, no horizontal scroll, charts have non-zero size.
2. S1 answered on the first screen at 1440×900 (KPIs + map + risky hours visible without scrolling).
3. Drawer: change a coefficient in «Обзор» → numbers update, badge shows N active, reset works.
4. Assistant works on every view; «Применить» switches to «Обзор» with parameters.
5. Screenshots of each view (light + dark, desktop + mobile) in `service/docs/screenshots/ui2_*.png`.
