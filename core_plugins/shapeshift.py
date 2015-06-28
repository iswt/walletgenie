
import sys
import os

import json
import datetime

try:
    import requests
except ImportError:
    print('missing requests module, install it with: `pip install requests`')

from walletgenie_plugins.walletgenie_plugins import BasePlugin

class Shapeshift(BasePlugin):
	'''
	https://shapeshift.io/api.html
	'''
	
	plugins = []
	loaded_plugins = None
	active_plugin = None
	
	coinA = None
	coinB = None
	active_pair = None
	
	history = {} # history[deposit_address] = {coina, coinb, withdrawal, deposit, outgoing_tx}
	
	def __init__(self):
		self.baseurl = 'https://shapeshift.io'
		self.user_agent = 'WalletGenie ShapeShift Plugin/0.1'
		self.headers = {
			'Host': 'shapeshift.io',
			'User-Agent': self.user_agent,
			'Content-type': 'application/json'
		}
		
		self.APIKEY = 'aafa42d87bbdb0b0c10eec2764c87084450e1732a54c85983cbe519232989665a49a3177ae6b7d6e900ba72cf76264d04b48be2422b0fc80328cadc0045995a0'
		
		self.topmenu = [
			('s', {'description': '(S)hapeShift', 'callback': self.main_menu}), 
		]
		
	def on_plugin_update(self, plugins, loaded_plugins, active_plugin):
		self.plugins = plugins
		self.loaded_plugins = loaded_plugins
		self.active_plugin = active_plugin
		
		if '_' in self.active_plugin:
			apn = self.active_plugin[ self.active_plugin.rfind('_') + 1 : ]
		else:
			apn = self.active_plugin
		self.topmenu[0][1]['description'] = '(S)hapeShift {}'.format(apn)
	
	def _call(self, httpmethod, method, *args, **kwargs):
		requrl = '/{}'.format(method)
		for arg in args:
			requrl += '/{}'.format(arg)
		try:
			if httpmethod.lower() == 'post':
				postdata = json.dumps(kwargs)
				response = requests.post('{}{}'.format(self.baseurl, requrl), headers=self.headers, data=postdata)
			else:
				response = requests.get('{}{}'.format(self.baseurl, requrl), headers=self.headers)
			
			if int(response.status_code) != 200:
				return None
			output = json.loads( response.text )
		except Exception as e:
			print('\nError contacting ShapeShift servers...: {} ({})\n'.format(e, type(e)))
			return None
		
		return output
	
	def main_menu(self):
		try:
			try:
				self.coinA_pre_func = self.loaded_plugins[self.active_plugin]['plugin_class'].run_before_shapeshift
				if not self.coinA_pre_func():
					self.output('Error initializing {} for ShapeShift'.format(self.active_plugin))
					return None
			except AttributeError:
				pass
			
			self.coinA_withdrawal_address_func = None
			try:
				self.coinA_withdrawal_address_func = self.loaded_plugins[self.active_plugin]['plugin_class'].shapeshift_withdrawal
			except AttributeError:
				pass
			
			self.coinA = self.loaded_plugins[self.active_plugin]['plugin_class'].coin_name.lower()
			self.coinA_send_func = self.loaded_plugins[self.active_plugin]['plugin_class'].send
			self.coinA_amount_func = self.loaded_plugins[self.active_plugin]['plugin_class'].amount
			self.coinA_newaddy_func = self.loaded_plugins[self.active_plugin]['plugin_class'].newaddress
		except AttributeError:
			self.output('Error: {} does not seem to be compatible with the ShapeShift plugin'.format(self.active_plugin))
			return None
			
		menu = [
			{'description': 'ShapeShift', 'callback': self.shapeshift},
			{'description': 'ShapeShift (fixed amount)', 'callback': self.shapeshift_fixed},
			{'description': 'Check deposit status', 'callback': self._prompt_get_deposit_status},
			{'description': 'Request email receipt', 'callback': self._prompt_send_email_receipt},
			{'description': 'Stop ShapeShifting', 'callback': self.cleanup}
		]
		running = True
		while running:
			try:
				disp = [d['description'] for d in menu]
				choice = self.prompt(disp, title='ShapeShift Menu\n', choicemsg='What is your choice? ')
				print('')# add a blank line to separate out the function call text
				try:
					menu[choice]['callback']()
				except KeyboardInterrupt:
					print('\naborted...')
				if choice == len(menu) - 1: # quit
					running = False
			except KeyboardInterrupt:
				running = False
	
	def shapeshift(self):
		print('\nFetching information from ShapeShift...')
		coins = self.get_supported_coins()
		if not coins:
			print('Error contacting the ShapeShift API server')
			return None
		
		allrates = self.get_market_rates(self.coinA)
		if not allrates:
			print('Error contacting the ShapeShift API server')
			return None
		
		disp = sorted(
			[(coin, coind['name']) for coin, coind in coins.iteritems() if coin.upper() != self.coinA.upper()],
			key=lambda x: x[0].lower()
		)
		print('\nWhat asset would you like to shift your {} into?\n'.format(self.coinA.upper()))
		
		for i, (coin, coinname) in enumerate(disp):
			if coin.upper() in allrates.keys():
				print('{0: >2} -> {1} ({2}) -> {3} / 1 {4}'.format(i + 1, coinname, coin, allrates[coin.upper()]['rate'], self.coinA.upper()))
			else:
				print('{0: >2} -> {1} ({2}) -> unavailable'.format(i + 1, coinname, coin))
		
		choice = None
		while choice is None:
			try:
				choice = int( raw_input('\nWhich asset? ') )
				if choice not in range(1, len(disp) + 1):
					print('invalid choice')
					choice = None
				choice -= 1
				if disp[choice][0].lower() == self.coinA:
					print('You can\'t shift into the same coin! (I think, anyway...?)')
					choice = None
			except Exception:
				print('invalid choice')
				choice = None
		
		self.coinB = disp[choice][0].lower()
		coinpair = '{}_{}'.format(self.coinA, self.coinB)
		
		rate = self.get_rate('{}_{}'.format(self.coinA.lower(), self.coinB.lower()))
		if not rate:
			return None
		
		print('\nThe current rate is: 1 {0} = {1} {2}\nThe miner fee will be {3} {2}'.format(
			self.coinA.upper(), self.formatted(rate), self.coinB.upper(), allrates[self.coinB.upper()]['minerFee']
		))
		
		if self.coinA_withdrawal_address_func:
			withdrawal_addy = self.coinA_withdrawal_address_func(self.coinB, address_validator=self.is_address_valid)
		else:
			withdrawal_addy = raw_input('What address would you like to receive your {} to? '.format(self.coinB.upper()))
			vret = self.is_address_valid(withdrawal_addy, self.coinB)
			while not vret['isvalid']:
				print 'Address is not valid for {}'.format(self.coinB)
				withdrawal_addy = raw_input('\nWhat address would you like to receive your {} to? '.format(self.coinB.upper()))
				vret = self.is_address_valid(withdrawal_addy, self.coinB)
			
		ret_addy = raw_input('Return address in case of problems (enter \'n\' generate a new one or leave blank for none [not recommended])?\n')
		if ret_addy == '':
			ret_addy = None
		elif ret_addy.lower() == 'n':
			ret_addy = self.coinA_newaddy_func()
			print('(using {} as a return address)'.format(ret_addy))
		
		depinfo = self.get_deposit_info(coinpair, withdrawal_addy, ret_addy)
		
		if not depinfo:
			print('Error contacting the ShapeShift API Server')
			return None
		if 'error' in depinfo.keys():
			print('Error contacting the ShapeShift API server: {}'.format(depinfo['error']))
			return None
		
		deposit_address = depinfo['deposit']
		print('Received deposit address: {}'.format(deposit_address))
		
		coinpair_limit = self.get_deposit_limit(coinpair)
		limitmax, limitmin = coinpair_limit['limit'], coinpair_limit['min']
		print('\nYou can shift up to: {} {}\nYou must shift at least: {} {}\n'.format(limitmax, self.coinA.upper(), limitmin, self.coinA.upper()))
		
		print('Checking balance...')
		amnt = self.coinA_amount_func()
		if float(amnt) < float(limitmin):
			print('You do not have a sufficient balance to shift {} into {}'.format(self.coinA.upper(), self.coinB.upper()))
			return None
		print('You have: {} {} ({} {})\n'.format(
			amnt, self.coinA.upper(),
			float(amnt) * float(rate), self.coinB.upper()
		))
		
		howmuch = None
		while howmuch is None:
			howmuch = raw_input('\nHow many would you like to shift -- you can shift up to {} (\'m\' to use max)? '.format(amnt)).strip()
			if howmuch == '':
				howmuch = amnt
			try:
				assert float(howmuch) <= float(amnt)
				assert float(howmuch) <= float(limitmax)
				assert float(howmuch) >= float(limitmin)
			except AssertionError as e:
				print('invalid amount: {}'.format(e))
				howmuch = None
		
		rate = self.get_rate('{}_{}'.format(self.coinA.lower(), self.coinB.lower()))
		approx_shift = float(howmuch) * rate
		approx_shift -= float(allrates[self.coinB.upper()]['minerFee'])
		print('\nThe current rate is: 1 {0} = {1} {2} with a miner fee of {3} {2}\nYou will receive approximately: {4} {2}\n'.format(
			self.coinA.upper(), self.formatted(rate), self.coinB.upper(), allrates[self.coinB.upper()]['minerFee'], approx_shift
		))
		
		msg = '\nReally send {} {} to be ShapeShifted into ~ {} {} at {}'.format(
			howmuch, self.coinA.upper(), approx_shift, self.coinB.upper(), withdrawal_addy
		)
		yorn = self.confirm_prompt(msg)
		if not yorn:
			print('\naborted')
			return None
		else:
			tx = self.coinA_send_func(deposit_address, howmuch)
			self.output('Sent {} {}: {}'.format(howmuch, self.coinA.upper(), tx))
			self.history[deposit_address] = {
				'deposit': deposit_address, 'withdrawal': withdrawal_addy, 'howmuch': howmuch, 
				'coina': self.coinA, 'coinb': self.coinB, 'coin_pair': coinpair,
				'coinpair_limit_min': limitmin, 'coinpair_limit_max': limitmax, 
				'approx_shift': approx_shift, 'tx': tx
			}
		
	def shapeshift_fixed(self):
		print('\nFetching information from ShapeShift...')
		coins = self.get_supported_coins()
		if not coins:
			print('Error contacting the ShapeShift API server')
			return None
		
		allrates = self.get_market_rates(self.coinA)
		if not allrates:
			print('Error contacting the ShapeShift API server')
			return None
			
		disp = sorted(
			[(coin, coind['name']) for coin, coind in coins.iteritems() if coin.upper() != self.coinA.upper()],
			key=lambda x: x[0].lower()
		)
		print('\nWhat asset would you like to receive?\n'.format())
		
		for i, (coin, coinname) in enumerate(disp):
			if coin.upper() in allrates.keys():
				print('{0: >2} -> {1} ({2})'.format(i + 1, coinname, coin))
			else:
				print('{0: >2} -> {1} ({2}) -> unavailable'.format(i + 1, coinname, coin))
		
		choice = None
		while choice is None:
			try:
				choice = int( raw_input('\nWhich asset? ') )
				if choice not in range(1, len(disp) + 1):
					print('invalid choice')
					choice = None
				else:
					choice -= 1
					if disp[choice][0].lower() == self.coinA:
						print('You can\'t shift into the same coin! (I think, anyway...?)')
						choice = None
			except Exception:
				print('invalid choice')
				choice = None
		
		self.coinB = disp[choice][0].lower()
		coinpair = '{}_{}'.format(self.coinA, self.coinB)
		
		amnt = raw_input('How many {} would you like? '.format(self.coinB.upper())).strip()
		
		if self.coinA_withdrawal_address_func:
			withdrawal_addy = self.coinA_withdrawal_address_func(self.coinB, address_validator=self.is_address_valid)
		else:
			withdrawal_addy = raw_input('What address would you like to receive your {} to? '.format(self.coinB.upper()))
			vret = self.is_address_valid(withdrawal_addy, self.coinB)
			while not vret['isvalid']:
				print 'Address is not valid for {}'.format(self.coinB)
				withdrawal_addy = raw_input('\nWhat address would you like to receive your {} to? '.format(self.coinB.upper()))
				vret = self.is_address_valid(withdrawal_addy, self.coinB)
		
		ret_addy = raw_input('Return address in case of problems (enter \'n\' generate a new one or leave blank for none [not recommended])?\n')
		if ret_addy == '':
			ret_addy = None
		elif ret_addy.lower() == 'n':
			ret_addy = self.coinA_newaddy_func()
			print('(using {} as a return address)'.format(ret_addy))
		
		infod_ret = self.get_fixed_deposit_info(coinpair, amnt, withdrawal_addy, return_address=ret_addy)
		
		if not infod_ret:
			print('Error contacting the ShapeShift API server...')
			return None
		if 'success' not in infod_ret.keys():
			if 'error' in infod_ret.keys():
				print('\nShapeShift Error: {}'.format(infod_ret['error']))
			return None
			
		infod = infod_ret['success']
		
		print('\nReceived deposit address: {}\nWithdrawal amount: {}\nQuoted rate: {}\nExpiration time: {}\n'.format(
			infod['deposit'], infod['withdrawalAmount'], infod['quotedRate'], 
			datetime.datetime.fromtimestamp(int(infod['expiration']) / 1000)
		))
		print('\nExact amount to be sent: {} {}'.format(infod['depositAmount'], self.coinA.upper()))
		
		deposit_address = infod['deposit']
		howmuch = infod['depositAmount']
		
		msg = '\nReally send {} {} to be ShapeShifted into ~ {} {} at {}'.format(
			howmuch, self.coinA.upper(), infod['withdrawalAmount'], self.coinB.upper(), withdrawal_addy
		)
		yorn = self.confirm_prompt(msg)
		if not yorn:
			print('\naborted')
			return None
		else:
			tx = self.coinA_send_func(deposit_address, howmuch)
			self.output('Sent {} {}: {}'.format(howmuch, self.coinA.upper(), tx))
			self.history[deposit_address] = {
				'deposit': deposit_address, 'withdrawal': withdrawal_addy, 'howmuch': howmuch, 
				'coina': self.coinA, 'coinb': self.coinB, 'coin_pair': coinpair,
				'approx_shift': infod['withdrawalAmount'], 'tx': tx
			}
			return tx
		
	def get_deposit_info(self, coinpair, withdrawal_address, return_address=None):
		return self._call('post', 'shift', 
			withdrawal=withdrawal_address, pair=coinpair, returnAddress=return_address, apiKey=self.APIKEY
		)
	
	def get_fixed_deposit_info(self, coinpair, amount, withdrawal_address, return_address=None):
		return self._call('post', 'sendamount', 
			withdrawal=withdrawal_address, pair=coinpair.lower(), amount=amount, returnAddress=return_address,
			apiKey=self.APIKEY
		)
	
	def get_rate(self, coinpair):
		rated = self._call('get', 'rate', coinpair)
		return float(rated['rate'])
	
	def get_market_rates(self, coin):
		allinfo = self._call('get', 'marketinfo')
		outd = {}
		for d in allinfo:
			p1, p2 = d['pair'].split('_')
			if coin.upper() == p1:
				outd[p2] = d
		return outd
	
	def get_deposit_limit(self, coinpair):
		return self._call('get', 'limit', coinpair)
	
	def get_deposit_status(self, address):
		return self._call('get', 'txStat', address)
	
	def _prompt_get_deposit_status(self):
		if len(self.history) > 0:
			tup_disp = [(infod['deposit'], '{} ({})'.format(infod['deposit'], infod['tx'])) for depaddy, infod in self.history.iteritems()]
			tup_disp += [('None', 'Enter address manually')]
			
			disp = [x[1] for x in tup_disp]
			choice = self.prompt(disp, title='Get the status for which deposit address? (Most recent listed first)', choicemsg='(number)-> ')
			if choice == len(tup_disp) - 1: 
				address = raw_input('\nGet the status for which deposit address? ').strip()
			else:
				address = self.history[ tup_disp[choice][0] ]['deposit']
		else:
			address = raw_input('Get the status for which deposit address? ').strip()
		
		status = self.get_deposit_status(address)
		if not status:
			print('Error contacting the API server about this address (wait a minute if you\'ve just created the transaction)')
			return None
			
		self.output('Status: {}{}{}'.format(
			status['status'], 
			'\nIncoming: {} {}'.format(status['incomingCoin'], status['incomingType']) if 'incomingCoin' in status.keys() else '', 
			'\n\nOutgoing: {} {}\nOutgoing TX: {}'.format(status['outgoingCoin'], status['outgoingType'], status['transaction']) if 'transaction' in status.keys() else ''
		))
		# check to see if we can add the outgoing tx hash to existing history
		if status['address'] in self.history.keys():
			if 'transaction' in status.keys(): # and status['status'] == 'complete':
				if 'outgoing_tx' not in self.history[ status['address'] ].keys():
					self.history[ status['address'] ]['outgoing_tx'] = status['transaction']
	
	def send_email_receipt(self, tx, email_addy):
		return self._call('post', 'mail',
			txid=tx, email=email_addy
		)
	
	def _prompt_send_email_receipt(self):
		histtx = []
		if len(self.history) > 0:
			for depaddy, infod in self.history.iteritems():
				if 'outgoing_tx' in infod.keys():
					histtx.append(infod['outgoing_tx'])
			if len(histtx) > 0:
				disp = histtx + ['Enter transaction ID manually']
				choice = self.prompt(disp, title='Transaction ID to use?', choicemsg='(number)-> ')
				if choice == len(disp) - 1:
					txid = raw_input('Transaction ID of your withdrawal (NOT your deposit): ').strip()
				else:
					txid = disp[choice]
			else:
				txid = raw_input('Transaction ID of your withdrawal (NOT your deposit): ').strip()
		else:
			txid = raw_input('Transaction ID of your withdrawal (NOT your deposit): ').strip()
		
		emailaddy = raw_input('Email address to send receipt to? ')
		
		receipt = self.send_email_receipt(txid, emailaddy)
		if not receipt:
			print('Error contacting the API server (wait a minute if you\'ve just created the transaction)')
			return None
			
		if 'error' in receipt.keys():
			self.output('ShapeShift API Error: {}'.format(receipt['error']))
		else:
			self.output('Status: {}\nMessage: {}'.format(receipt['email']['status'], receipt['email']['message']))
	
	def get_supported_coins(self):
		return self._call('get', 'getcoins')
	
	def is_address_valid(self, address, coinsymbol):
		return self._call('get', 'validateAddress', address, coinsymbol.upper())