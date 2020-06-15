import time
import json
import bitmex
import datetime
import numpy as np
from dateutil.tz import tzutc
from bravado.exception import HTTPUnauthorized


class BitmexClient:
    def __init__(self, api_key=None, api_secret=None, test=True):
        self.client =\
            bitmex.bitmex(api_key=api_key, api_secret=api_secret, test=test)

    def __call__(self):
        return self.client

    @property
    def is_connected(self):  # [test]
        if not self.acc_balance:
            return False
        else:
            return True

    @property
    def acc_balance(self):
        try:
            return self.getWallet('amount')
        except HTTPUnauthorized:
            return False

    @property
    def unrealisedPnl_XBTUSD(self):
        return self.getXBTUSDPosition('unrealisedPnl')

    @property
    def open_contracts(self):
        return self.getXBTUSDPosition('currentQty')

    @property
    def current_price(self):
        return self.getXBTUSDPosition('lastPrice')

    @property
    def positionValue_XBTUSD(self):
        position_result = self.client.Position.Position_get(
            filter=json.dumps({'symbol': 'XBTUSD'})).result()[0][0]
        _open_contracts = position_result['currentQty']
        value = 0
        if _open_contracts > 0:
            value =\
                position_result['lastPrice'] - position_result['avgEntryPrice']
        else:
            value =\
                position_result['avgEntryPrice'] - position_result['lastPrice']
        return value

    def getHistory(self, symbol='XBTUSD', binSize='5m', count=15,
                   startTime=datetime.datetime.utcnow() - datetime.timedelta(
                       days=5)):
        return self.client.Trade.Trade_getBucketed(symbol=symbol,
                                                   binSize=binSize,
                                                   count=count,
                                                   startTime=startTime
                                                   ).result()

    def getXBTUSDPosition(self, prop):
        return self.client.Position.Position_get(
            filter=json.dumps({'symbol': 'XBTUSD'})).result()[0][0][str(prop)]

    def getWallet(self, prop):
        return self.client.User.User_getWallet().result()[0][str(prop)]

    def long_order(self, orderQty, sl, symbol='XBTUSD'):
        entry = self.client.Order.Order_new(
            symbol=symbol, ordType='Market', orderQty=orderQty).result()
        time.sleep(1)
        stoploss = self.client.Order.Order_new(
            symbol=symbol, ordType='MarketIfTouched', orderQty=-orderQty,
            price=round(self.getXBTUSDPosition('avgEntryPrice')-sl, 2)).result()
        return entry, stoploss

    def short_order(self, orderQty, sl, symbol='XBTUSD'):
        entry = self.client.Order.Order_new(
            symbol=symbol, ordType='Market', orderQty=-orderQty).result()
        time.sleep(1)
        stoploss = self.client.Order.Order_new(
            symbol=symbol, ordType='MarketIfTouched', orderQty=orderQty,
            price=round(self.getXBTUSDPosition('avgEntryPrice')+sl, 2)).result()
        return entry, stoploss

    def close_all(self):
        return self.client.Order.Order_new(symbol='XBTUSD',
                                           ordType='Market',
                                           execInst='Close').result()


