"""Capture dashboard screenshots with headless Chrome (playwright).

Usage: python scripts/screenshots.py [base_url]   -> docs/screenshots/*.png

Round 5 layout: 5 views (#overview, #fleet, #analytics, #anomalies, #model) and the «Сценарий» drawer.
ui2_<view>_<theme>_<desktop|mobile>.png = first screen of every view (1440×900 / 390×844), light and dark.
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
OUT = Path(__file__).resolve().parents[1] / "docs" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)
VIEWS = ["overview", "fleet", "analytics", "anomalies", "model"]


def wait_ready(page, ms=2200):
    page.wait_for_function("document.querySelectorAll('#routeTable tbody tr').length > 0", timeout=30000)
    page.wait_for_timeout(ms)  # tiles + chart animations


def view(page, v):
    page.evaluate(f"document.getElementById('tab-{v}').click()")
    page.wait_for_timeout(500)


def show(page, sel):
    """Open the view that contains the element."""
    page.evaluate("""sel => { const v = document.querySelector(sel)?.closest('.view');
      if (v) document.getElementById('tab-' + v.id.slice(5)).click(); }""", sel)
    page.wait_for_timeout(400)


def drawer(page, open_):
    if page.is_visible("#drawer") != open_:
        page.click("#scnBtn") if open_ else page.keyboard.press("Escape")
        page.wait_for_timeout(400)


def panel(page, sel, name):
    """Element screenshot (its view is opened first) without the sticky bars covering it."""
    show(page, sel)
    page.add_style_tag(content=".filters{position:static !important} .viewnav{position:static !important} "
                               ".asst-btn{display:none !important}")
    page.locator(sel).first.screenshot(path=str(OUT / name))


def filters(page, fn):
    sheet = page.is_visible("#filtBtn")
    if sheet:
        page.click("#filtBtn")
    fn()
    if sheet and page.evaluate("document.body.classList.contains('filters-open')"):
        page.click("#filtClose")


with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome", headless=True)
    # ---------- Round 5: every view, light + dark, desktop + mobile ----------
    for theme in ("light", "dark"):
        for kind, vp in (("desktop", {"width": 1440, "height": 900}), ("mobile", {"width": 390, "height": 844})):
            ctx = b.new_context(viewport=vp, color_scheme=theme, device_scale_factor=1)
            page = ctx.new_page()
            page.on("console", lambda m: m.type == "error" and "Failed to load" not in m.text and print("console:", m.text))
            page.goto(BASE + "/#overview", wait_until="domcontentloaded")
            wait_ready(page)
            for v in VIEWS:
                view(page, v)
                page.wait_for_timeout(1300)
                page.screenshot(path=str(OUT / f"ui2_{v}_{theme}_{kind}.png"))
            view(page, "overview")
            page.click("#scnBtn")
            page.wait_for_timeout(700)
            page.screenshot(path=str(OUT / f"ui2_drawer_{theme}_{kind}.png"))
            page.keyboard.press("Escape")
            if kind == "mobile":
                page.click("#filtBtn")
                page.wait_for_timeout(400)
                page.screenshot(path=str(OUT / f"ui2_filters_{theme}_mobile.png"))
                page.click("#filtClose")
            page.click("#asstBtn")
            page.fill("#asstQ", "сколько вагонов на семерке завтра в вечерний час пик")
            page.press("#asstQ", "Enter")
            page.wait_for_timeout(1500)
            page.screenshot(path=str(OUT / f"ui2_assistant_{theme}_{kind}.png"))
            if kind == "mobile":
                print("mobile overflow:", page.evaluate("document.documentElement.scrollWidth > innerWidth"))
            ctx.close()

    # ---------- panels used in README (light, desktop) ----------
    ctx = b.new_context(viewport={"width": 1440, "height": 900}, color_scheme="light", device_scale_factor=1)
    page = ctx.new_page()
    page.goto(BASE + "/", wait_until="domcontentloaded")
    wait_ready(page)
    page.screenshot(path=str(OUT / "day_all_light.png"))
    page.select_option("#route", "17")
    page.fill("#date", "2025-12-10")
    page.dispatch_event("#date", "change")
    wait_ready(page)
    panel(page, "#fleetCard", "panel_fleet.png")
    drawer(page, True)
    page.eval_on_selector("#kLevel", "el => { el.value = 1.03; el.dispatchEvent(new Event('input')); }")
    page.select_option("#eRoute", "17")
    page.fill("#eFrom", "2025-12-10"); page.fill("#eTo", "2025-12-10")
    page.select_option("#eH0", "16"); page.select_option("#eH1", "21")
    page.click(".ghost-btn[data-k='1.2']")
    page.click("#eAdd")
    page.fill("#wDate", "2025-12-10"); page.fill("#wMm", "10"); page.fill("#wT", "-15")
    page.click("#wAdd")
    wait_ready(page)
    page.locator("#adjCard").screenshot(path=str(OUT / "panel_corrections.png"))
    page.locator("#trafficCol").screenshot(path=str(OUT / "r4_traffic_coefficient.png"))
    drawer(page, False)
    panel(page, "#fleetCard", "panel_fleet_corrected.png")
    view(page, "overview")
    page.screenshot(path=str(OUT / "corrections_route17.png"))
    drawer(page, True)
    page.click("#adjReset")
    drawer(page, False)
    view(page, "analytics")
    page.click("#horizon button[data-h=year]")
    wait_ready(page)
    panel(page, "#lineChart", "panel_year.png")
    page.click("#horizon button[data-h=month]")
    wait_ready(page)
    panel(page, "#lineChart", "panel_month.png")
    page.click("#horizon button[data-h=day]")
    view(page, "overview")
    wait_ready(page)
    panel(page, "#lineChart", "ai_interval_day.png")
    panel(page, "#kpis", "ai_kpi_overflow.png")
    panel(page, "#riskCard", "ui2_rail_risk.png")
    show(page, "#fP90")
    page.check("#fP90", force=True)
    wait_ready(page)
    panel(page, "#fleetCard", "ai_fleet_p90.png")
    page.uncheck("#fP90", force=True)
    page.select_option("#route", "12")  # April: 1–4 Apr drop found by the detector (likely diversion)
    view(page, "analytics")
    page.click("#horizon button[data-h=month]")
    page.select_option("#month", "2025-04")
    wait_ready(page)
    panel(page, "#lineChart", "ai_anomalies_month.png")
    panel(page, "#anomCard", "ai_anomalies_panel.png")
    page.select_option("#month", "2025-12")
    if page.is_visible("#modelSeg button[data-m=hybrid]"):
        page.click("#modelSeg button[data-m=hybrid]")
    view(page, "analytics")
    wait_ready(page)
    panel(page, "#lineChart", "ai_interval_month_hybrid.png")
    panel(page, "#modelCard", "ai_model_panel.png")
    page.eval_on_selector("#asstBtn", "b => b.click()")
    for q in ("Где завтра переполнение?", "сколько вагонов на семерке завтра в вечерний час пик"):
        page.fill("#asstQ", q)
        page.press("#asstQ", "Enter")
        page.wait_for_timeout(1200)
    page.locator("#asst").screenshot(path=str(OUT / "ai_assistant.png"))
    page.eval_on_selector_all(".qcard [data-act=edit]", "bs => bs[bs.length - 1].click()")
    page.wait_for_timeout(300)
    page.locator("#asst").screenshot(path=str(OUT / "r4_assistant_edit.png"))
    page.click("#asstClose")
    page.select_option("#route", "5")
    view(page, "analytics")
    page.select_option("#month", "2025-10")
    wait_ready(page)
    panel(page, ".chart-wrap:has(#lineChart)", "r4_empty_state.png")
    panel(page, ".topbar", "r4_header.png")
    ctx.close()
    b.close()
print("saved to", OUT)
