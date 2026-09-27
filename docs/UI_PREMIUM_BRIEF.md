# UI premium redesign — brief (from team, 27.09)
Branch: `ui-premium` (from ml-ai). Do not change app logic or API requests; no build step; keep Leaflet + ECharts, restyle them; SVG icons (Lucide-style inline), no emoji.

Palette: blue (data, charts, map, accents; deep navy → light sky) + orange (team cat colour: CTA, warnings, active elements, recommendations). Dark bg ≈ #0a0e1a, light bg ≈ #f8f9fc (warm-soft white). Text contrast ≥ 4.5:1.

Tokens (CSS variables, no hard-coded colours): primary, accent, surface, background, text, border, success, warning, danger; spacing 4/8/12/16/24/32/48; radius 4/8/12/16; shadow sm/md/lg; transition fast 150 / normal 250 / slow 400 ms.

Components:
- Header: sticky, backdrop-blur, large title with accent bar; API/Swagger as icon buttons with tooltips; animated theme toggle.
- Filters: Apple-style segmented control for Day/Month/Year; custom selects with search (stretch), datepicker (stretch), hours range slider (stretch), export buttons with download icons, orange hover.
- KPI cards: 5 in a row desktop, stacked on mobile; 32–40 px monospace numerals (tabular), small caption, SVG icon in corner, accent: blue neutral / orange important / red risk; soft shadow, hover lift 2 px, fade+slide-up stagger 50 ms.
- Corrections (drawer): cards inside card; custom sliders (blue track, orange thumb); floating labels; event preset chips (×0, ×1.2); highlight changed values; animated «было → стало» counter; orange «Сбросить всё».
- Map: CartoDB Dark Matter tiles in dark theme, Positron in light; stop circles coloured blue → orange by load, smooth size/colour animation on hour change; compact gradient legend in a corner.
- Charts (ECharts theme): minimal; fact = blue, forecast = orange, interval = translucent fill; custom rounded tooltips with shadow; smooth entrance; pale/no grid; clickable legend.
- Fleet: bars blue (enough) / orange (risk) / red (overflow); animated dashed current-supply line; recommendation cards with icon, coloured left stripe, hover lift, «Применить» button each.
- Tables: soft zebra, blue translucent row hover, sticky header, sort arrows, compact icon pagination.
- Micro-interactions: cursor-pointer on clickables, 150–300 ms transitions, visible focus rings, skeletons for map/charts, fade+slide between horizons, toasts top-right with auto-close.
- Assistant: floating orange button with cat, chat panel, placeholder «Спросите что-нибудь…», answer cards with «Показать на карте» / «Экспорт».
- Responsive 390 / 768 / 1440+, no horizontal scroll. Themes via CSS variables, 300 ms colour transition. A11y: ARIA for dialogs/tooltips/sliders, keyboard, prefers-reduced-motion.
Result: premium business product look; screenshots updated in service/docs/screenshots/.
