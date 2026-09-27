"""Browser regression / acceptance tests (headless Chrome via Playwright). Skipped when Playwright or Chrome is absent.

- Round 4 bug: charts drawn while hidden kept ECharts' 100 px fallback canvas → ResizeObserver per chart container.
- Round 5 (docs/UI_PLAN.md §7): every view × light/dark × 1440/390 px renders without JS errors or horizontal scroll,
  S1 on the first screen at 1440×900, «Сценарий» drawer, assistant «Применить» → «Обзор», assistant example chips
  keep their height after many questions (coordinator's flex fix).
"""
import socket
import threading
import time

import pytest

pw = pytest.importorskip("playwright.sync_api")

VIEWS = ["overview", "fleet", "analytics", "anomalies", "model"]
CHART_JS = """[...document.querySelectorAll('.view.active .chart')].filter(el => el.offsetParent).map(el => {
  const cv = el.querySelector('canvas');
  return {id: el.id, box: el.clientWidth, canvas: cv ? parseInt(cv.style.width) : 0}; })"""


@pytest.fixture(scope="module")
def base_url():
    import uvicorn

    from app.main import app

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    t.join(timeout=5)


@pytest.fixture(scope="module")
def browser():
    with pw.sync_playwright() as p:
        try:
            b = p.chromium.launch(channel="chrome", headless=True)
        except Exception:
            try:
                b = p.chromium.launch(headless=True)
            except Exception as e:  # no browser binaries on this machine
                pytest.skip(f"no Chromium available: {e}")
        yield b
        b.close()


def _ready(page):
    page.wait_for_function("document.querySelectorAll('#routeTable tbody tr').length > 0", timeout=30000)
    page.wait_for_timeout(900)


def _page(browser, width, height=900, theme="light"):
    page = browser.new_page(viewport={"width": width, "height": height}, color_scheme=theme)
    # basemap tiles and web fonts are cosmetic and come from slow external CDNs: block them so the suite is deterministic
    page.route(lambda u: "basemaps.cartocdn.com" in u or "fonts.g" in u or "tile.openstreetmap" in u, lambda r: r.abort())
    page.set_default_navigation_timeout(60000)
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: m.type == "error" and "Failed to load resource" not in m.text and errors.append(m.text))
    return page, errors


def _filters(page, fn):
    """Run fn with the filters visible (on phones they live in the «Фильтры» sheet)."""
    sheet = page.is_visible("#filtBtn")
    if sheet:
        page.click("#filtBtn")
    fn()
    if sheet and page.evaluate("document.body.classList.contains('filters-open')"):
        page.click("#filtClose")


@pytest.mark.parametrize("width", [1440, 390])
def test_charts_render_after_hidden_start(browser, base_url, width):
    page, errors = _page(browser, width)
    page.add_init_script("document.addEventListener('DOMContentLoaded', () => "
                         "{ document.querySelector('main').style.display = 'none'; })")
    page.goto(base_url + "/", wait_until="domcontentloaded")
    _ready(page)
    page.evaluate("document.querySelector('main').style.display = ''")
    page.wait_for_timeout(800)
    charts = page.evaluate(CHART_JS)
    assert charts and all(abs(c["canvas"] - c["box"]) <= 2 for c in charts), charts
    assert not errors, errors
    page.close()


@pytest.mark.parametrize("width", [1440, 390])
@pytest.mark.parametrize("theme", ["light", "dark"])
def test_every_view(browser, base_url, width, theme):
    page, errors = _page(browser, width, theme=theme)
    page.goto(base_url + "/#overview", wait_until="domcontentloaded")
    _ready(page)
    for v in VIEWS:
        page.click(f"#tab-{v}")
        page.wait_for_timeout(700)
        assert page.is_visible(f"#view-{v}") and page.evaluate("location.hash") == f"#{v}"
        assert page.get_attribute(f"#tab-{v}", "aria-selected") == "true"
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (v, width)
        charts = page.evaluate(CHART_JS)
        assert all(c["box"] > 0 and abs(c["canvas"] - c["box"]) <= 2 for c in charts), (v, charts)
    # hash routing without reload + back button
    page.goto(base_url + "/#model", wait_until="domcontentloaded")
    page.wait_for_timeout(400)
    assert page.is_visible("#view-model") and not page.is_visible("#view-overview")
    page.go_back()
    page.wait_for_timeout(400)
    assert not errors, errors
    page.close()


def test_horizons_routes_no_errors(browser, base_url):
    page, errors = _page(browser, 390, 844)
    page.goto(base_url + "/#analytics", wait_until="domcontentloaded")
    _ready(page)
    for route in ("all", "7", "17"):
        _filters(page, lambda: page.select_option("#route", route))
        for h in ("day", "month", "year"):
            _filters(page, lambda: page.click(f"#horizon button[data-h={h}]"))
            _ready(page)
            n = page.evaluate("echarts.getInstanceByDom(document.getElementById('lineChart')).getOption().series.length")
            assert n > 0, (route, h)
        _filters(page, lambda: page.click("#horizon button[data-h=day]"))
    assert not errors, errors
    page.close()


