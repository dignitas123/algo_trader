import json
import math
import bitmex
import time
import uuid
import pickle
import sys

from bravado.exception import HTTPBadGateway, HTTPUnauthorized, HTTPBadRequest, HTTPNotFound, HTTPGatewayTimeout, HTTPServiceUnavailable, HTTPTooManyRequests


class BitmexClient:
    def __init__(self, api_key=None, api_secret=None, testnet=True):
        self.client = bitmex.bitmex(
            api_key=api_key, api_secret=api_secret, test=testnet)
        self._last_wallet_balance = ''
        self._last_currentprice = {}
        self.testnet = testnet

    def __call__(self):
        return self.client

    def get_margin(self, prop):
        try:
            wallet_balance = self.client.User.User_getMargin().result()[
                0][str(prop)]
            self._last_wallet_balance = wallet_balance
            return wallet_balance
        except (HTTPBadRequest, HTTPGatewayTimeout):
            return self._last_wallet_balance

    def get_position(self, symbol, prop):
        position = 0
        i = 0
        while True:
            try:
                position = self.client.Position.Position_get(
                    filter=json.dumps({'symbol': symbol})).result()[0][0][str(prop)]
                break
            except (IndexError, HTTPBadRequest, HTTPBadGateway) as e:
                if 'expired' in str(e):
                    print('Getting open contracts in {} failed. Expired error.'.format(
                        symbol), flush=True)
                else:
                    time.sleep(2)  # try again after 2 seconds
                    print("Can't get position in {}. Trying again...".format(symbol), e)
                    i += 1
                    if i > 1:
                        print("Can't get position in {} for 2nd time.".format(symbol))
                        return False
        return position

    def get_histories(self, symbols=['XBTUSD'], binSize='5m', count=15):
        histories = {}
        for symbol in symbols:
            i = 0
            while True:
                try:
                    histories[symbol] = self.client.Trade.Trade_getBucketed(symbol=symbol,
                                                                            binSize=binSize,
                                                                            count=count,
                                                                            reverse=True,
                                                                            ).result()
                    break
                except HTTPBadRequest as e:
                    if 'expired' in str(e):
                        print('Getting {} history failed. Expired error.'.format(
                            symbol), flush=True)
                    else:
                        time.sleep(2)  # try again after 2 seconds
                        print("Can't get history. Trying again...", e)
                        i += 1
                        if i > 1:
                            print("Can't get history for 2nd time.")
                            break
        return histories

    def get_current_price(self, symbol):
        try:
            price = self.client.Trade.Trade_get(symbol=symbol,
                                                count=2,
                                                reverse=True,
                                                ).result()[0][0]['price']
            self._last_currentprice[symbol] = price
            return price
        except (IndexError, HTTPBadRequest, HTTPGatewayTimeout, HTTPBadGateway, HTTPServiceUnavailable) as e:
            if 'expired' in str(e):
                print('Current price expired. Returning last price.', flush=True)
            elif 'Service Unavailable' in str(e):
                print('Server maintenance. Trying to reconnect in 5 Minutes...')
                while True:
                    time.sleep(360)
                    current_price = self.get_current_price(symbol)
                    if current_price:
                        break
            # else:
            #     # print('API error getting current price', e, flush=True)
            #     pass
            return self.last_current_price(symbol)

    def get_current_price_candle(self, symbol):
        try:
            price = self.client.Trade.Trade_getBucketed(symbol=symbol,
                                                        binSize='1m',
                                                        count=1,
                                                        reverse=True,
                                                        ).result()[0][0]
            return price
        except (IndexError, HTTPBadRequest, HTTPBadGateway, HTTPGatewayTimeout, HTTPServiceUnavailable, HTTPTooManyRequests) as e:
            if 'Service Unavailable' in str(e):
                print(
                    'Server maintenance. Trying to reconnect in 5 Minutes...', flush=True)
                while True:
                    time.sleep(360)
                    current_price = self.get_current_price(symbol)
                    if current_price:
                        break
            return self._last_currentprice[symbol]

    def last_current_price(self, symbol):
        if symbol in self._last_currentprice.keys():
            return self._last_currentprice[symbol]
        else:
            time.sleep(2)
            return self.get_current_price(symbol)

    def unrealised_pnl(self, symbol):
        return self.get_position(symbol, 'unrealisedPnl')

    def open_contracts(self, symbol):
        res = self.get_position(symbol, 'currentQty')
        if res is not False:
            return res
        else:
            return 0

    def current_price_position(self, symbol):
        return self.get_position(symbol, 'lastPrice')

    @property
    def is_connected(self):
        if not self.acc_balance:
            return False
        else:
            return True

    @property
    def acc_balance(self):
        try:
            return self.get_margin('walletBalance')
        except HTTPUnauthorized:
            return False