class BitmexData:
    def __init__(self, client, symbol="XBTUSD", interval=15, timeframe=5,
                 refresh_limit=20, initialLoad=20):
        self.client = client
        self._hist = []
        self._symbol = symbol
        self._firstCall = False
        self._interval = interval
        self._timeframe = timeframe
        self._candle_load = self._interval // timeframe
        self._refresh_limit = refresh_limit  # seconds
        """these buffers are filled to be the close, high, low in the right
        time interval. they only will get filled as big as appropriate"""
        self._C = []
        self._H = []
        self._L = []
        # initiate the filling of the close, high, low buffers _C, _H, _L
        self.convert_to_interval(self.load_candles(initialLoad),
                                 self._interval, start=self._candle_load)
        # initial True Range Values fill-up
        self._TR = [self.true_range(i) for i in range(1, len(self._C))]
        self._last_minute = 0  # for checking if new candle exists
        assert interval % 5 == 0 or interval == 1, "interval must be \
            dividable by 5!"
        assert timeframe in [1, 5, 60], "wrong timeframe!"

    def __call__(self, buffer_size=500):
        # resize buffers
        if len(self._C) == buffer_size:
            self._C.drop(0)
            self._H.drop(0)
            self._L.drop(0)
            self._TR.drop(0)
        # add new values to _O, _H, _L buffers to be able to calculate features
        if self._firstCall:
            self.get_last_candle(self._candle_load)
        else:
            diff = (datetime.datetime.utcnow().minute
                    - self.minute())
            if diff < 0:
                diff = 60 - abs(diff)
            self.get_last_candle(diff // self._timeframe)
            self._firstCall = True
        # add new TR value to buffer
        self._TR.append(self.true_range(-1))

    @property
    def SL(self):
        return np.mean(self._TR) * 2

    def minute(self, index=-1):
        return self._hist[0][index]['timestamp'].minute

    def close(self, index=-1):
        return self._hist[0][index]['close']

    def high(self, index=-1):
        return self._hist[0][index]['high']

    def low(self, index=-1):
        return self._hist[0][index]['low']

    def true_range(self, i):
        return max(self._H[i] - self._L[i],
                   abs(self._H[i] - self._C[i-1]),
                   abs(self._L[i] - self._C[i-1]))

    def close_dists(self):
        return [(self._C[-1-x] - self._C[-1]) / self.SL for x in range(10)]

    def high_dists(self):
        return [(self._H[-1-x] - self._H[-1]) / self.SL for x in range(2)]

    def low_dists(self):
        return [(self._L[-1-x] - self._L[-1]) / self.SL for x in range(2)]

    def load_candles(self, candles):
        # candles: candle amount to load
        count = candles * self._timeframe  # in minutes
        binSize = str(self._timeframe) + "m"
        now = datetime.datetime.utcnow()
        count += now.minute % self._timeframe  # tzinfo=tzutc()
        startTime = now - datetime.timedelta(minutes=count)
        return self.client.getHistory(symbol=self._symbol,
                                      binSize=binSize, count=count,
                                      startTime=startTime.replace(tzinfo=tzutc()))

    def convert_to_interval(self, interval, start=0):
        for i in range(start, len(self._hist[0])):
            if self.minute(self._hist, i) % interval == 0:
                self._C.append(self.close(self._hist, -1))
                self._H.append(
                    max([self.high(
                            self._hist, i-x) for x in range(self._candle_load)]))
                self._L.append(
                    max([self.low(
                            self._hist, i-x) for x in range(self._candle_load)]))
        self._last_minute = self.minute(self._hist)  # save the last minute

    def get_last_candle(self, load_count):
        self._hist = self.load_candles(load_count)
        start = time.time()
        while time.time() - start < self._max_limit:
            # check if the new candle is present
            if self._last_minute != self.minute(self._hist):
                self.convert_to_interval(self._hist, self._interval)
                break
            # wait 300 milliseconds and load history again
            time.sleep(0.3)
            # and try to only load the latest minute bar (not multiple again)
            self._hist = self.load_candles(load_count)


class BitmexTrade:
    def __init__(self, client, data, position_size):
        self.client = client
        self.data = data
        self._position_size = position_size / 100  # in % of account balance

    def __call__(self, act):
        open_contracts = self.client.open_contracts
        if open_contracts > 0:
            if open_contracts > 0:
                if act == 2:
                    self.close_trade()
            else:
                if act == 1:
                    self.close_trade()
        else:
            self.open_trade(act)

    def set_position_size(self, new_position_size):
        self._position_size = new_position_size

    def calc_pos_size(self, cp, sl):
        return (self.client.acc_balance * self._position_size * cp) // (sl / cp)

    def process_signal(self, act):
        entry, stoploss = {}, {}
        qty = self.calc_pos_size(self.client.current_price, self.data.SL)
        try:
            if act == 1:
                entry, stoploss = self.client.long_order(qty, self.data.SL)
            if act == 2:
                entry, stoploss = self.client.short_order(qty, self.data.SL)
        except Exception:
            print("Something went wrong while opening order! Response:",
                  "Entry Error {} Stoploss Error {}".format(entry, stoploss))

    def close_trade(self):
        close = {}
        try:
            close = self.client.close_all()
        except Exception:
            print("Something went wrong while closing order! Response:", close)