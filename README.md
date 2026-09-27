# ИИ-прогноз загрузки трамвайных маршрутов Москвы

Почасовой прогноз посадок для 10 трамвайных маршрутов на ноябрь–декабрь 2025 и веб-сервис для диспетчеров (карта, коэффициенты, выпуск подвижного состава, интервалы, детектор аномалий, помощник).

| | |
|---|---|
| Public LB (WAPE-score) | **0.90167** (baseline организаторов ≈ 0.48) |
| Локальная валидация | hold-out Jan–Aug → Sep–Oct 0.821 · Oct 0.908 · среднее 6 скользящих фолдов ≈ 0.87 |
| Финальный CSV | `submissions/FINAL_SUBMISSION.csv` (= v08) |
| Сервис | `service/` → `docker compose up --build` → http://localhost:8000 (см. [service/README.md](service/README.md)) |

## Почему именно это решение — где смотреть обоснование
| Вопрос | Документ |
|---|---|
| Какая модель и почему она объяснима | [SOLUTION.md](SOLUTION.md) — формула `уровень × суточный профиль × особый день × погода × события`, внешние источники со ссылками и эффектом, область применимости |
| Что пробовали, какие метрики, что отбросили | [EXPERIMENTS.md](EXPERIMENTS.md) — все 17 шагов от 0.48 до 0.9017 с CV и LB, по одному изменению на сабмит |
| Почему не бустинг / нейросеть | [experiments/ml/REPORT.md](experiments/ml/REPORT.md) — LightGBM на 55 точках прогноза хуже на всех фолдах (−0.019…−0.026), вес выбран кросс-валидацией = 0; ML используется для интервалов P10–P90 и детектора аномалий |
| Какие решения принимались и почему | [DECISIONS.md](DECISIONS.md) — журнал решений с отвергнутыми альтернативами |
| Находки в данных | [INSIGHTS.md](INSIGHTS.md) — 26 инсайтов (утечка-хвост 1 ноября, ремонты 7/50, запуск маршрута 5, каникулы в окне уровня…) |
| Спор «поднимать ли уровень» | [research/debate_bull.md](research/debate_bull.md), [research/debate_bear.md](research/debate_bear.md), разрешён анализом [research/analyst_round2.md](research/analyst_round2.md) и пробами LB |
| Внешние события и источники | [research/external_events.md](research/external_events.md), [research/events_round2.md](research/events_round2.md), [research/traffic_source.md](research/traffic_source.md), [research/calendar_notes.md](research/calendar_notes.md), [research/prior_art.md](research/prior_art.md) |
| Независимое ревью | [research/judge_review.md](research/judge_review.md) — скоркарта по критериям, вопросы жюри с ответами |
| Хронология работы | [LOG.md](LOG.md), таблица сабмитов [LEADERBOARD.md](LEADERBOARD.md), постановка [TASK.md](TASK.md) |
| Пайплайн данных | [experiments/ingest_report.md](experiments/ingest_report.md) — 62.4M сырых строк → 59.7M валидаций за 28 с, 100 % совпадение с разметкой |
| Сервис: сборка, тесты, производительность | [service/README.md](service/README.md), [service/BUILD_LOG.md](service/BUILD_LOG.md) — 67 pytest-тестов, p95 17–63 мс на 2 vCPU |

## Тесты и воспроизводимость
```bash
pip install -r service/requirements-dev.txt pandas numpy duckdb openpyxl statsmodels lightgbm
python src/pipeline_ingest.py          # сырые CSV → почасовые агрегаты + сверка с разметкой
python src/make_final.py --no-weather --name final   # = FINAL_SUBMISSION.csv (v08)
python src/ml/hybrid.py                # бэктест гибрида LightGBM (обоснование w = 0)
python src/ml/quantiles.py             # калибровка интервалов P10–P90
python src/ml/anomalies.py             # детектор аномалий
cd service && pytest -q                # тесты API, помощника, UI
```
Сырые данные (train.csv/test.csv, 10 ГБ) не хранятся в репозитории — описание датасета: [docs/DATASET_README.md](docs/DATASET_README.md).
