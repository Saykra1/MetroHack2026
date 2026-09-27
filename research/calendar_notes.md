# Calendar notes (companion to calendar_2025.csv)

Source: Government Decree No. 1335 of 04.10.2024 "On the transfer of days off in 2025" (see [ConsultantPlus 2025 calendar](https://www.consultant.ru/law/ref/calendar/proizvodstvennye/2025/), [Garant](https://www.garant.ru/calendar/buhpravo/2025/)).
Check: the CSV yields **247 working days**, matching the official 5-day-week norm for 2025.

## Transfers in 2025
| Weekend day | moved to (day off) |
|---|---|
| Sat 4 Jan | Fri 2 May |
| Sun 5 Jan | **Wed 31 Dec** |
| Sun 23 Feb | Thu 8 May (so Mon 24 Feb was a normal WORKING day) |
| Sat 8 Mar | Fri 13 Jun (so Mon 10 Mar was a normal WORKING day) |
| **Sat 1 Nov** | **Mon 3 Nov** (so Sat 1 Nov = WORKING day, 7-hour pre-holiday day) |

Non-working blocks: 1–8 Jan; 23 Feb (Sun only); 8–9 Mar (weekend only); 1–4 May; 8–11 May; 12–15 Jun; **2–4 Nov**; **31 Dec**; (1–11 Jan 2026 follows).
Pre-holiday shortened days: 7 Mar, 30 Apr, 11 Jun, **1 Nov** (the working Saturday). 30 Dec is NOT shortened (31 Dec is a transferred day off, not a statutory holiday).

## Nov–Dec 2025 anomalies to model explicitly
- **Sat 1 Nov**: working Saturday -> expect weekday-like AM/PM peaks but weaker (people take it off; school autumn break until 2 Nov). Model as its own day type or "weekday x ~0.8" blend; there is no training analogue in Jan–Oct 2025 (no working Saturdays), so use a blend of weekday and Saturday profiles.
- **Sun 2 – Tue 4 Nov**: 3-day holiday block; 3 Nov (Mon) and 4 Nov (Tue, National Unity Day) = holiday profile (closest analogues in training: 12–13 Jun, 2 May, 8–9 May).
- **Mon 29 – Tue 30 Dec**: working days but strongly depressed (pre-New-Year vacations, school holidays start 31 Dec; many firms give 29–30 Dec off). Afternoon peak shifts earlier; evening shopping/leisure flows higher on 26–30 Dec.
- **Wed 31 Dec**: day off; evening flow atypical; **free fares on metro/MCC/ground transport from 20:00 31 Dec to 06:00 1 Jan** ([rosacademtrans](https://rosacademtrans.ru/transpotny251224/), [mos.ru](https://www.mos.ru/news/item/164558073/)) -> **validations after 20:00 on 31 Dec likely near zero / not recorded** even if passengers ride. 18 tram routes + T1 ran all night ([gazetametro](https://www.gazetametro.ru/articles/pervyj-moskovskij-tramvajnyj-diametr-t1-budet-rabotat-vsju-novogodnjuju-noch-30-12-2025)). Check whether 1–8 Jan 2025 in training data show the same free-fare artifact on the night of 31 Dec 2024.
- Jan 2025 training data: 1–8 Jan holiday block + school holidays to 8 Jan -> exclude or flag as holiday; do not let it pollute the "January level".

## Moscow school holidays (quarter system, recommended by Moscow DOgM; individual schools may differ)
| Year | Autumn | Winter | Spring | Summer |
|---|---|---|---|---|
| 2024/25 | 26 Oct – 4 Nov 2024 | 30 Dec 2024 – 8 Jan 2025 | 24 – 31 Mar 2025 | 24 May – 31 Aug 2025 |
| 2025/26 | 25 Oct – 2 Nov 2025 | 31 Dec 2025 – 11 Jan 2026 | 28 Mar – 5 Apr 2026 | 27 May – 31 Aug 2026 |

Trimester/module schools (minority) 2024/25: 5–13 Oct, 16–24 Nov, 29 Dec–8 Jan, 15–24 Feb, 5–13 Apr; 2025/26: 4–12 Oct, **15–23 Nov**, 31 Dec–11 Jan.
Sources: [lenta.ru 2024/25](https://lenta.ru/articles/2025/06/23/raspisanie-shkolnyh-kanikul-na-2024-2025-god/), [idistur-kids 2024/25 Moscow](https://idistur-kids.ru/news/kanikuly-2024-2025-novyi-grafik-otdykha-dlya-moskovskikh-shkolnikov), [banki.ru 2025/26](https://www.banki.ru/wikibank/shkolnye_kanikuly_2025_2026/). Spring 2025 dates vary by source (some give 29 Mar–6 Apr) — low impact, verify on data if needed.

## CSV columns
`date, dow (0=Mon), is_official_holiday, is_transferred_dayoff, is_transferred_workday, is_preholiday_shortened, is_dayoff (weekend or holiday, excl. working Sat), is_holiday (= is_dayoff), is_school_holiday (quarter system), is_new_year_period (25–31 Dec)`.
