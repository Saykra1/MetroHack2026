# External events affecting Moscow tram ridership (2025)

Target routes: **1, 5, 7, 11, 12, 17, 25, 26, 28, 50**. Items touching them are marked **[TARGET]**.
Network context: ~830k tram trips/day (June 2025, [mskagency](https://www.mskagency.ru/materials/3554685)).

## Nov–Dec 2025 (forecast period)

| Date(s) | Event | Routes | Expected effect | Link |
|---|---|---|---|---|
| Sep 2025 – "end of autumn" (~30 Nov), **weekends only** | Track repair in Protopopovsky lane: route 7 on Sat/Sun cut back to Kalanchevskaya St (no Belorussky/Novoslobodskaya); **route 50 cancelled on Sat/Sun** | **[TARGET] 7, 50** | Weekend flows of 7 and 50 in Sep–Oct training data are depressed / zero for 50. For 1–30 Nov weekends likely still depressed; December weekends likely back to normal -> use pre-Sep weekend/weekday ratio for Dec. Verify on data (50 weekend = 0 in Sep–Oct?) | [newsvostok 12.09.2025](https://newsvostok.ru/dlya-tramvaev-7-i-50-izmeneniya-po-vyhodnym-budut-dejstvovat-do-kontsa-oseni/), [rimc-rambam](https://rimc-rambam.ru/news/14880/) |
| 12–13 Nov 2025 | **Moscow Tram Diameter T1 launched** (Universitet – Metrogorodok, 27 km, 64 stops, 50 Lvyonok trams, 6-min interval). Routes 13 and 39 kept (shared-segment interval 10 -> 4 min); several sources say **route 90 was discontinued**. T1 got ~77k trips/weekday (1.5x forecast) | not target directly; T1 runs via Krasnye Vorota / Kalanchevskaya / Preobrazhenka corridor shared with 7, 50, 11, 12 etc. | Possible diversion of passengers from parallel routes (esp. **7, 50** in the east/centre) from 13 Nov; network-level ridership likely +. Check level shift in Nov for 7/50 is not modelable from training -> consider small downward adj. | [vedomosti](https://www.vedomosti.ru/gorod/ourcity/articles/ot-universiteta-do-metrogorodka), [t-j.ru](https://t-j.ru/news/tramvainyi-diametr-moskva/), [news.mail.ru](https://news.mail.ru/society/68770314/), [i.transport.mos.ru/mtd](https://i.transport.mos.ru/mtd), [sobyanin.ru 2025 recap](https://www.sobyanin.ru/kakim-byl-2025-god-dlya-moskovskogo-tramvaya) |
| **16 Dec 2025** | **Route 5 (re)launched: Belorussky vokzal – m. Rizhskaya** via Lesnaya, Palikha, Tikhvinskaya, Obraztsova, new 2.1 km catenary-free line on Trifonovskaya. 7 Lvyonok trams, 6–7 min. **Route 9 and e-bus S510 discontinued** (5 capacity ~+20% vs 9+S510 combined) | **[TARGET] 5** | If "route 5" exists in Jan–Oct training data it was a different route/alignment (tram 5 had been absent from Trifonovskaya since 1995) -> **structural break on 16 Dec**. If route 5 has no history, predict ~0 until 15 Dec and use route 9's history (scaled ~1.0–1.2) from 16 Dec. CHECK DATA FIRST. | [mperspektiva 17.12.2025](https://mperspektiva.ru/topics/v-moskve-vnov-zapustili-tramvaynyy-marshrut-5/), [interfax](https://www.interfax.ru/moscow/1063595), [msk1](https://msk1.ru/text/transport/2025/12/16/76173070/), [mos.ru](https://www.mos.ru/mayor/themes/13888050/) |
| 20 Dec 2025 | Bus/e-bus network corrections (new bus 442; S510 removed) | none tram | minor | [gazetametro](https://www.gazetametro.ru/articles/s-20-dekabrja-skorrektirujut-marshruty-nazemnogo-transporta-v-raznyh-chastjah-goroda-18-12-2025) |
| 15 Nov 2025 | First snow + heaviest Nov precip day (12.8 mm, 5 cm snowfall, temp swing +5 -> -3 C), Sat | all | weekend + weather dip | Open-Meteo (weather CSV) |
| 1–25 Dec 2025 | Record-low-snow December start (max cover 3 cm by 18 Dec) — i.e. benign conditions | all | no weather disruption | [lenta 18.12.2025](https://lenta.ru/news/2025/12/18/moskovskiy-dekabr-poshel-na-rekord-po-minimumu-snega/) |
| 13–15 Dec, **23–24 Dec** | Cold snaps: 23–24 Dec min -15..-17 C (coldest days of 2025), mean -12 C | all | small (+/- few %) | weather CSV |
| **26 Dec 2025** (overnight 25->26) | Heaviest snowfall of the season, snow cover to 13 cm; DepTrans reported ground-transport delays, intervals doubled on some routes; metro recommended | all (trams slower, fewer trips) | lower validations on 26 Dec (Fri) and possibly 27 Dec | [gazetametro 26.12.2025](https://www.gazetametro.ru/articles/moskva-utonula-v-snegu-i-obnovila-rekord-etoj-zimy-26-12-2025), [vbr.ru](https://www.vbr.ru/help/novosti/moskva-snegopad-48832/) |
| 31 Dec 20:00 – 1 Jan 06:00 | **Free travel** on metro, MCC and ground transport; 18 tram routes + T1 run all night | all | validations after 20:00 on 31 Dec ~ 0 (no fare taps) — check vs 31 Dec 2024 pattern (not in training) | [rosacademtrans](https://rosacademtrans.ru/transpotny251224/), [mos.ru](https://www.mos.ru/news/item/164558073/), [rg.ru](https://rg.ru/2025/12/31/reg-cfo/metro-mck-nazemnyj-transport-budut-rabotat-v-novyj-god-i-posle-boia-kurantov.html) |
| Dec 2025 (from ~late Nov) | "Moscow Winter Journey / New Year journey" festival sites, Red Square fair etc. (annual) | central routes | mild evening uplift in centre, weekends | annual event, mos.ru |
| 2 Jan 2026 | Fare rise to 75 RUB (Troika) | — | outside horizon | [t-j.ru](https://t-j.ru/news/tramvainyi-diametr-moskva/) |

No Nov–Dec 2025 closures were found for routes 1, 11, 12, 17, 25, 26, 28 (searched mos.ru / transport.mos.ru / mskagency / msk1). Official live list: [i.transport.mos.ru/perekrytiya](https://i.transport.mos.ru/perekrytiya), [transport.mos.ru closures map](https://transport.mos.ru/mostrans/closures).

## Jan–Oct 2025 (to explain training anomalies)

| Date(s) | Event | Routes | Link |
|---|---|---|---|
| Summer–autumn 2025 | Capital track repair on 15 sections (12+ km), "mostly nights and weekends": Stroginsky bridge, Novoslobodskaya, Preobrazhenskaya, Lesnaya, Volochaevskaya, Tikhvinskaya, Krasnokazarmennaya/Mikhalkovskaya, Volokolamskoe sh., Shosse Entuziastov, Danilovsky Val, Radio St, Vostochnoe Izmailovo & Sokolniki loops | many; Krasnokazarmennaya/Radio -> **[TARGET] 50, 7?**; Vost. Izmailovo loop -> **[TARGET] 11, 12?** | [mskagency 26.06.2025](https://www.mskagency.ru/materials/3554685) |
| 5–6, 8 Jun 2025 | Belorussky–Kalanchevskaya closed (marathon/works); route 9 replaced, **7** Bul. Rokossovskogo–Kalanchevskaya, **50** DK Kompressor–Kalanchevskaya | **[TARGET] 7, 50** | [msk1 02.06.2025](https://msk1.ru/text/transport/2025/06/02/75536669/) |
| from 7 Jun 2025 (weekends) | Aviamotornaya – Sh. Entuziastov closed: route 2 cut, **12** re-routed Vost. Izmailovo–MCD Novogireevo, 37 re-routed | **[TARGET] 12** | same |
| 10 Jul – ~7 Aug 2025 (up to 28 days) | No trams Krasnye Vorota – Belorussky and near Novoslobodskaya/MIIT; 37 cut to Lefortovsky most; **50 merged with 13** (Metrogorodok – Krasnye Vorota – Aviamotornaya – DK Kompressor) | **[TARGET] 50 (and likely 7)** | [uv-kurier 08.07.2025](https://uv-kurier.ru/2025/07/08/u-tramvaya-37-konechnaya-budet-v-lefortove-a-marshruty-50-i-13-obedinyat/) |
| 10 Sep 2025 | Catenary-free line on Akademika Sakharova (Komsomolskaya sq. – Chistye Prudy) opened | lines via Sakharova (check 7/50 corridor) | [mos.ru](https://www.mos.ru/mayor/themes/13360050/), [mperspektiva](https://mperspektiva.ru/topics/v-moskve-zapustili-pervyy-beskontaktnyy-tramvay-/) |
| 12 Sep 2025 – end autumn | Weekend cut of 7 / cancellation of 50 (see above) | **[TARGET] 7, 50** | newsvostok |
| Sep 2025 | Autonomous (driverless) tram trial on route 10 (Strogino) | 10 | [sobyanin.ru](https://www.sobyanin.ru/kakim-byl-2025-god-dlya-moskovskogo-tramvaya) |
| 17–25 Feb, 23–24 Feb 2025 | Coldest pre-Dec spell (min -14..-16 C) | all | weather CSV |
| 6–8 Apr 2025 | Late heavy snowfall (8–9 cm/day, strongest of year) | all | weather CSV |
| 8–12 Jul 2025 | Heat wave, max 31–35 C | all | weather CSV |
| 21 Jul 2025 | Heaviest rain of year (31 mm) | all | weather CSV |
| 1–8 Jan, 1–4 & 8–11 May, 12–15 Jun 2025 | Holiday blocks (see calendar) | all | calendar CSV |

Tip: flag days/route pairs where the daily total drops >40% vs same-weekday median as "disruption" and exclude them from profile/level estimation (or add a disruption flag feature) — the list above explains most such drops for 7/50/12.

## Weather file
`weather_moscow_2025.csv`: 8760 hourly rows 2025-01-01T00:00..2025-12-31T23:00 local (Europe/Moscow, UTC+3, no DST), no NaNs. Source: Open-Meteo ERA5 archive
`https://archive-api.open-meteo.com/v1/archive?latitude=55.7558&longitude=37.6173&start_date=2025-01-01&end_date=2025-12-31&hourly=temperature_2m,precipitation,rain,snowfall,snow_depth,weather_code,wind_speed_10m,apparent_temperature&timezone=Europe%2FMoscow`
Caveat: reanalysis grid (~9–25 km) underestimates snow depth (ERA5 gives <=0.2 m in Dec vs 13 cm observed). Use snowfall/precipitation and temperature; treat snow_depth as a relative signal only.
Nov–Dec 2025 summary: mild November (daily means +9..-4 C, first frost 15–16 Nov); very dry, snowless early December; cold snaps 13–15 Dec and 23–24 Dec; snowy last week (25–31 Dec).
