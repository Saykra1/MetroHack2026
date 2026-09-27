"""Ingest → normalise → aggregate raw validations (62M rows, ~10 GB CSV) with DuckDB in ~1 min on a laptop.
Steps: parse CSV (lenient) → typed columns → keep successful validations (validation_result=1) → route from ngpt_route
→ drop duplicates (device_no, tran_no, ts) → timestamp = tran_date_time (input_date_time is unreliable)
→ hourly boardings per route (+ unique cards, device counts) → verify against organizer labels.
Usage: python src/pipeline_ingest.py [csv ...]   (default: train.csv test.csv)"""
import duckdb, sys, os, time
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
files = sys.argv[1:] or ['train.csv', 'test.csv']
con = duckdb.connect(); con.execute("PRAGMA threads=8")
t0 = time.time()
opts = "delim=';', header=true, all_varchar=true, quote='', escape='', strict_mode=false, null_padding=true, ignore_errors=true"
con.execute(f"""
CREATE OR REPLACE VIEW raw AS SELECT * FROM read_csv({files}, {opts});
CREATE OR REPLACE TABLE clean AS
SELECT DISTINCT
  TRY_CAST(tran_date_time AS TIMESTAMP)                          AS ts,
  TRY_CAST(regexp_extract(ngpt_route, '^([0-9]+)', 1) AS INT)    AS route,
  device_no, tran_no, crd_hashcode AS card, good_type, garage_number, bus_exit_no
FROM raw
WHERE validation_result = '1' AND ngpt_route LIKE '%трамвай%' AND TRY_CAST(tran_date_time AS TIMESTAMP) IS NOT NULL;
""")
n_raw = con.execute("SELECT count(*) FROM raw").fetchone()[0]; n_clean = con.execute("SELECT count(*) FROM clean").fetchone()[0]
con.execute("""COPY (SELECT route, CAST(ts AS DATE) AS date, hour(ts) AS hour, count(*) AS boardings,
                      count(DISTINCT card) AS unique_cards, count(DISTINCT garage_number) AS vehicles
               FROM clean GROUP BY ALL ORDER BY ALL) TO 'experiments/hourly_boardings.csv' (HEADER, DELIMITER ';')""")
chk = con.execute("""
  WITH mine AS (SELECT * FROM read_csv('experiments/hourly_boardings.csv', delim=';', header=true)),
       lab  AS (SELECT * FROM read_csv(['labels/labels_day_train.csv','labels/labels_day_test.csv'], delim=';', header=true))
  SELECT count(*) cells, sum((m.boardings = l.boardings)::INT) exact, sum(abs(m.boardings - l.boardings)) abs_diff, sum(l.boardings) total
  FROM lab l LEFT JOIN mine m USING (route, date, hour)""").fetchone()
report = (f"# Ingest report\n- files: {files}\n- raw rows: {n_raw:,}\n- clean successful validations: {n_clean:,}\n"
          f"- labels cells: {chk[0]:,}, exact match: {chk[1]:,} ({chk[1]/chk[0]:.2%}), abs diff: {chk[2]:,} of {chk[3]:,}\n"
          f"- runtime: {time.time()-t0:.0f} s\n")
open('experiments/ingest_report.md', 'w', encoding='utf-8').write(report); print(report)
