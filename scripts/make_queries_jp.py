import os
from pathlib import Path

out = Path('maple_prebb/queries_jp.txt')
out.parent.mkdir(parents=True, exist_ok=True)

years_main = ['2006','2007','2008']
jobs = [
    '戦士','ファイター','ページ','スピアマン','クルセイダー','ホワイトナイト','ドラゴンナイト','ヒーロー','パラディン','ダークナイト',
    '魔法使い','氷雷','火毒','クレリック','プリースト','ビショップ',
    '弓使い','ハンター','レンジャー','ボウマスター','クロスボウマスター',
    '盗賊','アサシン','ハーミット','ナイトロード','シーフ','バンディット','チーフバンディット','斬り賊','投げ賊',
    '海賊','ガンスリンガー','アウトロー','インファイター','バッカニア','拳'
]
base_kw = ['ブログ','日記','攻略','育成','スキル振り','狩場','時給','クエスト','ドロップ','相場','露店','考察','検証','装備','強化','ステータス','振り方','テンプレ','まとめ','Wiki']

hosts = [
    'site:fc2.com','site:xrea.com','site:seesaa.net','site:livedoor.jp','site:cocolog-nifty.com','site:jugem.jp','site:yaplog.jp',
    'site:geocities.jp','site:exblog.jp','site:ameblo.jp','site:wikiwiki.jp','site:ninja-web.net'
]

host_kws = ['メイプル 2006','メイプル 2007','メイプル 2008','メイプル 攻略 2007','メイプル 日記 2006','メイプル 斬り賊 2007']

maps_terms = ['ビシャス','ジャクム','姫','金融','武器庫','河童','提灯','卵','骨','クルー','オハゼ','駐車場','黒字','赤字','命中','必中','MH','SE','TT','HS']

qs = []
# job x base_kw x year
for j in jobs:
    for kw in ['ブログ','攻略','育成','スキル振り','狩場']:
        for y in years_main:
            qs.append(f'メイプル {j} {kw} {y}')
# generic kw x year
for kw in base_kw:
    for y in years_main:
        qs.append(f'メイプル {kw} {y}')
# host-limited
for h in hosts:
    for kw in host_kws:
        qs.append(f'{h} {kw}')
# map/boss terms x year
for t in maps_terms:
    for y in years_main:
        qs.append(f'メイプル {t} 攻略 {y}')

# de-dup and cap
seen = set()
uniq = []
for q in qs:
    if q not in seen:
        seen.add(q)
        uniq.append(q)

# cap to 400 lines to keep reasonable size
uniq = uniq[:400]

out.write_text('\n'.join(uniq), encoding='utf-8')
print('written', len(uniq), 'queries to', out)
