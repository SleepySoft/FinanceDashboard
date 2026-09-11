# -*- coding: utf-8 -*-
"""QMT xttrader 交易接口验证脚本。

用法：
    set QMT_ACCOUNT=你的资金账号
    python scripts/qmt_test_xttrader.py

要点：
- XtQuantTrader(path, session) 第一个参数是 userdata 目录，第二个是会话号（int），顺序别搞反
- path 指向 miniQMT 的 userdata_mini；完整版 QMT 的 userdata 会 connect() 返回 -1
- connect() 返回 0=成功，-1=失败（国金完整版实测为 -1）
- 本脚本只查询资产/持仓，绝不下单
"""
import os
import sys
from xtquant import xttrader
from xtquant.xttype import StockAccount

SESSION = int(os.environ.get('QMT_SESSION', '919001'))
# miniQMT 登录成功后用 userdata_mini；完整版用 userdata（但会 -1）
USERDATA = os.environ.get('QMT_USERDATA', r'D:\国金证券QMT交易端\userdata_mini')
ACC = os.environ.get('QMT_ACCOUNT', '')

if not ACC:
    print('请先 set QMT_ACCOUNT=资金账号')
    sys.exit(1)

print('[1] XtQuantTrader start/connect ...  userdata =', USERDATA)
t = xttrader.XtQuantTrader(USERDATA, SESSION)
t.start()
r = t.connect()
print('    connect() ->', r, '(0=成功, -1=失败)')

if r == 0:
    print('[2] subscribe + 查资产/持仓 ...')
    acc = StockAccount(ACC)
    print('    subscribe() ->', t.subscribe(acc))
    try:
        asset = t.query_stock_asset(acc)
        if asset:
            print('    资产: 总资产=%.2f 可用=%.2f 市值=%.2f' % (asset.total_asset, asset.cash, asset.market_value))
        else:
            print('    资产: EMPTY')
    except Exception as e:
        print('    资产查询失败:', str(e)[:200])
    try:
        positions = t.query_stock_positions(acc)
        print('    持仓: %d 只' % (len(positions) if positions else 0))
        for p in (positions or [])[:10]:
            print('      %s %s 持仓=%s 可用=%s 成本=%.3f' % (
                p.stock_code, p.stock_name, p.volume, p.can_use_volume, p.open_price))
    except Exception as e:
        print('    持仓查询失败:', str(e)[:200])
else:
    print('[2] 连接失败，跳过账户查询')

print('XTTRADER TEST DONE')
