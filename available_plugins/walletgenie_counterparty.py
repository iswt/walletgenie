from walletgenie_plugins import BasePlugin, WalletGenieConfig, WalletGenieConfigurationError

import sys
import time
import json
import random
try:
	import requests
	from requests.auth import HTTPBasicAuth
except ImportError:
	print('Unable to import the requests module, install it with: `pip install requests`')
	sys.exit(0)
try:
	import tabulate
except ImportError:
	print('Unable to import the tabulate module, install it with `pip install tabulate`')
	sys.exit(0)

FREEASSET_MIN = 26**12 + 1
FREEASSET_MAX = 256**8

class Counterparty(BasePlugin):
	
	coin_name = 'XCP' # shapeshift plugin -- default value
	ACCEPTED_SHAPESHIFT_ASSETS = ['SJCX', 'GEMZ', 'SWARM', 'XCP']
	
	def __init__(self, *args, **kwargs):
		
		super(Counterparty, self).__init__(*args, **kwargs)
		
		if not self.require_plugin('walletgenie_bitcoin', autoload_if_available=True):
			print('Error loading Counterparty plugin')
			sys.exit(0)
		
		self.btc = self.active_plugins['walletgenie_bitcoin']['plugin_class']
		
		self.config_file = 'wgcounterparty.conf'
		self.required_config_vars = ['rpc-password']
		self.default_config_vars = {'rpcuser': 'rpc', 'rpcssl': 0, 'rpcport': '4000', 'rpcurl': '127.0.0.1'}
		
		bitcoin_menu_height = sorted(self.btc.main_menu.iteritems(), key=lambda x: x[0])[-1][0]
		bitcoin_menu_height += 1
		
		self.main_menu = self.btc.main_menu.copy()
		
		self.main_menu[bitcoin_menu_height] = {
			'description': 'Genie, are you currently able to speak to the Counterparty network?',
			'insert_before': '\n--- Counterparty Functions ---\n',
			'callback': self.print_diagnostics
		}
		self.main_menu[bitcoin_menu_height + 1] = {
			'description': 'Genie, I wish to see all of my Counterparty balances.',
			'callback': self.print_all_balances
		}
		self.main_menu[bitcoin_menu_height + 2] = {
			'description': 'Genie, I wish to send an asset from my active address to another address.',
			'callback': self._prompt_send_asset
		}
		self.main_menu[bitcoin_menu_height + 3] = {
			'description': 'Genie, I wish to choose an active address.',
			'callback': self.choose_address
		}
		self.main_menu[bitcoin_menu_height + 4] = {
			'description': 'Genie, I wish to create a new Counterpary asset to be owned by the active address.',
			'callback': self._prompt_create_issuance
		}
		self.main_menu[bitcoin_menu_height + 5] = {
			'description': 'Genie, I wish to issue additional tokens for an asset owned by the active address.',
			'callback': self._prompt_issue_additional
		}
		self.main_menu[bitcoin_menu_height + 6] = {
			'description': 'Genie, I wish to lock an asset in the active address so that no further issuances can be made.',
			'callback': self._prompt_lock_asset
		}
		self.main_menu[bitcoin_menu_height + 7] = {
			'description': 'Genie, I wish to transfer ownership of an asset from the active address to another address.',
			'callback': self._prompt_transfer_asset
		}
		self.main_menu[bitcoin_menu_height + 8] = {
			'description': 'Genie, I wish to change the description of an asset owned by the active address.',
			'callback': self._prompt_change_asset_description
		}
		self.main_menu[bitcoin_menu_height + 9] = {
			'description': 'Genie, I wish to make a broadcast on the Counterparty network.',
			'callback': self._prompt_send_broadcast
		}
		
		wgc = WalletGenieConfig()
		self.rpcd = wgc.check_and_load(self.config_file, required_values=self.required_config_vars, default_values=self.default_config_vars)
		if self.rpcd is None:
			print('\nIt appears that {} does not yet exist. If this is your first time running the walletgenie_counterparty plugin, you will need a config file detailing your RPC Connection information.\n'.format(self.config_file))
			confvars = [(x, None) for x in self.required_config_vars if x not in self.default_config_vars.keys()]
			confvars += self.default_config_vars.items()
			wgc.set_from_coin_or_text(
				self.config_file, 
				default_conf_loc='/home/xcp/.config/counterparty/server.conf', 
				coin_conf_header='Default',
				config_vars=confvars
			)
			self.rpcd = wgc.check_and_load(self.config_file, required_values=self.required_config_vars, default_values=self.default_config_vars, silent=False)
			if not self.rpcd:
				print('\n\nUnable to load configuration file: {}\nAborting Counterparty plugin\n'.format(self.config_file))
				raise WalletGenieConfigurationError(self.config_file)
			
		# note: even though we change url to https here, encrypted requests will not work (using HTTPBasicAuth)
		self.url = '{}://{}:{}/api/'.format(
			'https' if int(self.rpcd['rpcssl']) else 'http', self.rpcd['rpcurl'], self.rpcd['rpcport']
		)
		self.auth = HTTPBasicAuth(self.rpcd['rpcuser'], self.rpcd['rpc-password'])
	
	def make_request(self, payload, tojson=True, printerrors=True):
		headers = {'content-type': 'application/json'}
		if 'jsonrpc' not in payload.keys():
			payload['jsonrpc'] = '2.0'
		if 'id' not in payload.keys():
			payload['id'] = 0
		
		response = requests.post(self.url, data=json.dumps(payload), headers=headers, auth=self.auth)
		if tojson:
			resp = response.json()
			if printerrors and 'error' in resp.keys():
				print('Error making request: {}'.format(resp['error']))
			return resp
		return response
	
	# decorators
	def bitcoin_address_required(func):
		def validate_and_call(*args, **kwargs):
			if not args[0].btc.selected_address:
				print('I can\'t do that until you choose an active address...\n')
				#args[0].btc.choose_address()
				args[0].choose_address()
			return func(*args, **kwargs)
		return validate_and_call
	# ******************************************************
	
	# shapeshift plugin functions
	@bitcoin_address_required
	def run_before_shapeshift(self):
		payload = {
			'method': 'get_balances',
			'params': {
				'filters': {
					'field': 'address', 'op': '==', 'value': self.btc.selected_address 
				}
			}
		}
		resp = self.make_request(payload)['result']
		assets = [d['asset'] for d in resp if d['asset'] in self.ACCEPTED_SHAPESHIFT_ASSETS]
		if not assets:
			print('You do not have any Counterparty assets that are currently supported by ShapeShift {}'.format(self.ACCEPTED_SHAPESHIFT_ASSETS))
			return False
		choice = self.prompt(assets, title='Which asset do you want to ShapeShift?', choicemsg='Which asset? ')
		self.coin_name = assets[choice]
		return True
	
	@bitcoin_address_required
	def send(self, toaddy, amount):
		divis, locked = self.get_div_locked(self.coin_name)
		if divis:
			return self._send(toaddy, self.coin_name, self.to_satoshis(amount))
		else:
			return self._send(toaddy, self.coin_name, amount)
	
	def amount(self):
		return self.get_balance(self.btc.selected_address, self.coin_name)
	
	def newaddress(self):
		return self.btc.newaddress()
	
	def shapeshift_withdrawal(self, coin, **kwargs):
		return self.btc.shapeshift_withdrawal(coin, **kwargs)
	# ***************************	
	
	def choose_address(self):
		retargs = self.btc.choose_address()
		for k, x in self.main_menu.items():
			if x['callback'] == self.choose_address:
				x['description'] = 'Genie, I wish to choose an active address. (currently {})'.format(self.btc.selected_address)
		return retargs
		
	def get_div_locked(self, asset):
		payload = {
			"method": "get_issuances",
			"params": {
				"filters": {
					'field': 'asset', 'op': '==', 'value': asset
				}
			},
			"jsonrpc": "2.0",
			"id": 0,
		}
		response = self.make_request(payload)
		ld = response['result']
		divisibility, locked = bool(ld[-1]['divisible']), bool(ld[-1]['locked'])
		
		return (divisibility, locked)
	
	def get_divisibility(self, asset):
		return self.get_div_locked(asset)[0]
	
	def get_locked(self, asset):
		return self.get_div_locked(asset)[1]
	
	def get_balance(self, address, asset):
		payload = {
			'method': 'get_balances',
			'params': {
				'filters': [
					{
						'field': 'address', 'op': '==', 'value': address
					},
					{
						'field': 'asset', 'op': '==', 'value': asset
					}
				]
			}
		}
		resp = self.make_request(payload)['result']
		qty = resp[0]['quantity']
		divis, lockd = self.get_div_locked(asset)
		
		if divis:
			return self.from_satoshis(qty)
		else:
			return qty
	
	def get_balances(self, address, btcbal, pretty=True):
		payload = {
			'method': 'get_balances',
			'params': {
				'filters': 
					{
					'field': 'address', 
					'op': '==', 
					'value': address 
				}
			}
		}
		
		assets = [ ['Asset', 'Balance', 'Divisible', 'Locked'], ['BTC', self.formatted(btcbal), 'Yes', 'N/A'] ]
		
		resp = self.make_request(payload)['result']
		
		for d in resp:
			asset = d['asset']
			divis, lockd = self.get_div_locked(asset)
			
			qty = d['quantity']
			
			if pretty:
				disp_qty = self.formatted( self.from_satoshis(qty) ) if divis else self.formatted(qty)
			else:
				disp_qty = self.from_satoshis(qty) if divis else qty
			
			locked = 'Yes' if lockd else 'No'
			divisible = 'Yes' if divis else 'No'
			
			assets.append( [ asset, disp_qty, divisible, locked ] )
		
		return assets
	
	def print_all_balances(self):
		allow_empty = self.confirm_prompt('Do you want to list all addresses - even with a zero bitcoin balance? ')
		if allow_empty:
			address_bal_tup = self.btc.get_wallet_addresses(allow_empty=True)
		else:
			address_bal_tup = self.btc.get_wallet_addresses()
		
		for i, (address, btcbal) in enumerate(address_bal_tup):
			print('\nAddress {} -> {}'.format(i + 1, address))
			balances = self.get_balances(address, btcbal)
			real_balances = [balances[0]]
			for b in balances[1 : ]:
				if b[1] != '0':
					real_balances.append(b)
				else:
					if b[0] == 'BTC':
						real_balances.append(b)
			print( tabulate.tabulate(real_balances, headers='firstrow', tablefmt='grid', stralign='left') )
		print('\n')
	
	@bitcoin_address_required
	def _send(self, toaddy, asset, amount):
		payload = {
			'method': 'create_send',
			'params': {
				'source': self.btc.selected_address,
				'destination': toaddy,
				'pubkey': self.btc.selected_address_info['pubkey'],
				'asset': asset,
				'quantity': amount,
				'encoding': 'multisig'
			}
		}
		utx = self.make_request(payload)['result']
		tx = self.btc.sign_and_send(utx)
		return tx
	
	def send_asset(self, asset, amount, toaddress):
		payload = {
			"method": "create_send",
			"params": {
				"source": self.btc.selected_address,
				"destination": toaddress,
				"pubkey": self.btc.selected_address_info['pubkey'],
				"asset": asset,
				"quantity": amount,
				"encoding": "multisig",
			},
			"jsonrpc": "2.0",
			"id": 0
		}
		
		disp_amount = self.from_satoshis(amount) if self.get_divisibility(asset) else amount
		if not self.confirm_prompt('\nDo you really want me to send {} {} to {}? '.format(disp_amount, asset, toaddress)):
			print('\naborted')
			return None
		
		response = self.make_request(payload)
		
		utx = response['result']
		tx = self.btc.sign_and_send(utx)
		
		self.output('Sent successfully: {}'.format(tx))
		return tx
	
	@bitcoin_address_required
	def _prompt_send_asset(self):
		assets_l = self.get_balances(self.btc.selected_address, 0.0, pretty=False)[2 : ] # note: we really need a get_balances which doesnt take in the bitcoin balance as well...
		assets = [a[0] for a in assets_l]
		if not assets:
			self.output('The current active address does not contain any assets to send!')
			return None
		
		choice = self.prompt(assets, title='\n', choicemsg='\nWhich asset would you like me to send? ')
		asset = assets[choice]
		
		divis = self.get_divisibility(asset)
		
		amount = None
		while amount is None:
			amount = raw_input('How many {0} would you like me to send (You have {1} {0}, enter \'m\' to send the max amount)? '.format(
				asset, assets_l[choice][1]
			))
			if amount == 'm':
				amount = assets_l[choice][1]
			try:
				if divis:
					amount = self.to_satoshis(amount)
				else:
					try:
						amount = int(amount)
					except AssertionError:
						print('{} is indivisible, you must enter a whole number.\n'.format(asset))
						amount = None
			except Exception as e:
				print('Exception: {} ({})'.format(e, type(e)))
				amount = None
		
		toaddress = raw_input('To which address, netki domain or Let\'s Talk Bitcoin! user would you like me to send {}? '.format(asset))
		validaddy = self.btc.access.validateaddress(toaddress)
		if not validaddy['isvalid']:
			netki_addy = None
			if '.' in toaddress:
				print('Checking netki for a wallet by the name of {}...'.format(toaddress))
				netki_addy = self.btc.get_address_by_netki_wallet(toaddress, 'btc', printerrors=False)
				if netki_addy:
					print('The Bitcoin address that belongs to {} is {}. Setting that as the destination address.'.format(toaddress, netki_addy))
					print('\nImportant note: netki does not officially support Counterparty. This *Bitcoin* address is not guaranteed to be in a Counterparty compatible wallet.\n')
					toaddress = netki_addy
				else:
					print('No netki user was found.')
			
			if not netki_addy:
				print('Checking Let\'s Talk Bitcoin! for a user by the name of {}...'.format(toaddress))
				ltb_addy = self.btc.get_address_by_ltb_user(toaddress)
				if not ltb_addy:
					print('Unable to locate any user by the name of {} at Let\'s Talk Bitcoin!'.format(toaddress))
					return None
				else:
					print('The verified LTB address for {} is {}. Setting that as the destination address.'.format(toaddress, ltb_addy))
					toaddress = ltb_addy
		
		return self.send_asset(asset, amount, toaddress)
	
	def create_issuance(self, asset, amount, divis, description):
		payload = {
			"method": "create_issuance",
			"params": {
				'source': self.btc.selected_address,
				'pubkey': self.btc.selected_address_info['pubkey'],
				'asset': asset,
				'quantity': amount,
				'description': description, # optional
				'divisible': divis,
				'encoding': 'multisig'
			},
			"jsonrpc": "2.0",
			"id": 0,
		}
		conf_str = '\nDo you really want me to create an asset with the following parameters?\nName: {}\nDivisibility: {}\nInitial amount: {}\nInitial description: {} '.format(
			asset, 'Divisible' if divis else 'Indivisible', 
			self.from_satoshis(amount) if divis else amount, 
			description
		)
		if not self.confirm_prompt(conf_str):
			print('\naborted')
			return None
		
		response = self.make_request(payload)
		
		utx = response['result']
		tx = self.btc.sign_and_send(utx)
		
		if tx:
			self.output('Successfully created {}: {}'.format(asset, tx))
		else:
			self.output('Sorry, there was an error creating the issuance ({})'.format(tx))
		return tx
	
	@bitcoin_address_required
	def _prompt_create_issuance(self):
		asset, isnumeric = self.get_asset()
		divis = self.confirm_prompt('Do you want the asset to be divisible? ', choicemsg='[Y/n]: ', default_to_yes=True)
		
		amount = None
		while amount is None:
			amount = raw_input('How many would you like me to issue? ')
			try:
				if divis:
					amount = self.to_satoshis(amount)
				else:
					try:
						amount = int(amount)
					except Exception:
						print('{} will be indivisible, you must issue a whole number.\n'.format(asset))
						amount = None
			except Exception, e:
				print('Exception: {}'.format(e))
				amount = None
		
		description = raw_input('What would you like the initial description for {} to be?\n'.format(asset))
		
		return self.create_issuance(asset, amount, divis, description)
		
	def get_asset(self):
		disp = ['Numeric asset (Free)', 'Named asset (0.5 XCP)']
		
		isavailable = False # is asset available
		while not isavailable:
			choice = self.prompt(disp)
			isnumeric = False
			if choice == 0: # free asset
				isnumeric = True
				asset = raw_input('Please provide me with an asset name (must start with \'A\'), or enter nothing to generate a random free asset')
				if asset == '':
					asset = self.generate_free_asset()
					print('Generated: {}'.format(asset))
				if asset[0] != 'A':
					print('\nWarning: Free assets must start with an uppercase \'A\'. Your chosen name does not -- you will incur a 0.5 XCP fee upon successful creation\n')
			else: # paid asset
				asset = raw_input('Please provide me with the asset name you would like me to create: ')
			asset = asset.upper()
			
			_, isavailable = self.is_asset_valid(asset)
			if not isavailable:
				print('Sorry, {} already exists. :(\n'.format(asset))
		
		return asset, isnumeric
	
	def generate_free_asset(self, until_available=False):
		if not until_available:
			return 'A{}'.format( random.randint(FREEASSET_MIN, FREEASSET_MAX) )
		else:
			while True:
				asset = 'A{}'.format( random.randint(FREEASSET_MIN, FREEASSET_MAX) )
				_, available = self.is_asset_valid(asset)
				if available:
					return asset
	
	def is_asset_valid(self, asset):
		'''
		check if asset is valid according to the counterparty specification.
		returns (asset_validity, asset_available)
		does not currently actually check validity and will always return true for that field
		'''
		payload = {
			'method': 'get_asset_names'
		}
		try:
			all_assets = self.make_request(payload)['result']
			if asset in all_assets: # asset is taken
				return True, False
			else: # asset is free
				return True, True
		except Exception as e: # default
			print('is_asset_valid: {} ({})'.format(e, type(e)))
			return True, True
	
	def send_broadcast(self, text, value, fee_fraction):
		payload = {
			"method": "create_broadcast",
			"params": {
				"source": self.btc.selected_address,
				"fee_fraction": fee_fraction,
				"text": text,
				"timestamp": int(time.time()),
				"value": value,
				"pubkey": self.btc.selected_address_info['pubkey'],
				"encoding": "multisig",
			}
		}
		
		if not self.confirm_prompt('Do you really want to make a broadcast onto the CounterParty network with the following:\nAddress: {}\nTime: {}\nText: {}'.format(self.btc.selected_address, payload['params']['timestamp'], text)):
			print('\naborted')
			return None
	
		response = self.make_request(payload)
		
		utx = response['result']
		tx = self.btc.sign_and_send(utx)
		self.output('Successfully sent broadcast: {}'.format(tx))
		return tx
	
	@bitcoin_address_required
	def _prompt_send_broadcast(self):
		text = raw_input('Please provide me with the text of the broadcast?\n')
		
		value = raw_input('Please provide me with a broadcast value (optional)? ')
		if value == '':
			value = 0.0
		
		fee_fraction = raw_input('Please provide me with a fee fraction (optional)? ')
		if fee_fraction == '':
			fee_fraction = 0.0
		
		return self.send_broadcast(text, value, fee_fraction)
	
	def change_asset_description(self, asset, description, divis):
		payload = {
			"method": "create_issuance",
			"params": {
				'source': self.btc.selected_address, 'pubkey': self.btc.selected_address_info['pubkey'],
				'asset': asset, 'quantity': 0,
				'description': description, 'divisible': divis,
				'encoding': 'multisig'
			}
		}
		if not self.confirm_prompt('Do you really want me to change the description of {} to be "{}" ?'.format(asset, description)):
			print('\naborted')
			return None
		
		response = self.make_request(payload)
		
		utx = response['result']
		tx = self.btc.sign_and_send(utx)
		
		if tx:
			self.output('Successfully changed the description of {}: {}'.format(asset, tx))
		else:
			self.output('There was an error creating the issuance call ({})'.format(tx))
		return tx
	
	@bitcoin_address_required
	def _prompt_change_asset_description(self):
		print('checking for owned assets...')
		assets = self.get_all_owned_assets()
		if not assets:
			self.output('You do own any assets in this address ({}), so you cannot change the description of anything.'.format(self.btc.selected_address))
			return None
		
		choice = self.prompt(assets, title='\nYou would like me to change the description for which owned asset? ', choicemsg='Which asset? ')
		asset = assets[choice]
		
		desc = self.get_description(asset)
		divis = self.get_divisibility(asset)
		
		print('This is the current description: {}\n'.format(desc))
		new_desc = raw_input('\nPlease provide me with your new description: ')
		
		return self.change_asset_description(asset, new_desc, divis)
	
	def issue_additional(self, asset, amount, divis, description):
		payload = {
			"method": "create_issuance",
			"params": {
				'source': self.btc.selected_address,
				'pubkey': self.btc.selected_address_info['pubkey'],
				'asset': asset,
				'quantity': amount,
				'description': description, 
				'divisible': divis,
				'encoding': 'multisig'
			}
		}
		disp_amnt = self.from_satoshis(amount) if divis else amount
		if not self.confirm_prompt('Do you really want me to issue {} more {}?'.format(disp_amnt, asset)):
			print('\naborted')
			return None
		
		response = self.make_request(payload)
		
		utx = response['result']
		tx = self.btc.sign_and_send(utx)
		
		if tx:
			self.output('Successfully issued {}: {}'.format(asset, tx))
		else:
			self.output('There was an error creating the issuance call ({})'.format(tx))
		return tx
	
	@bitcoin_address_required
	def _prompt_issue_additional(self):
		print('checking for owned assets...')
		all_assets = self.get_all_owned_assets()
		if not all_assets:
			self.output('You do own any assets in this address ({}), so you cannot issue more of anything.'.format(self.btc.selected_address))
			return None
		assets = [a for a in all_assets if not self.get_locked(a)]
		if not assets:
			print('All of the assets that you own are locked, so you cannot issue any more of anything.')
			return None
		choice = self.prompt(assets, title='Which asset would you like me to issue more of?', choicemsg='Which asset? ')
		asset = assets[choice]
		
		divis = self.get_divisibility(asset)
		desc = self.get_description(asset)
		
		amount = None
		while amount is None:
			amount = raw_input('How many would you like me to issue? ')
			try:
				if divis:
					amount = self.to_satoshis(amount)
				else:
					try:
						amount = int(amount)
					except Exception as e:
						print('{} is indivisible, you must enter a whole number: {} ({}).\n'.format(asset, e, type(e)))
						amount = None
			except Exception as e:
				print('Exception: {}'.format(e))
				amount = None
		
		return self.issue_additional(asset, amount, divis, desc)
	
	def lock_asset(self, asset, divis):
		payload = {
			"method": "create_issuance",
			"params": {
				'source': self.btc.selected_address, 'pubkey': self.btc.selected_address_info['pubkey'],
				'asset': asset, 'quantity': 0, 
				'description': 'LOCK', 'divisible': divis,
				'encoding': 'multisig'
			}
		}
		if not self.confirm_prompt('\nDo you really want me to lock {} ?'.format(asset)):
			print('\naborted')
			return None
		
		response = self.make_request(payload)
		utx = response['result']
		tx = self.btc.sign_and_send(utx)
		if tx:
			self.output('Successfully locked {}: {}'.format(asset, tx))
			return True
		else:
			self.output('There was an error creating the lock call ({})'.format(tx))
			return False
	
	@bitcoin_address_required
	def _prompt_lock_asset(self):
		print('checking for owned assets...')
		assets = self.get_all_owned_assets()
		if not assets:
			self.output('You do not own any assets in this address ({}), so you cannot lock anything.'.format(self.btc.selected_address))
			return None
		
		choice = self.prompt(assets, title='\nWhich asset would you like to lock? ', choicemsg='(number)-> ')
		asset = assets[choice]
		
		divis = self.get_divisibility(asset)
		
		return self.lock_asset(asset, divis)
	
	def transfer_asset(self, asset, divisibility, description, destination):
		payload = {
			"method": "create_issuance",
			"params": {
				'source': self.btc.selected_address, 'pubkey': self.btc.selected_address_info['pubkey'],
				'asset': asset, 'quantity': 0,
				'description': description, 'divisible': divisibility,
				'transfer_destination': destination,
				'encoding': 'multisig'
			}
		}
		if not self.confirm_prompt('\nDo you really want to transfer ownership of {} to {} ?'.format(asset, destination)):
			print('\naborted')
			return None
		
		response = self.make_request(payload)
		utx = response['result']
		tx = self.btc.sign_and_send(utx)
		if tx:
			self.output('Successfully transferred ownership of {}:\n{}'.format(asset, tx))
			return True
		else:
			self.output('There was an error creating the transfer call ({})'.format(tx))
			return False
	
	@bitcoin_address_required
	def _prompt_transfer_asset(self):
		print('\nchecking for owned assets...')
		assets = self.get_all_owned_assets()
		if not assets:
			self.output('You do own any assets in this address ({}), so you cannot transfer anything.'.format(self.btc.selected_address))
			return None
		
		choice = self.prompt(assets, title='\nWhich asset would you like to transfer', choicemsg='Which asset? ')
		asset = assets[choice]
		
		divis = self.get_divisibility(asset)
		desc = self.get_description(asset)
		
		transfer_destination = raw_input('To which address would you like to transfer ownership? ').strip()
		
		return self.transfer_asset(asset, divis, desc, transfer_destination)
	
	@bitcoin_address_required
	def get_all_owned_assets(self):
		return self.get_all_issued_assets()
	
	@bitcoin_address_required
	def get_all_issued_assets(self):
		payload = {
			'method': 'get_issuances',
			'params': {
				'filters': [
					{'field': 'issuer', 'op': '==', 'value': self.btc.selected_address}
				]
			},
			'jsonrpc': '2.0',
			'id': 0
		}
		resp = self.make_request(payload)['result']
		assets = [x['asset'] for x in resp]
		return list(set(assets))
	
	def get_description(self, asset):
		payload = {
			'method': 'get_issuances',
			'params': {
				'filters': [
					{'field': 'asset', 'op': '==', 'value': asset}
				]
			},
			'jsonrpc': '2.0',
			'id': 0
		}
		resp = self.make_request(payload)['result']
		return resp[-1]['description']
	
	def print_diagnostics(self):
		r = self.get_running_info()
		xcpi = r['result']
		outs = 'I am attempting to speak to the Counterparty network for you...\n'
		outs += '\nMy grand magnificence is allowing me to speak to Counterparty v{}.{}.{}\n\nThe last block I have seen via Counterparty is {}.\n'.format(xcpi['version_major'],xcpi['version_minor'],xcpi['version_revision'],xcpi['last_block']['block_index'])
		if xcpi['db_caught_up'] == True:
			outs += "\nCounterparty tells me that its database is up to date. It should listen to requests I make on your behalf."
		self.output(outs)
	
	def get_running_info(self):
		payload = {
		  "method": "get_running_info",
		  "jsonrpc": "2.0",
		  "id": 0,
		}
		response = self.make_request(payload)
		return response