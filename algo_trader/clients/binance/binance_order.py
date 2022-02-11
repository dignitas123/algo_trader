import json
import math
import time
import uuid
import pickle
import sys
from algo_trader.clients.binance.binance_client import BinanceClient
from bravado.exception import HTTPBadRequest, HTTPNotFound


class BinanceOrder(BinanceClient):
    def __init__(self, symbols, settings, settings_path, magic='algo-trader', api_key=None, api_secret=None, testnet=True):
        self.settings = settings
        self.magic = magic
        self._settings_path = settings_path

        self.props = {}
        for symbol in symbols:
            self.props[symbol] = {
                'stoploss_id': '', 'stop_id': '', 'entry': .0, 'SL': .0, 'TP': .0, 'open': False, 'wait_stop': False, 'qty': 0}

        super().__init__(api_key=api_key, api_secret=api_secret, testnet=testnet)

    def check_open_bot_order(self, symbol, entry, sl):
        settings = pickle.load(open(self._settings_path, 'rb'))
        self.props[symbol]['stoploss_id'] = settings.symbols[symbol]['last_order_stoploss_id']
        self.props[symbol]['stop_id'] = settings.symbols[symbol]['last_order_stop_id']
        self.props[symbol]['SL'] = settings.symbols[symbol]['last_order_SL']
        if self.props[symbol]['stoploss_id']:
            try:
                res = self.client.Order.Order_getOrders(
                    filter=json.dumps({'symbol': symbol, 'open': True})).result()
                if res[0] and self.props[symbol]['stoploss_id'] in [order['clOrdID'] for order in res[0]]:
                    print('Bot order in {} open, stoploss might be modified'.format(
                        symbol), flush=True)
                    self.modifiy_stop(symbol, sl)
                    self.props[symbol]['entry'] = entry
                    self.props[symbol]['open'] = True
                    time.sleep(2)
            except HTTPBadRequest as e:
                print('Error getting orders.', e)
        if self.props[symbol]['stop_id']:
            try:
                res = self.client.client.Order.Order_getOrders(
                    filter=json.dumps({'symbol': symbol, 'open': True})).result()
                if res[0] and self.props[symbol]['stop_id'] in [order['clOrdID'] for order in res[0]]:
                    print('Bot order in {} open, stop will be deleted.'.format(
                        symbol), flush=True)
                    self.stoporder_cancel(symbol)
                    time.sleep(2)
            except HTTPBadRequest as e:
                print('Error getting orders.', e)

    def save_open_id(self, symbol, id, stop_type='normal'):
        settings = pickle.load(open(self._settings_path, 'rb'))
        if stop_type == 'normal':
            self.props[symbol]['stop_id'] = id
            settings.symbols[symbol]['last_order_stop_id'] = id
            pickle.dump(settings, file=open(self._settings_path, 'wb'))
        elif stop_type == 'stoploss':
            self.props[symbol]['stoploss_id'] = id
            settings.symbols[symbol]['last_order_stoploss_id'] = id
            settings.symbols[symbol]['last_order_SL'] = self.props[symbol]['SL']
            pickle.dump(settings, file=open(self._settings_path, 'wb'))
        else:
            print('No Stop Type given.')

    def manage_entries(self, symbols):
        for symbol in symbols:
            cp = self.client.get_current_price(symbol)
            if self.props[symbol]['wait_stop']:
                time.sleep(3)
                if self.props[symbol]['qty'] > 0 and cp >= self.props[symbol]['entry'] and self.client.open_contracts(symbol) != 0:
                    self.props[symbol]['wait_stop'] = False
                    self.props[symbol]['open'] = True
                    print('Long Position has been opened in {}, amending Stoploss to'.format(symbol),
                          self.props[symbol]['SL'], flush=True)
                    self.stoploss_order(symbol)
                elif self.props[symbol]['qty'] < 0 and cp <= self.props[symbol]['entry'] and self.client.open_contracts(symbol) != 0:
                    self.props[symbol]['wait_stop'] = False
                    self.props[symbol]['open'] = True
                    print('Short Position has been opened in {}, amending Stoploss to'.format(symbol),
                          self.props[symbol]['SL'], flush=True)
                    self.stoploss_order(symbol)
            elif self.props[symbol]['open']:
                if self.props[symbol]['qty'] > 0 and cp <= self.props[symbol]['SL'] and self.client.open_contracts(symbol) == 0:
                    self.props[symbol]['open'] = False
                    print('Long Position {} closed. {} Contracts from {} to {}. PnL in Points: {}'.format(symbol,
                                                                                                          self.props[symbol]['qty'], self.props[symbol]['entry'], self.props[symbol]['SL'], self.price_decimals(symbol, self.props[symbol]['SL']-self.props[symbol]['entry'])), flush=True)
                    self.props[symbol]['qty'] = 0
                elif self.props[symbol]['qty'] < 0 and cp >= self.props[symbol]['SL'] and self.client.open_contracts(symbol) == 0:
                    self.props[symbol]['open'] = False
                    print('Short Position {} closed. {} Contracts from {} to {}. PnL in Points: {}'.format(symbol,
                                                                                                           -self.props[symbol]['qty'], self.props[symbol]['entry'], self.props[symbol]['SL'], self.price_decimals(symbol, self.props[symbol]['entry']-self.props[symbol]['SL'])), flush=True)
                    self.props[symbol]['qty'] = 0

    def generate_id(self, symbol, _type='stop'):
        return '{}_{}_{}_{}'.format(self.magic, symbol, str(uuid.uuid4().fields[-1])[:5], _type)

    def price_decimals(self, symbol, price):
        if symbol == 'XBTUSD':
            return round(price * 2) / 2
        elif symbol == 'ETHUSD':
            return round(price * 20) / 20
        else:
            print('{} is not a valid symbol for price decimal rounding.'.format(symbol))
            sys.exit()

    def calc_pos_size(self, symbol, sl_distance):
        acc_balance = self.client.acc_balance(symbol)
        ps = float(self.settings.symbols[symbol]['position_size'])
        if symbol == 'XBTUSD':
            btc_usd = self.client.last_current_price(symbol)
            lot_step = 100
            riskvalue = (float(acc_balance) / 100000000) * \
                float(btc_usd) * (ps/100)  # riskvalue in usd
            pos_size = int(
                round((math.floor(riskvalue / (sl_distance / btc_usd)) / lot_step)) * lot_step)
        elif symbol == 'ETHUSD':
            tickvalue = 100
            lot_step = 1
            riskvalue = acc_balance * (ps/100)
            pos_size = int(
                round((math.floor(riskvalue / (sl_distance * tickvalue)) / lot_step)) * lot_step)
        else:
            print('Symbol not supported')
            sys.exit()
        if pos_size < lot_step:
            return lot_step
        else:
            return pos_size

    def stoploss_order(self, symbol, execPrice='LastPrice'):
        try:
            self.props[symbol]['stoploss_id'] = self.generate_id(
                symbol, _type='SL')
            self.save_open_id(
                symbol, self.props[symbol]['stoploss_id'], stop_type='stoploss')
            return self.client.client.Order.Order_new(
                symbol=symbol, ordType='Stop', clOrdID=self.props[symbol]['stoploss_id'], orderQty=-self.props[symbol]['qty'],
                stopPx=self.price_decimals(symbol, self.props[symbol]['SL']), execInst=execPrice
            ).result()
        except HTTPBadRequest as e:
            print('Error placing stoploss order.', e, flush=True)

    def order_cancel(self, symbol, orderId):
        try:
            order_res = self.client.client.Order.Order_cancel(
                clOrdID=orderId
            ).result()
            self.props[symbol]['wait_stop'] = False
            return order_res
        except (HTTPBadRequest, HTTPNotFound) as e:
            print('Error canceling order.', e, flush=True)

    def stoploss_cancel(self, symbol):
        self.order_cancel(symbol, self.props[symbol]['stoploss_id'])

    def stoporder_cancel(self, symbol):
        self.order_cancel(symbol, self.props[symbol]['stop_id'])

    def bracket_stop_order(self, symbol, orderQty, entry, sl, tp=0):
        try:
            self.props[symbol]['stop_id'] = self.generate_id(symbol)
            order_res = self.client.client.Order.Order_new(
                symbol=symbol, ordType='Stop', clOrdID=self.props[symbol]['stop_id'], orderQty=orderQty,
                stopPx=self.price_decimals(symbol, entry), execInst='LastPrice'
            ).result()
            self.save_open_id(symbol, self.props[symbol]['stop_id'])
            self.props[symbol]['qty'] = orderQty
            self.props[symbol]['wait_stop'] = True
            self.props[symbol]['SL'] = sl
            self.props[symbol]['TP'] = tp
            self.props[symbol]['entry'] = entry
            return order_res
        except HTTPBadRequest as e:
            print('Error placing bracket stop order in {}.'.format(
                symbol), e, flush=True)

    def bracket_market_order(self, symbol, orderQty, sl, cp, tp=0):
        try:
            entry = self.market_order(symbol, orderQty)
            self.props[symbol]['SL'] = sl
            self.props[symbol]['TP'] = tp
            time.sleep(5)
            stoploss = self.stoploss_order(symbol)
            self.props[symbol]['qty'] = orderQty
            self.props[symbol]['entry'] = cp
            return entry, stoploss
        except HTTPBadRequest as e:
            print('Error placing bracket market order in {}.'.format(
                symbol), e, flush=True)

    def market_order(self, symbol, orderQty):
        try:
            order_res = self.client.client.Order.Order_new(
                symbol=symbol, ordType='Market', orderQty=orderQty
            ).result()
            self.props[symbol]['qty'] = orderQty
            self.props[symbol]['open'] = True
            self.props[symbol]['wait_stop'] = False
            return order_res
        except HTTPBadRequest as e:
            print('Error placing market order.', e, flush=True)

    def modifiy_stop(self, symbol, newStopLoss):
        try:
            # could be clOrdID, not sure difference
            res = self.client.client.Order.Order_amend(
                origClOrdID=self.props[symbol]['stoploss_id'], stopPx=self.price_decimals(symbol,
                                                                                          newStopLoss)
            ).result()
            self.props[symbol]['SL'] = newStopLoss
            return res
        except HTTPBadRequest as e:
            if 'Invalid amend' in str(e):
                return 'noValChanged'
            elif 'Invalid origClOrdID' in str(e):
                return 'invalidID'
            else:
                return str(e)

    def close(self, symbol, qty=0):
        if not qty:
            qty = -self.props[symbol]['qty']
        if self.props[symbol]['open']:
            # note: have to delete stop too
            try:
                close = self.client.client.Order.Order_new(
                    symbol=symbol, ordType='Market', execInst='Close', orderQty=qty
                ).result()
                self.stoploss_cancel(symbol)
                return close
            except HTTPBadRequest as e:
                print('Error closing order in {}.'.format(symbol), e, flush=True)
        else:
            return False


