from algo_trader.clients import BitmexClient

client = BitmexClient(api_key='',
                      api_secret='', testnet=False)

# print(client.get_current_price('XBTUSD'))

bucket = client.client.Trade.Trade_getBucketed(symbol='XBTUSD',
                                               binSize='1m',
                                               count=1,
                                               reverse=True,
                                               ).result()

print(bucket[0][0]['symbol'])

# testnet id: Wy-golkVr1wwO2-jy8lDOzzU
# testnet secret: fRRvX8rMh6_QkcZRANs1maqzHYnFBunit4uMr87ub2j_eREz
