"""Scan raw validations (10 GB) with DuckDB: leak hunt + consistency checks."""
import duckdb, sys, time
import os; os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
con = duckdb.connect()
con.execute("PRAGMA threads=12; PRAGMA memory_limit='12GB'")
t = time.time()
src = "read_csv(['train.csv','test.csv'], delim=';', header=true, all_varchar=true, filename=true, quote='', escape='', strict_mode=false, null_padding=true, ignore_errors=true, sample_size=200000)"
con.execute(f"""CREATE TABLE r AS SELECT filename AS f, device_no, crd_hashcode AS card,
  TRY_CAST(tran_date_time AS TIMESTAMP) ts, TRY_CAST(input_date_time AS TIMESTAMP) its,
  validation_result vr, tran_type_id tt, place_id, good_type, ngpt_route rt, bus_exit_no ex, garage_number gn
  FROM {src}""")
print("loaded", con.execute("select count(*) from r").fetchone(), round(time.time()-t), "s", flush=True)
con.execute("COPY r TO 'experiments/raw.parquet' (FORMAT parquet)")
q = lambda s: print(s, "\n", con.execute(s).df().to_string(), "\n", flush=True)
q("select f, min(ts), max(ts), count(*) from r group by 1")
q("select f, strftime(ts,'%Y-%m') m, count(*) n, sum((vr='1')::int) ok from r where ts>='2025-10-25' or ts<'2025-01-02' group by 1,2 order by 1,2")
q("select rt, count(*) n, sum((vr='1')::int) ok from r group by 1 order by 2 desc")
q("select vr, count(*) from r group by 1 order by 2 desc")
q("select tt, count(*) from r group by 1 order by 2 desc")
q("select good_type, count(*) from r group by 1 order by 2 desc limit 25")
q("select place_id, count(*) from r group by 1 order by 2 desc")
q("select strftime(its,'%Y-%m') m, count(*) from r where its>='2025-11-01' or its<'2025-01-01' group by 1 order by 1")
q("select date_trunc('day',ts) d, count(*) from r where ts>='2025-10-30' group by 1 order by 1")
