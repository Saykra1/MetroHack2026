import duckdb
con = duckdb.connect()
q = lambda w: con.execute(f"""select cast(regexp_extract(rt,'^([0-9]+)',1) as int) route, extract(hour from ts) h, count(*) n
 from 'experiments/raw.parquet' where {w} and vr='1' group by 1,2 order by 1,2""").df()
df = q("ts>='2025-11-01'"); print(df); df.to_csv('experiments/leak_nov01.csv', sep=';', index=False)
print(q("ts>='2025-10-01' and ts<'2025-10-01 02:00'"))
