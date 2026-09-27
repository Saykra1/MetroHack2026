# External events, round 2 (Nov–Dec 2025): targeted answers

Main source: a full dump of the Deptrans operational Telegram channel **t.me/s/DtOperativno** (every post from 2025-08-08 to 2026-01-25, about 2,360 posts, paged by message id, with post timestamps). I grepped it for tram posts that mention the target routes. Channel links are given as `t.me/DtOperativno/<id>`.
Confidence levels: H = official post with an explicit date. M = official source, but scope or inference is not fully explicit. L = inference.

## Q1. Weekend cut of routes 7 and 50 (Protopopovsky lane): END DATE = weekend of **15 Nov 2025**

| Date | Fact | Conf | Link |
|---|---|---|---|
| 2025-09-05 post | "From **6 Sep**, on weekends": route 7 runs only Bul. Rokossovskogo – Kalanchevskaya St; **route 50 does not run**; replacement bus 07 (Belorussky – Sokolniki); e-bus s510 extended | H | t.me/DtOperativno/22624, [mskagency 05.09](https://www.mskagency.ru/materials/3506273) |
| **2025-11-15 09:14** | "**From 15 Nov**, weekend service to Belorusskaya/Novoslobodskaya **restored**. Trams 7, 50 and e-bus s510 run their normal routes on these days. Temporary bus 07 withdrawn." | **H** | t.me/DtOperativno/23565, [mskagency 3523754 (15.11.2025 14:16)](https://www.mskagency.ru/materials/3523754) |

**Implication:**
- Weekend days that were still affected in the forecast window: **Sun 2 Nov, Mon 3 Nov and Tue 4 Nov (holiday/non-working days, probably covered by "по выходным"; M), and Sat 8 / Sun 9 Nov (H)**.
- **Sat 1 Nov 2025 was a working Saturday (moved workday).** A parallel Deptrans post for the Nagatino closure said "on weekends **and also on Saturday 1 Nov**" (t.me/DtOperativno/23313). The 7/50 notice had no such clause, so **1 Nov was probably normal weekday service for 7 and 50 (M/L)**.
- **From 15 Nov all weekends are normal (H).** Apply the "restored weekend" ratios the team already uses for December (r50 Sat/Sun ≈ 0.44/0.37 of weekday, r7 0.60/0.51) to **15–16, 22–23 and 29–30 Nov as well** (6 extra weekend days per route).
- **No other weekend closures of 7 or 50 were posted for Nov–Dec 2025 (H: the channel was checked in full).**

**Route 7: a second weekend cut ran 20–28 Sep only.** Bul. Rokossovskogo – Bogorodskoe was closed on weekends from 20 Sep (t.me/DtOperativno/22810, [mskagency 3509951](https://www.mskagency.ru/materials/3509951)) and restored **from 4 Oct** (t.me/DtOperativno/23007). The training weekends of 20/21 and 27/28 Sep for route 7 are doubly abnormal. Exclude them when estimating the normal ratio.

**Late-evening cuts for 7 and 50 (affect about 22–01h cells on every day, including weekdays):**

| Period | Rule | Conf | Link |
|---|---|---|---|
| 12 Sep – 30 Sep | after 23:00, 7 and 50 run only to Kalanchevskaya | H | 22723; restored 1 Oct: 22966 |
| (15 Aug – ?) | after 23:00, 7 runs Rokossovskogo–Sokolniki, 50 to Kalanchevskaya (Komsomolskaya sq.) | H | 22371 |
| **28 Oct – 24 Nov** | **after 22:00**, 7 and 50 run only to Kalanchevskaya (Protopopovsky) | H | 23293 |
| 5 Nov – 24 Nov | after 23:20, 7 runs Rokossovskogo–**Sokolniki**, 50 runs to Kalanchevskaya (Komsomolskaya sq.) | H | 23413 |
| **25 Nov** | full evening service after 22:00 restored for 7 and 50 | H | 23760, [mskagency 3525053](https://www.mskagency.ru/materials/3525053) |
| **13 Dec – beyond 25 Jan 2026** | "trams in centre finish earlier": **4 and 7 run only Rokossovskogo–Sokolniki after 23:00; 50 runs only to Kalanchevskaya after 23:00** (energy-infrastructure works; no restoration post found up to 25 Jan) | H | 24097 |

**Implication:** late hours of 7 and 50 are cut on 1–24 Nov (22h+) and from 13 Dec onwards (23h+). The period 25 Nov–12 Dec has full late service. The effect is small in absolute terms (late hours are about 2–4% of daily volume). If the shape comes from Oct weeks (22h+ cut from 28 Oct), the Oct profile slightly under-weights 22–23h for 25 Nov–12 Dec.

## Q2. "Network change" 2025-12-20: stop relocations only; no re-routing of 7, 11 or 12

The complete set of Deptrans posts about 20 Dec:
- 7 and 50: stops "Ulitsa Shchepkina" and "Teatr zverey im. Durova" moved to new raised platforms (t.me/DtOperativno/24240), H.
- **11 and 12**: new stop platforms on **Pervomayskaya St** (t.me/DtOperativno/24238), H.
- A, **12**, 38, 43: new platforms on Abelmanovskaya St, plus a new stop "Abelmanovskaya Zastava" (t.me/DtOperativno/24235), H.
- 32, 46: platforms in Lefortovo (24239).
- Bus side: T42+110 merged into 442, s510 removed ([mskagency 3528449](https://www.mskagency.ru/materials/3528449)).

The 2025-10-11 date in the directory (routes 1/3/6/10…) matches the same kind of event. On **11 Oct**, stops were moved to new raised platforms (Galushkina/Rostokinsky for 11 and 25, Izmailovsky/Preobrazhensky Val and Semyonovskaya for 11, and others; t.me/DtOperativno/23072).

**Conclusion (H):** the organizer's `route_date_start` values are GTFS version dates driven by stop changes. **Route 7 is unchanged: Bul. Rokossovskogo – Belorussky vokzal was its normal alignment all year.** There is no merger, no cut and no interval change. **Do not apply any level shift to 7, 11, 12 (or 2, 4) on 20 Dec.** At most, expect a small redistribution between stops.

## Q3. Route 5 (Rizhskaya – Belorussky vokzal)

| Fact | Conf | Link |
|---|---|---|
| Opened with a ceremony on **16 Dec 2025 at about 18:06** (Deptrans post 18:17). Scheduled service runs 5:30–0:45 | M-H | [msknovosti](https://msknovosti.ru/news/transport/dvizhenie-tramvaev-zapustili-po-trifonovskoy-ulitse-v-moskve/), t.me/DtOperativno/24135 |
| **Route 9 and e-bus s510 ran through 16 Dec** (last route 9 trip from Belorussky 21:47) and were withdrawn "from 17 Dec". Route 5 merges their alignments | H | 24135, 24136, msknovosti |
| Interval about 8 min (msknovosti) or 6–7 min (mperspektiva). About 7 Lvyonok trams | M | msknovosti; [mperspektiva](https://mperspektiva.ru/topics/v-moskve-vnov-zapustili-tramvaynyy-marshrut-5/) |
| Forecast about 20k passengers/day (35k by 2030) | M | msknovosti, [mos.ru](https://www.mos.ru/mayor/themes/13888050/) |
| **Actual: "more than 160k trips" in the first month** (Liksutov, 22 Jan 2026) | H | [MK 22.01.2026](https://www.mk.ru/social/2026/01/22/zammera-liksutov-vosstanovlennaya-tramvaynaya-liniya-po-trifonovskoy-ulice-pokazala-sebya-udobnoy-i-vostrebovannoy.html), [gazetametro 22.01.2026](https://www.gazetametro.ru/articles/vozvraschenie-tramvajnogo-dvizhenija-na-trifonovskuju-ulitsu-opravdalo-sebja-22-01-2026) |
| No ridership numbers found for route 9 | – | – |

**Implication (L):**
- 160k trips over about 31–37 days, including the New Year shutdown (31 Dec – 11 Jan is low), works out to about 4.5–5k/day on average. Normal working days are probably **about 5.5–7k/day**, weekends about 3–4k. Actual ridership was far below the 20k forecast.
- **16 Dec: predict route 5 only from about 18h** (hours 5–17 ≈ 0). Some sources are vague on whether passenger service started before the ceremony (M).
- Compare these numbers with the current "0.5 × route-28 profile". If that gives much more than about 6k/weekday, scale it down. If it gives less, the k=0.5 vs k=1.0 LB result points to about the same level.

## Q4. T1, other target routes, and 11 Oct

- **T1 opened 12 Nov 2025** (Metrogorodok – Universitet, 27 km). **Route 90 was discontinued**; T1 is "the extended 90" (t.me/DtOperativno/23513, H). T1 shares track with 7 and 50 only between Krasnoselskaya/Komsomolskaya/Kalanchevskaya and Sokolniki–Bul. Rokossovskogo (7). It serves a different corridor from 50's core.
  - T1 ridership: about 70k trips/day by 30 Nov and about 77–78k/weekday later, 1.5× forecast ([gazetametro 30.11](https://www.gazetametro.ru/articles/bolee-70-tysjach-poezdok-v-sutki-sovershajut-passazhiry-na-pervom-tramvajnom-diametre-30-11-2025), [MK 21.01.2026](https://www.mk.ru/social/2026/01/21/zammera-liksutov-pervyy-moskovskiy-tramvaynyy-diametr-stal-samym-vostrebovannym-tramvaynym-marshrutom.html)).
  - No statement found about diversion from 7 or 50 (L: small, since 90 already ran the shared section from 10 Sep).
- **Routes 1, 11, 12, 17, 25, 26, 28: no planned closures or re-routings in Nov–Dec 2025 (H: full channel scan).** Only short incident delays occurred: 1 on 18 Nov morning; 17 on 20, 21 and 28 Nov and 16–17 and 23 Dec; 11 and 25 on 13 Dec; 26 on 14 Dec; 28 on 4 Dec; 12 on 8 and 16 Nov; 50 on 10, 16 and 24 Nov and 28 Dec; 7 on 1 Nov evening and 18 Dec. These are too minor to model.
- 20 Nov after 22:30: route 4 detour at the Sokolniki loop (not a target route). 19 Dec 11:30–13:00: centre closed (A, 3, 39 only).
- 11 Oct: stop relocations only (see Q2). No network change.

## Q5. Ridership statements, holidays, snow

- 2025 overall: trips on e-buses and trams **+30% y/y** ([mskagency 3534582](https://www.mskagency.ru/materials/3534582)). Ground transport carried about 4.5M trips/weekday in Oct 2025 ([gazetametro 10.10.2025](https://www.gazetametro.ru/articles/45-mln-poezdok-sovershaetsja-na-avtobusah-elektrobusah-i-tramvajah-v-budni-10-10-2025)). No monthly Nov or Dec figures for trams, and no "record day" posts, were found (L: network growth is driven by T1, not by the target routes).
- Snow: on **26 Dec**, Deptrans posted no tram-specific disruption. Only one ДТП (traffic accident) delay was posted, for T1/A/3/39. On **15 Nov** (first snow), there were no tram weather posts. The weather effect should come through the regression only; no route-specific outage is needed.
- New Year: 18 tram routes plus T1 ran all night on 31 Dec–1 Jan, with free travel 20:00–06:00 (t.me/DtOperativno/24391). This supports the existing rule of 0 boardings for 31 Dec 20–23h.

## Quantified summary for the forecast
1. **7 and 50 weekends: normal from 15 Nov (H).** Extend the "restored weekend" ratios from December to 15/16, 22/23 and 29/30 Nov. Keep depressed levels (Sep–Oct pattern: 50 ≈ 0, 7 cut) for 2, 3, 4, 8 and 9 Nov. Treat 1 Nov (working Saturday) as normal weekday service.
2. **20 Dec: no level change** for 7, 11, 12, 2 or 4 (only stops moved to platforms).
3. **Route 5:** about 5.5–7k/weekday, about 3–4k/weekend day (L, from 160k in the first month). On 16 Dec it runs from about 18h only; it absorbs routes 9 and s510 from 17 Dec.
4. **Late evening (≥22–23h) for 7 and 50:** cut on 1–24 Nov and from 13 Dec. Full service 25 Nov–12 Dec.
5. **No closures for 1, 11, 12, 17, 25, 26, 28 (H).**
