import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from maple_prebb.cdx import cdx_iter

pattern = sys.argv[1]
match = sys.argv[2] if len(sys.argv) > 2 else "prefix"
for i, row in enumerate(cdx_iter(pattern, to_ts="20091231", match_type=match, page_size=10, max_pages=1)):
    if i >= 10:
        break
    print(row)