class BitmexOrder:
    def __init__(self, symbols, client, settings, settings_path, magic='algo-trader'):
        self.client = client
        self.settings = settings
        self._settings_path = settings_path
        self.magic = magic
        self._symbols = symbols

        self.props = {}
        for symbol in symbols:
            self.props[symbol] = {
                'stoploss_id': '', 'stop_id': '', 'entry': .0, 'SL': .0, 'TP': .0, 'open': False, 'wait_stop': False, 'qty': 0, 'initialSL': .0}

        self.show_slippage = False  # only for testing
        if self.show_slippage:
            self.entry_acc_balance = {}
            self.between_profits = {}
            for symbol in symbols:
                self.between_profits[symbol] = .0
                self.entry_acc_balance[symbol] = .0

    def check_open_bot_order(self, symbol, entry, sl):
        settings = pickle.load(open(self._settings_path, 'rb'))
        self.props[symbol]['stoploss_id'] = settings.symbols[symbol]['last_order_stoploss_id']
        self.props[symbol]['stop_id'] = settings.symbols[symbol]['last_order_stop_id']
        self.props[symbol]['SL'] = settings.symbols[symbol]['last_order_SL']
        self.props[symbol]['qty'] = settings.symbols[symbol]['last_order_qty']
        if self.props[symbol]['stoploss_id']:
            try:
                res = self.client.client.Order.Order_getOrders(
                    filter=json.dumps({"symbol": symbol, "open": True})).result()
                if res[0] and self.props[symbol]['stoploss_id'] in [order['clOrdID'] for order in res[0]]:
                    print("Bot order in {} open, stoploss might be modified".format(
                        symbol), flush=True)
                    self.modifiy_stop(symbol, sl)
                    self.props[symbol]['entry'] = entry
                    self.props[symbol]['open'] = True
                    time.sleep(2)
            except HTTPBadRequest as e:
                print("Error getting orders.", e)
        if self.props[symbol]['stop_id']:
            try:
                res = self.client.client.Order.Order_getOrders(
                    filter=json.dumps({"symbol": symbol, "open": True})).result()
                if res[0] and self.props[symbol]['stop_id'] in [order['clOrdID'] for order in res[0]]:
                    print("Bot order in {} open, stop will be deleted.".format(
                        symbol), flush=True)
                    self.stoporder_cancel(symbol)
                    time.sleep(2)
            except HTTPBadRequest as e:
                print("Error getting orders.", e)

    def save_open_id(self, symbol, id, stop_type='normal'):
        settings = pickle.load(open(self._settings_path, 'rb'))
        if stop_type == 'normal':
            self.props[symbol]['stop_id'] = id
            settings.symbols[symbol]['last_order_stop_id'] = id
            settings.symbols[symbol]['last_order_qty'] = self.props[symbol]['qty']
            pickle.dump(settings, file=open(self._settings_path, 'wb'))
        elif stop_type == 'stoploss':  # also save the stoploss
            self.props[symbol]['stoploss_id'] = id
            settings.symbols[symbol]['last_order_stoploss_id'] = id
            settings.symbols[symbol]['last_order_SL'] = self.props[symbol]['SL']
            pickle.dump(settings, file=open(self._settings_path, 'wb'))
        else:
            print("No Stop Type given.")

    def set_position_open(self, symbol, dir):
        self.props[symbol]['wait_stop'] = False
        self.props[symbol]['open'] = True
        print("{} Position has been opened in {}, amending Stoploss to".format(dir, symbol),
              self.props[symbol]['SL'], flush=True)
        self.stoploss_order(symbol)
        self.calculate_between_profits(symbol)

    def calculate_between_profits(self, symbol):
        between_profs = .0
        for sym in self._symbols:
            if symbol != sym:
                between_profs += self.between_profits[sym]
                self.between_profits[sym] = .0
        return between_profs

    def set_position_closed(self, symbol, dir, currentPrice=False):
        self.props[symbol]['open'] = False
        pnl_points = self.price_decimals(
            symbol, self.props[symbol]['SL']-self.props[symbol]['entry'])
        qty = self.props[symbol]['qty']
        if dir == "Short":
            pnl_points = -pnl_points
            qty = -qty
        if currentPrice:
            exitPrice = self.client.get_current_price(symbol)
        else:
            exitPrice = self.props[symbol]['SL']
        print("{} Position {} closed. {} Contracts from {} to {}. PnL in Points: {}".format(symbol,
                                                                                            dir, qty,
                                                                                            self.props[symbol]['entry'],
                                                                                            exitPrice,
                                                                                            pnl_points), flush=True)
        if self.show_slippage and self.props[symbol]['initialSL']:
            acc_pos_size = float(
                self.settings.symbols[symbol]['position_size'])/100

            current_acc_balance = float(self.client.acc_balance)

            between_profs = self.calculate_between_profits(symbol)

            # exit account balance - current account balance
            acc_balance_diff = current_acc_balance - \
                between_profs - self.entry_acc_balance[symbol]
            print("current_acc_balance", current_acc_balance, "between_profs", between_profs,
                  "self.entry_acc_balance[symbol]", self.entry_acc_balance[symbol])

            # in acc balance difference
            self.between_profits[symbol] += acc_balance_diff

            initial_risk_points = abs(
                self.props[symbol]['initialSL'] - self.props[symbol]['entry'])
            pnl_rr = pnl_points / initial_risk_points

            real_gain = (acc_balance_diff / self.entry_acc_balance[symbol])
            expected_gain = pnl_rr * acc_pos_size

            # slippage is real acc balance change relative - executed pnl percent
            print("expected_gain", expected_gain,
                  "real_gain", real_gain)
            print("Slippage: {}%".format(
                round((real_gain - expected_gain) / abs(expected_gain) * 100, 2)), flush=True)
        self.props[symbol]['qty'] = 0

    def has_position_opened(self, symbol, cp, candlePrice):
        if self.client.open_contracts(symbol) != 0:
            if self.props[symbol]['qty'] > 0:
                _cp = candlePrice['high'] if candlePrice else cp
                if _cp >= self.props[symbol]['entry']:
                    self.set_position_open(symbol, 'Long')
            elif self.props[symbol]['qty'] < 0:
                _cp = candlePrice['low'] if candlePrice else cp
                if _cp <= self.props[symbol]['entry']:
                    self.set_position_open(symbol, 'Short')

    def has_position_closed(self, symbol, cp, candlePrice):
        # wait for if position really closed and prevent bad requests
        time.sleep(1)
        if self.client.open_contracts(symbol) == 0:
            if self.props[symbol]['qty'] > 0:
                _cp = candlePrice['low'] if candlePrice else cp
                if _cp <= self.props[symbol]['SL']:
                    self.set_position_closed(symbol, 'Long')
            elif self.props[symbol]['qty'] < 0:
                _cp = candlePrice['low'] if candlePrice else cp
                if _cp >= self.props[symbol]['SL']:
                    self.set_position_closed(symbol, 'Short')

    def manage_entries(self, symbols, me_count=0, candlePrice=''):
        for symbol in symbols:
            if not candlePrice:
                cp = self.client.get_current_price(symbol)
            else:
                cp = ''
            time.sleep(0.5)
            if self.props[symbol]['wait_stop']:
                self.has_position_opened(symbol, cp, candlePrice)
            elif self.props[symbol]['open']:
                self.has_position_closed(symbol, cp, candlePrice)

        # every 30 seconds additional candle check to not miss entry/exit
        if me_count and me_count % 3 == 0:
            if self.props[symbol]['qty'] > 0:
                candlePrice = self.client.get_current_price_candle(symbol)
                # + 1 to prevent endless loop
                self.manage_entries(self._symbols, candlePrice=candlePrice)
            elif self.props[symbol]['qty'] < 0:
                candlePrice = self.client.get_current_price_candle(symbol)
                self.manage_entries(self._symbols, candlePrice=candlePrice)

    def generate_id(self, symbol, _type='stop'):
        return "{}_{}_{}_{}".format(self.magic, symbol, str(uuid.uuid4().fields[-1])[:5], _type)

    def price_decimals(self, symbol, price):
        if symbol == 'XBTUSD':
            return round(price * 2) / 2
        elif symbol == 'ETHUSD':
            return round(price * 20) / 20
        else:
            print('{} is not a valid symbol for price decimal rounding.'.format(symbol))
            sys.exit()

    def calc_pos_size(self, symbol, sl_distance):
        acc_balance = float(self.client.acc_balance)
        if self.show_slippage:
            self.entry_acc_balance[symbol] = acc_balance
        ps = float(self.settings.symbols[symbol]['position_size'])
        if symbol == 'XBTUSD':
            btc_usd = self.client.last_current_price(symbol)
            lot_step = 100
            riskvalue = (acc_balance / 100000000) * \
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
            print("Error placing stoploss order.", e, flush=True)

    def order_cancel(self, symbol, orderId):
        try:
            order_res = self.client.client.Order.Order_cancel(
                clOrdID=orderId
            ).result()
            self.props[symbol]['wait_stop'] = False
            self.props[symbol]['qty'] = 0
            return order_res
        except (HTTPBadRequest, HTTPNotFound) as e:
            print("Error canceling order.", e, flush=True)

    def stoploss_cancel(self, symbol):
        self.order_cancel(symbol, self.props[symbol]['stoploss_id'])

    def stoporder_cancel(self, symbol):
        self.order_cancel(symbol, self.props[symbol]['stop_id'])

    def bracket_stop_order(self, symbol, orderQty, entry, sl, tp=0):
        try:
            if self.props[symbol]['qty'] != 0:
                self.close(symbol)
                time.sleep(1)
            self.props[symbol]['stop_id'] = self.generate_id(symbol)
            order_res = self.client.client.Order.Order_new(
                symbol=symbol, ordType='Stop', clOrdID=self.props[symbol]['stop_id'], orderQty=orderQty,
                stopPx=self.price_decimals(symbol, entry), execInst='LastPrice'
            ).result()
            self.props[symbol]['qty'] = orderQty
            self.save_open_id(symbol, self.props[symbol]['stop_id'])
            self.props[symbol]['wait_stop'] = True
            self.props[symbol]['SL'] = sl
            self.props[symbol]['initialSL'] = sl
            self.props[symbol]['TP'] = tp
            self.props[symbol]['entry'] = entry
            return order_res
        except HTTPBadRequest as e:
            print("Error placing bracket stop order in {}.".format(
                symbol), e, flush=True)

    def bracket_market_order(self, symbol, orderQty, sl, cp, tp=0):
        try:
            entry = self.market_order(symbol, orderQty)
            self.props[symbol]['SL'] = sl
            self.props[symbol]['initialSL'] = sl
            self.props[symbol]['TP'] = tp
            time.sleep(5)
            stoploss = self.stoploss_order(symbol)
            self.props[symbol]['qty'] = orderQty
            self.props[symbol]['entry'] = cp
            return entry, stoploss
        except HTTPBadRequest as e:
            print("Error placing bracket market order in {}.".format(
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
            print("Error placing market order.", e, flush=True)

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
                time.sleep(1)  # wait before making new API call
                if self.props[symbol]['qty'] > 0:
                    self.set_position_closed(
                        symbol, 'Long', currentPrice=True)
                elif self.props[symbol]['qty'] < 0:
                    self.set_position_closed(
                        symbol, 'Short', currentPrice=True)
                self.stoploss_cancel(symbol)
                return close
            except HTTPBadRequest as e:
                print("Error closing order in {}.".format(symbol), e, flush=True)
        else:
            return False
