# -*- coding: utf-8 -*-
"""QMT xtdata 行情接口验证脚本。

用法：
    python scripts/qmt_test_xtdata.py [host] [port]

默认连接 127.0.0.1:58600（国金完整版 QMT 实际监听端口）。
miniQMT 正常运行时通常可不带参数直接让 xtdata 自动发现服务（去掉 connect 行即可）。

判断标准：
- getFullTick / getTradingDatesByMarket / supplyHistoryData 报 200005「未找到处理函数」
  => 服务端没加载行情 handler（国金完整版的现状）
- get_stock_list_in_sector 能返回 => RPC 通道本身正常
"""
import sys
from xtquant import xtdata

host = sys.argv[1] if len(sys.argv) > 1 else '127.0.0.1'
port = int(sys.argv[2]) if len(sys.argv) > 2 else 58600

xtdata.enable_hello = False
c = xtdata.connect(host, port)
print('connected:', c is not None and c.is_connected())

code = '000001.SZ'

def t(name, fn):
    try:
        r = fn()
        ok = r is not None and r != {} and r != []
        print('[%s] %s' % ('OK ' if ok else 'EMPTY', name))
        if ok:
            print('       ', str(r)[:300].replace('\n', ' | '))
    except Exception as e:
        print('[FAIL]', name, '->', str(e)[:200])

t('get_instrument_detail', lambda: xtdata.get_instrument_detail(code))
t('get_full_tick', lambda: xtdata.get_full_tick([code]))
t('get_market_data_ex(1d)', lambda: xtdata.get_market_data_ex([], [code], period='1d', count=3))
t('get_local_data(1d)', lambda: xtdata.get_local_data([], [code], period='1d', count=3))
t('download_history_data', lambda: xtdata.download_history_data(code, period='1d'))
t('get_divid_factors', lambda: xtdata.get_divid_factors(code))
t('get_stock_list_in_sector(沪深A股)', lambda: len(xtdata.get_stock_list_in_sector('沪深A股') or []))
print('DONE')
