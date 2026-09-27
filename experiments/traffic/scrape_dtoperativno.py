"""Scrape public Telegram channel preview t.me/s/DtOperativno (Дептранс. Оперативно,
official channel of Moscow Transport Dept) for 2025 posts containing the ЦОДД road-load
score ("загруженность дорог составляет N баллов") and average speed ("N км/ч").

Output: experiments/traffic/dtop_messages.jsonl (raw posts) — parsed by build_traffic.py.
Usage: python experiments/traffic/scrape_dtoperativno.py
"""
import json, re, html, time, os, urllib.request

CH = "DtOperativno"
OUT = os.path.join(os.path.dirname(__file__), "dtop_messages.jsonl")
# message ids 19800..24520 cover 2024-12-23 .. 2026-01-09 (found by probing ?before=N)


def fetch(before):
    url = f"https://t.me/s/{CH}?before={before}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    for k in range(4):
        try:
            return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
        except Exception as e:  # noqa
            time.sleep(2 + 3 * k)
    return ""


def parse(s):
    out = []
    for b in re.split(r"tgme_widget_message_wrap", s)[1:]:
        pid = re.search(r'data-post="[^/]+/(\d+)"', b)
        d = re.search(r'datetime="([^"]+)"', b)
        m = re.search(r"(?s)tgme_widget_message_text[^>]*>(.*?)</div>", b)
        if not (pid and d):
            continue
        t = html.unescape(re.sub(r"<[^>]+>", " ", m.group(1))) if m else ""
        out.append({"id": int(pid.group(1)), "dt": d.group(1), "text": re.sub(r"\s+", " ", t).strip()})
    return out


def main():
    from concurrent.futures import ThreadPoolExecutor
    befores = list(range(19800, 24520, 20))
    seen = {}
    with ThreadPoolExecutor(8) as ex:
        for i, page in enumerate(ex.map(lambda b: parse(fetch(b)), befores)):
            for r in page:
                seen[r["id"]] = r
            if i % 20 == 0:
                print(i, len(befores), len(seen), flush=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for k in sorted(seen):
            f.write(json.dumps(seen[k], ensure_ascii=False) + "\n")
    ids = sorted(seen); print("msgs", len(ids), "id range", ids[0], ids[-1], "missing ids", ids[-1] - ids[0] + 1 - len(ids))


if __name__ == "__main__":
    main()