def test_s1_first_screen(browser, base_url):
    """S1: KPIs + map + risky hours visible without scrolling at 1440×900."""
    page, errors = _page(browser, 1440, 900)
    page.goto(base_url + "/", wait_until="domcontentloaded")
    _ready(page)
    page.wait_for_function("document.querySelectorAll('#riskList .risk-item').length > 0", timeout=20000)
    for sel in ("#kpis", "#map", "#riskList .risk-item"):
        box = page.locator(sel).first.bounding_box()
        assert box and box["y"] >= 0 and box["y"] + min(box["height"], 60) <= 900, (sel, box)
    assert page.locator("#kpis").bounding_box()["y"] + page.locator("#kpis").bounding_box()["height"] <= 900
    assert not errors, errors
    page.close()


@pytest.mark.parametrize("width", [1440, 390])
def test_scenario_drawer(browser, base_url, width):
    page, errors = _page(browser, width)
    page.goto(base_url + "/#overview", wait_until="domcontentloaded")
    _ready(page)
    before = page.inner_text("#kTotal")
    page.click("#scnBtn")
    page.wait_for_timeout(400)
    assert page.is_visible("#drawer") and page.get_attribute("#scnBtn", "aria-expanded") == "true"
    page.eval_on_selector("#kLevel", "el => { el.value = 1.2; el.dispatchEvent(new Event('input')); }")
    page.wait_for_function("document.getElementById('scnBadge').textContent === '1' && "
                           "document.getElementById('adjDelta').textContent.includes('стало')", timeout=15000)
    assert page.inner_text("#scnBadge") == "1" and page.is_visible("#scnBadge")
    assert "стало" in page.inner_text("#adjDelta")
    page.keyboard.press("Escape")  # Esc closes the drawer; numbers on «Обзор» follow the scenario
    page.wait_for_timeout(400)
    assert not page.is_visible("#drawer")
    page.wait_for_function("t => document.getElementById('kTotal').textContent !== t", arg=before, timeout=15000)
    page.click("#scnBtn")
    page.wait_for_timeout(300)
    page.click("#adjReset")
    page.wait_for_function("t => document.getElementById('kTotal').textContent === t", arg=before, timeout=15000)
    assert not page.is_visible("#scnBadge")
    # focus stays inside the drawer (trap)
    for _ in range(40):
        page.keyboard.press("Tab")
    assert page.evaluate("document.getElementById('drawer').contains(document.activeElement)")
    page.keyboard.press("Escape")
    assert not errors, errors
    page.close()


@pytest.mark.parametrize("width", [1440, 390])
def test_assistant_apply_goes_to_overview(browser, base_url, width):
    page, errors = _page(browser, width, 844)
    page.goto(base_url + "/#model", wait_until="domcontentloaded")
    _ready(page)
    page.click("#asstBtn")
    page.fill("#asstQ", "сколько вагонов на 17 маршруте завтра в 8 утра")
    page.press("#asstQ", "Enter")
    page.wait_for_selector(".qcard [data-act=apply]", timeout=15000)
    page.click(".qcard [data-act=apply]")
    page.wait_for_timeout(1200)
    assert page.evaluate("location.hash") == "#overview" and page.is_visible("#view-overview")
    assert page.input_value("#route") == "17" and page.input_value("#hour") == "8"
    assert not errors, errors
    page.close()


def test_assistant_example_chips_keep_height(browser, base_url):
    """Regression (coordinator's fix): after many answers the example chips must not be squeezed to 0 px."""
    page, errors = _page(browser, 1440, 900)
    page.goto(base_url + "/", wait_until="domcontentloaded")
    _ready(page)
    page.click("#asstBtn")
    for q in ("где завтра переполнение", "сколько вагонов на 17 маршруте в 8 утра", "час пик на 11 маршруте в пятницу",
              "пассажиры на семерке послезавтра вечером", "аномалии на 12 маршруте в апреле"):
        n = page.evaluate("document.querySelectorAll('.msg.a').length")
        page.fill("#asstQ", q)
        page.press("#asstQ", "Enter")
        page.wait_for_function("n => document.querySelectorAll('.msg.a:not(.thinking)').length > n", arg=n, timeout=15000)
    h = page.evaluate("document.getElementById('asstEx').getBoundingClientRect().height")
    assert h >= 30, h
    assert page.evaluate("document.getElementById('asstLog').scrollHeight > document.getElementById('asstLog').clientHeight")
    assert not errors, errors
    page.close()
