import pymysql
from datetime import date

conn = pymysql.connect(host='localhost', port=3306, user='root', password='root', database='shoplazza_dashboard', charset='utf8mb4')
c = conn.cursor()

c.execute("SELECT DATE(time_hour) as d FROM shoplazza_overview_hourly GROUP BY d ORDER BY d")
dates = [r[0] for r in c.fetchall()]

for d in dates:
    c.execute("""SELECT SUM(total_gmv), SUM(total_orders), MAX(total_visitors)
        FROM shoplazza_overview_hourly WHERE DATE(time_hour)=%s""", (d,))
    gmv, orders, visitors = c.fetchone()
    if not orders: continue
    aov = gmv / orders if orders else 0

    c.execute("""SELECT COALESCE(SUM(spend),0) FROM fb_ad_account_spend_hourly
        WHERE DATE(time_hour)=%s AND owner='张三'""", (d,))
    fb_spend = c.fetchone()[0]

    c.execute("""INSERT INTO owner_daily_summary (date, owner, total_gmv, total_orders, total_visitors, avg_order_value, total_spend, tt_total_spend)
        VALUES (%s,'张三',%s,%s,%s,%s,%s,0)
        ON DUPLICATE KEY UPDATE total_gmv=VALUES(total_gmv), total_orders=VALUES(total_orders),
        total_visitors=VALUES(total_visitors), avg_order_value=VALUES(avg_order_value), total_spend=VALUES(total_spend)""",
        (d, gmv, orders, visitors, aov, fb_spend))

conn.commit()
c.execute("SELECT COUNT(*) FROM owner_daily_summary")
print(f"owner_daily_summary rows: {c.fetchone()[0]}")
conn.close()
