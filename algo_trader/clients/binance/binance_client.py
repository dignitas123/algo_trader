import time
from binance.client import Client as binanceClient, BinanceAPIException, BinanceRequestException, NotImplementedException

from bravado.exception import HTTPBadGateway, HTTPBadRequest, HTTPGatewayTimeout, HTTPServiceUnavailable


class BinanceClient:
    def __init__(self, api_key=None, api_secret=None, testnet=True):
        self.client = binanceClient(
            api_key, api_secret, {'timeout': 20}, testnet=testnet)
        self._last_wallet_balance = ''
        self._last_currentprice = {}
        self.testnet = testnet

    def __call__(self):
        return self.client

    def acc_balance(self, symbol):
        if 'USDT' in symbol:
            try:
                return self.client.futures_account_balance()[1]['balance']
            except (BinanceAPIException, BinanceRequestException, NotImplementedException) as e:
                print(e.status_code)
                print(e.message)
        else:
            try:
                s_bal = symbol.replace('USD', '')  # balance to search for
                balances = self.client.futures_coin_account_balance()
                return next(sym for sym in balances if sym['asset'] == s_bal)['balance']
            except (BinanceAPIException, BinanceRequestException, NotImplementedException) as e:
                print(e.status_code)
                print(e.message)

    def get_position(self, symbol, prop):
        '''

        example return of `s_info`:
            {'symbol': 'BTCUSDT', 'positionAmt': '0.001',
            'entryPrice': '41694.23', 'markPrice': '41822.27000000', 'unRealizedProfit': '0.12804000',
            'liquidationPrice': '0', 'leverage': '20', 'maxNotionalValue': '10000000', 'marginType': 'cross',
            'isolatedMargin': '0.00000000', 'isAutoAddMargin': 'false', 'positionSide': 'BOTH',
            'notional': '41.82227000', 'isolatedWallet': '0', 'updateTime': 1632491393073}

        '''
        try:
            s_info = self.client.futures_position_information(symbol=symbol)
            return s_info[prop]
        except (BinanceAPIException, BinanceRequestException, NotImplementedException) as e:
            print(e.status_code)
            print(e.message)

    def get_histories(self, symbols=['BTCUSDT'], count=15, interval=30):
        histories = {}
        for symbol in symbols:
            i = 0
            while True:
                try:
                    histories[symbol] = self.client.get_klines(
                        symbol=symbol, interval=str(interval)+'m', limit=count)
                    break
                except (BinanceAPIException, BinanceRequestException, NotImplementedException) as e:
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
            return self.last_current_price(symbol)

    def last_current_price(self, symbol):
        if symbol in self._last_currentprice.keys():
            return self._last_currentprice[symbol]
        else:
            time.sleep(2)
            return self.get_current_price(symbol)

    def unrealised_pnl(self, symbol):
        return self.get_position(symbol, 'unRealizedProfit')

    def open_contracts(self, symbol):
        res = self.get_position(symbol, 'positionAmt')
        if res != '0.000':
            return res
        else:
            return 0

    def current_price_position(self, symbol):
        return self.get_position(symbol, 'markPrice')

    @property
    def is_connected(self):
        print(self.acc_balance('BTCUSDT'))
        if isinstance(self.acc_balance('BTCUSDT'), str):
            return True
        else:
            return False
