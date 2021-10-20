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