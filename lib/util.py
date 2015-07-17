#!/usr/bin/env python

import requests
import json

def get_address_by_ltb_user(user):
	url = 'https://letstalkbitcoin.com/api/v1/users?search={}'.format(user)
	resp = requests.get(url)
	
	if int(resp.status_code) != 200:
		return None
	try:
		ret = json.loads(resp.text)
		whichd = [ x for x in ret['users'] if x['username'].lower() == user.lower() ]
		if not whichd:
			return None
		
		ltbaddy = whichd[0]['profile']['ltbcoin-address']['value']
		return ltbaddy
	except Exception as e:
		return None
	
def get_address_by_netki_wallet(wallet, coin, printerrors=True):
	url = 'https://netki.com/api/wallet_lookup/'
	headers = {
		'Host': 'netki.com', 'User-Agent': 'WalletGenie netki integration',
		'Content-type': 'application/json'
	}
	try:
		response = requests.get('{}{}/{}'.format(url, wallet, coin.lower()), headers=headers)
			
		if int(response.status_code) not in [200, 404, 500]:
			return None
		
		output = json.loads( response.text )
	except ValueError: # json error (trying to load html)
		if printerrors:
			print('netki API error')
		return None
	except Exception as e: # requests.exceptions.ConnectionError
		if printerrors:
			print('\nError contacting netki servers...: {} ({})\n'.format(e, type(e)))
		return None
	
	if 'success' in output.keys():
		if not output['success']:
			if printerrors:
				print('netki api error: {}'.format(output['message']))
			return None
		else:
			return output['wallet_address']
	else:
		return None