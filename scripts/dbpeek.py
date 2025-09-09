import sys, sqlite3, os

path = sys.argv[1] if len(sys.argv) > 1 else "index/maple.db"
print("db:", path, "exists:", os.path.exists(path))
if not os.path.exists(path):
    sys.exit(0)
con = sqlite3.connect(path)
cur = con.cursor()
try:
    c = list(cur.execute("select count(*) from pages"))[0][0]
    print("pages:", c)
    for row in cur.execute("select url, title, wayback_timestamp from pages limit 5"):
        print("-", row)
finally:
    con.close()