api_key = ''
api_secret = ''

# binance live account
# api_key = ''
# api_secret = ''

client = BinanceClient(api_key=api_key, api_secret=api_secret, testnet=True)

print(client.get_histories())

# balance = client.client.futures_coin_account_balance()
# account = client.client.futures_account()

# print(balance)
# print(account)


# import math

# sym = 'BTCUSDT'

# symbol_info = client.client.get_symbol_info(sym)
# step_size = 0.0
# for f in symbol_info['filters']:
#     if f['filterType'] == 'LOT_SIZE':
#         step_size = float(f['stepSize'])

# quantity = 5

# precision = int(round(-math.log(step_size, 10), 0))
# quantity = float(round(quantity, precision))

# order = client.client.futures_create_order(symbol=sym, side='BUY', type='MARKET', quantity=quantity)

# klines = client.client.get_historical_klines("BTCUSDT", binanceClient.KLINE_INTERVAL_30MINUTE, "1 day ago UTC")

# print(klines)

'''
{
    'XBTUSD':
        (
            [
                {'timestamp': datetime.datetime(2021, 9, 24, 15, 15, tzinfo=tzutc()),
                'symbol': 'XBTUSD',
                'open': 42215.5, 'high': 42215.5, 'low': 42150.0, 'close': 42205.0,
                'trades': 16, 'volume': 1900, 'vwap': 42196.9416, 'lastSize': 100, 'turnover': 4502700, 'homeNotional': 0.045027, 'foreignNotional': 1900.0},
                {'timestamp': datetime.datetime(2021, 9, 24, 15, 10, tzinfo=tzutc()),
                'symbol': 'XBTUSD',
                'open': 42171.0, 'high': 42271.0, 'low': 42094.0, 'close': 42215.5, 'trades': 31, 'volume': 7200, 'vwap': 42178.0758, 'lastSize': 100, 'turnover': 17070498, 'homeNotional': 0.17070498, 'foreignNotional': 7200.0}, {'timestamp': datetime.datetime(2021, 9, 24, 15, 5, tzinfo=tzutc()), 'symbol': 'XBTUSD', 'open': 42354.5, 'high': 42354.5, 'low': 42171.0, 'close': 42171.0, 'trades': 18, 'volume': 5300, 'vwap': 42337.361, 'lastSize': 100, 'turnover': 12518507, 'homeNotional': 0.12518507, 'foreignNotional': 5300.0}, {'timestamp': datetime.datetime(2021, 9, 24, 15, 0, tzinfo=tzutc()), 'symbol': 'XBTUSD', 'open': 42363.0, 'high': 42363.0, 'low': 42187.0, 'close': 42354.5, 'trades': 15, 'volume': 7600, 'vwap': 42351.5261, 'lastSize': 100, 'turnover': 17945096, 'homeNotional': 0.17945095999999994, 'foreignNotional': 7600.0}, {'timestamp': datetime.datetime(2021, 9, 24, 14, 55, tzinfo=tzutc()), 'symbol': 'XBTUSD', 'open': 42247.5, 'high': 42363.0, 'low': 42169.5, 'close': 42363.0, 'trades': 23, 'volume': 10100, 'vwap': 42292.0605, 'lastSize': 200, 'turnover': 23881640, 'homeNotional': 0.23881639999999996, 'foreignNotional': 10100.0}, {'timestamp': datetime.datetime(2021, 9, 24, 14, 50, tzinfo=tzutc()), 'symbol': 'XBTUSD', 'open': 42363.0, 'high': 42363.0, 'low': 42168.5, 'close': 42247.5, 'trades': 30, 'volume': 10000, 'vwap': 42295.1014, 'lastSize': 100, 'turnover': 23643416, 'homeNotional': 0.23643415999999998, 'foreignNotional': 10000.0}, {'timestamp': datetime.datetime(2021, 9, 24, 14, 45, tzinfo=tzutc()), 'symbol': 'XBTUSD', 'open': 42305.0, 'high': 42363.0, 'low': 42307.5, 'close': 42363.0, 'trades': 18, 'volume': 5300, 'vwap': 42342.2012, 'lastSize': 200, 'turnover': 12517109, 'homeNotional': 0.12517109, 'foreignNotional': 5300.0}, {'timestamp': datetime.datetime(2021, 9, 24, 14, 40, tzinfo=tzutc()), 'symbol': 'XBTUSD', 'open': 42096.0, 'high': 42351.0, 'low': 42051.0, 'close': 42305.0, 'trades': 40, 'volume': 72700, 'vwap': 42122.2894, 'lastSize': 800, 'turnover': 172592829, 'homeNotional': 1.7259282900000006, 'foreignNotional': 72700.0}, {'timestamp': datetime.datetime(2021, 9, 24, 14, 35, tzinfo=tzutc()), 'symbol': 'XBTUSD', 'open': 41998.5, 'high': 42096.0, 'low': 41987.5, 'close': 42096.0, 'trades': 41, 'volume': 44100, 'vwap': 42055.8586, 'lastSize': 100, 'turnover': 104860813, 'homeNotional': 1.0486081299999999, 'foreignNotional': 44100.0}, {'timestamp': datetime.datetime(2021, 9, 24, 14, 30, tzinfo=tzutc()), 'symbol': 'XBTUSD', 'open': 41964.5, 'high': 41998.5, 'low': 41909.0, 'close': 41998.5, 'trades': 23, 'volume': 6500, 'vwap': 41978.7084, 'lastSize': 1900, 'turnover': 15484098, 'homeNotional': 0.15484098, 'foreignNotional': 6500.0}, {'timestamp': datetime.datetime(2021, 9, 24, 14, 25, tzinfo=tzutc()), 'symbol': 'XBTUSD', 'open': 41911.0, 'high': 41964.5, 'low': 41908.5, 'close': 41964.5, 'trades': 33, 'volume': 10600, 'vwap': 41934.1717, 'lastSize': 200, 'turnover': 25277720, 'homeNotional': 0.2527772, 'foreignNotional': 10600.0}, {'timestamp': datetime.datetime(2021, 9, 24, 14, 20, tzinfo=tzutc()), 'symbol': 'XBTUSD', 'open': 41947.0, 'high': 41948.0, 'low': 41886.5, 'close': 41911.0, 'trades': 29, 'volume': 10300, 'vwap': 41937.1614, 'lastSize': 100, 'turnover': 24560617, 'homeNotional': 0.24560616999999998, 'foreignNotional': 10300.0}, {'timestamp': datetime.datetime(2021, 9, 24, 14, 15, tzinfo=tzutc()), 'symbol': 'XBTUSD', 'open': 41946.0, 'high': 41947.0, 'low': 41887.5, 'close': 41947.0, 'trades': 20, 'volume': 2100, 'vwap': 41931.5342, 'lastSize': 100, 'turnover': 5008181, 'homeNotional': 0.050081809999999984, 'foreignNotional': 2100.0}, {'timestamp': datetime.datetime(2021, 9, 24, 14, 10, tzinfo=tzutc()), 'symbol': 'XBTUSD', 'open': 41879.0, 'high': 41947.0, 'low': 41879.0, 'close': 41946.0, 'trades': 21, 'volume': 5000, 'vwap': 41933.2925, 'lastSize': 100, 'turnover': 11923711, 'homeNotional': 0.11923711000000001, 'foreignNotional': 5000.0}, {'timestamp': datetime.datetime(2021, 9, 24, 14, 5, tzinfo=tzutc()), 'symbol': 'XBTUSD', 'open': 41703.5, 'high': 41879.0, 'low': 41662.5, 'close': 41879.0, 'trades': 47, 'volume': 25400, 'vwap': 41769.8731, 'lastSize': 100, 'turnover': 60809419, 'homeNotional': 0.6080941899999998, 'foreignNotional': 25400.0}],
            < bravado.requests_client.RequestsResponseAdapter object at 0x7fb5fb583cd0 >
        )
}
'''
