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

def make_human_readable(num, time=False):
	if time: # http://stackoverflow.com/a/26781642
		# this is only currenlty used for block timestamps and so it should be limited to
		# hours at most. However, it's built out for much more
		intervals = [
			1, 60, 60*60, 60*60*24, 60*60*24*7, 60*60*24*7*4, 60*60*24*7*4*12,
			60*60*24*7*4*12*100, 60*60*24*7*4*12*100*10,
		]
		names = [
			('second', 'seconds'), ('minute', 'minutes'), ('hour', 'hours'),
			('day', 'days'), ('week', 'weeks'), ('month', 'months'),
			('year', 'years'), ('century', 'centuries'), ('millennium', 'millennia')
		]
		res = []
		unit = list(map(lambda i: i[1], names)).index('seconds')
		for i in range(len(names) - 1, -1, -1):
			a = num // intervals[i]
			if a > 0:
				res.append( (a, names[i][int(1 % a)]) )
				num -= a * intervals[i]
		
		cont = 0
		for u in res:
			if u[0] > 0:
				cont += 1
		buf = ''
		i = 0
		for u in res:
			if u[0] > 0:
				buf += '{:.0f} {}'.format(u[0], u[1])
				cont -= 1
			if i < len(res) - 1:
				if cont > 1:
					buf += ', '
				else:
					buf += ' and '
			i += 1
		return buf
	else:
		for unit in ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi']:
			if abs(num) < 1024.0:
				return '{:.1f} {}B'.format(num, unit)
			num /= 1024.0
		return '{:.1f} YiB'.format(num)