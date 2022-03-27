import json
import bitmex
import time

from bravado.exception import HTTPBadGateway, HTTPUnauthorized, HTTPBadRequest, HTTPGatewayTimeout, HTTPServiceUnavailable, HTTPTooManyRequests, HTTPServerError, HTTPServerError, BravadoConnectionError, BravadoTimeoutError


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
            except (IndexError, HTTPBadRequest, HTTPBadGateway, HTTPServerError, BravadoConnectionError, BravadoTimeoutError) as e:
                if 'expired' in str(e):
                    print('Getting open contracts in {} failed. Expired error.'.format(
                        symbol), flush=True)
                else:
                    print(
                        "Can't get position in {}.".format(symbol))
            time.sleep(2)  # try again after 2 seconds
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
        price = 0
        i = 0
        while True:
            try:
                price = self.client.Trade.Trade_get(symbol=symbol,
                                                    count=2,
                                                    reverse=True,
                                                    ).result()[0][0]['price']
                self._last_currentprice[symbol] = price
                break
            except (IndexError, HTTPBadRequest, HTTPGatewayTimeout, HTTPBadGateway, HTTPServiceUnavailable, HTTPServerError, BravadoConnectionError, BravadoTimeoutError) as e:
                if 'expired' in str(e):
                    print('Current price expired. Trying again...', flush=True)
                    time.sleep(15)
                elif 'Service Unavailable' in str(e):
                    print('Server maintenance. Trying to reconnect in 5 Minutes...')
                    while True:
                        time.sleep(360)
                        current_price = self.get_current_price(symbol)
                        if current_price:
                            return current_price
                else:
                    print(
                        "Can't get current price in {}. Trying again in 30 seconds...".format(symbol))
                    time.sleep(30)
            i += 1
            if i > 1:
                return self.last_current_price(symbol)
        return price

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
            time.sleep(30)
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
