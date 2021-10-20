import math

def calc_pos_size(symbol, sl_distance):
    btc_price = 49270
    acc_balance = 814941
    ps = 1
    if symbol == 'XBTUSD':
        lot_step = 100
        riskvalue = (acc_balance / 100000000) * btc_price * (ps/100)  # riskvalue in usd
        pos_size = int(round((math.floor(riskvalue / (sl_distance / btc_price)) / lot_step)) * lot_step)
    elif symbol == 'ETHUSD':
        tickvalue = 100
        lot_step = 1
        riskvalue = acc_balance * (ps/100)
        pos_size = int(round((math.floor(riskvalue / (sl_distance * tickvalue)) / lot_step)) * lot_step)
    else:
        print('Symbol not supported')
    print("Riskvalue", riskvalue)
    print("Position Size rounded:", pos_size)
    if pos_size < lot_step:
        return lot_step
    else:
        return pos_size

# risk should be 8150 satoshi 1& of 814941
print('XBTUSD 300', calc_pos_size('XBTUSD', 300))
print('XBTUSD 600', calc_pos_size('XBTUSD', 600))

print('ETHUSD 20', calc_pos_size('ETHUSD', 20))
print('ETHUSD 40', calc_pos_size('ETHUSD', 40))