import requests

token = ''

auth = {'token': token}

try:
    r = requests.get(
        'https://www.algoinvest.online/publicapi/lotus_bitmex_testnet', params=auth)
    print('Status:', r.status_code, r.reason, r)
    json = r.json()
    print(json)
except ValueError as e:
    print('Error', e)
