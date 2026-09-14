.. _institutional:

*************
 institutional
*************

:mod:`twstock.institutional` 可擷取台股**三大法人**（外資、投信、自營商）全日市場買賣超。

資料來源
========

* 上市（TWSE）：`T86` 三大法人買賣超日報
* 上櫃（TPEx）：三大法人日交易資訊

回傳單位為**股**；可用 :func:`twstock.institutional.to_lots` 轉成張。

.. note::

   公開資料中的「投信」為投信**合計**買賣超，不含單一投信公司或券商分點明細。
   ``Institutional.broker_detail`` 欄位預留供後續擴充，目前固定為 ``None``。


快速使用
========

擷取某交易日全市場（上市 + 上櫃）::

    >>> from twstock import institutional
    >>> rows = institutional.fetch("2026-09-11")
    >>> rows[0]
    Institutional(date=datetime.date(2026, 9, 11), market='twse', code='...', ...)

只抓上市或上櫃::

    >>> twse_rows = institutional.fetch("20260911", markets=["twse"])
    >>> tpex_rows = institutional.fetch("2026-09-11", markets=["tpex"])

投信買超排行（前 10 名）::

    >>> top = institutional.top_by(rows, field="trust_net", limit=10)
    >>> [(r.code, r.name, institutional.to_lots(r.trust_net)) for r in top]


欄位說明
========

:class:`twstock.institutional.Institutional` 主要欄位：

* ``foreign_*``：外陸資（不含外資自營商）買進／賣出／買賣超
* ``foreign_dealer_*``：外資自營商
* ``trust_*``：投信
* ``dealer_self_*`` / ``dealer_hedge_*``：自營商自行買賣／避險
* ``dealer_net``：自營商買賣超（官方彙總或加總）
* ``total_net``：三大法人買賣超合計

非交易日或查無資料時，對應市場會回傳空 list（不會拋錯）。


與 twstock-radar
================

若需要盤後排程、規則掃市、Telegram／Email／Slack 通知與管理後台，
請使用獨立專案 `twstock-radar`（依賴本模組做資料擷取）。
