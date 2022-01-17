import math


def calc_pos_size(symbol, sl_distance):
    acc_balance = float(100000000)
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
