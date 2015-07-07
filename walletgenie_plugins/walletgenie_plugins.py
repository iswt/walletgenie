import os
import sys

sys.dont_write_bytecode = True
WINDOWS = False
if sys.platform == 'win32':
	WINDOWS = True

import glob
try:
	import ConfigParser
except ImportError:
	try:
		import configparser as ConfigParser
	except ImportError:
		print('Unable to import ConfigParser, install it with: `pip install ConfigParser`')
		sys.exit(0)

from getpass import getpass
import time
import json

from walletgenie import WalletGenie, prompt
from walletgenie import USER_CONFIG_DIR, PLUGINS_DIR, AVAILABLE_PLUGINS_DIR

class BasePlugin(object):
	
	main_menu = None
	available_plugins = []
	active_plugins = {} # {name, loader, plugin_class}
	active_plugin = None
	
	def __init__(self, pluginlist, active_plugins, active_plugin, load_plugin_func):
		self.available_plugins = pluginlist
		self.active_plugins = active_plugins
		self.active_plugin = active_plugin
		self.load_plugin = load_plugin_func
	
	def cleanup(self):
		pass
	
	def to_satoshis(self, num):
		return int( float(num) * 1e8 )
	
	def from_satoshis(self, num):
		return float(num) / 1e8
	
	def formatted(self, f):
		return format(float(f), ',.8f').rstrip('0').rstrip('.')
	
	def output(self, message):
		longest_str = sorted(message.split('\n'), key=lambda x: len(x))[-1]
		border = '*' * len(longest_str)
		print('\n{0}\n\n{1}\n\n{0}\n'.format(border, message))
	
	def prompt(self, what, title=None, choicemsg='What is thy bidding, O\' Exhalted Master of the Keys? ', errormsg='I\'m sorry, but I didn\'t understand you. Please try again.'):
		return prompt(what, title=title, choicemsg=choicemsg, errormsg=errormsg)
	
	def confirm_prompt(self, message, title=None, choicemsg='[y/N]: ', extra_valid_responses=[], default_to_yes=False):
		if title:
			print('\n{}\n'.format(title))
		print('\n{}'.format(message))
		answer = raw_input(choicemsg)
		if answer.lower() not in ['y', 'yes', 'yep', 'yup', 'ok', 'sure', 'why not'] + extra_valid_responses:
			if default_to_yes:
				if answer == '':
					return True
			
			return False
		else:
			return True
	
	def on_plugin_update(self, plugins, loaded_plugins, active_plugin):
		self.available_plugins = plugins
		self.active_plugins = loaded_plugins
		self.active_plugin = active_plugin
	
	def require_plugin(self, plugin, autoload_if_available=False):
		if not plugin in self.active_plugins.keys():
			if not plugin in self.available_plugins:
				print('{} not found in the available plugins'.format(plugin))
				return False
			else:
				print('{} was found and is available, but is not yet loaded'.format(plugin))
				if autoload_if_available:
					print('Attempting to load {}...'.format(plugin))
					self.load_plugin(plugin)
					return True
					
			return False
		return True
	
class WalletGenieImportError(Exception):
	def __init__(self, message):
		super(WalletGenieImportError, self).__init__(message)

class BasePluginCoin(BasePlugin):
	'''
	implements functions from python-bitcoinrpc with the intention of being useful in coins that have the same/similar rpc calls
	'''
	def __init__(self, access_string, *args, **kwargs):
		super(BasePluginCoin, self).__init__(*args, **kwargs)
		try:
			import bitcoinrpc
		except ImportError:
			print('Unable to import bitcoinrpc, install it with: `pip install python-bitcoinrpc`')
			raise WalletGenieImportError('python-bitcoinrpc')
		
		class AuthServiceProxyWithErrorDisplay(bitcoinrpc.authproxy.AuthServiceProxy):
			def __call__(self, *args):
				try:
					return super(AuthServiceProxyWithErrorDisplay, self).__call__(*args)
				except bitcoinrpc.authproxy.JSONRPCException as e:
					if 'message' not in e.error.keys() and 'id' not in e.error.keys():
						msg = '{}'.format(e.error)
					else:
						msg = '{}'.format(e.error['message'])
					border = '*' * len(msg)
					print('\n{0}\n\nError: {1}\n\n{0}'.format(border, msg))
					return None
		
		bitcoinrpc.authproxy.AuthServiceProxy = AuthServiceProxyWithErrorDisplay
		self.access = bitcoinrpc.authproxy.AuthServiceProxy(access_string)
		self.RPCException = bitcoinrpc.authproxy.JSONRPCException
	
	def shapeshift_withdrawal(self, coin, **kwargs):
		_netki = False
		withdrawal_msg = 'To which address would you like to receive your {} to? '.format(coin.upper())
		if coin.upper() in ['BTC', 'LTC', 'DOGE', 'NMC', 'USDT']:
			_netki = True
			withdrawal_msg = 'To which address or netki domain would you like to receive your {} to? '.format(coin.upper())
		
		
		withdrawal_addy = raw_input(withdrawal_msg)
		vret = kwargs['address_validator'](withdrawal_addy, coin)
		isvalid = vret['isvalid']
		while not isvalid:
			netki_addy = None
			if _netki and '.' in withdrawal_addy:
				print('Checking netki for a wallet by the name of {}'.format(withdrawal_addy))
				netki_addy = self.get_address_by_netki_wallet(withdrawal_addy, self.coin_name.lower(), printerrors=False)
				if netki_addy:
					vret = kwargs['address_validator'](netki_addy, coin)
					isvalid = vret['isvalid']
					if not isvalid:
						print('Address returned for {} ({}) is not a valid address for {}.\n'.format(withdrawal_addy, netki_addy, coin.upper()))
						withdrawal_addy = raw_input(withdrawal_msg)
						vret = kwargs['address_validator'](withdrawal_addy, coin)
						isvalid = vret['isvalid']
					else:
						print('The address that belongs to {} is {}. Setting that as the destination address.'.format(withdrawal_addy, netki_addy))
						withdrawal_addy = netki_addy
				else:
					print('No netki user was found.\n')
			else:
				print('Invalid address.\n')
				
			if not netki_addy:
				withdrawal_addy = raw_input(withdrawal_msg)
				vret = kwargs['address_validator'](withdrawal_addy, coin)
				isvalid = vret['isvalid']
				
		return withdrawal_addy
	
	def choose_address(self, allow_empty=False):
		active_addresses = self.get_wallet_addresses(allow_empty=allow_empty)
		
		disp = [x[0] for x in active_addresses]
		if not disp:
			return None
		
		active_address = self.prompt(
			disp, title='\nLocal wallet {}addresses:\n'.format('(non-zero balance) ' if not allow_empty else ''), 
			choicemsg='\nWhich wallet number should I use? '
		)
		
		self.output('Address {} selected and active'.format(active_addresses[active_address][0]))
		
		retaddy, retbal = active_addresses[active_address][0], active_addresses[active_address][1]
		
		return retaddy
	
	
	def _print_diagnostics(self, coin):
		outs = 'I am attempting to speak to the {} network for you...\n'.format(coin)
		xtci = self.access.getinfo()
		outs += '\nUsing my awesome powers, I am now speaking to {}d v{}, which is connected to {} other nodes around the world.\n\nThe last block I have seen on the blockchain is {}.\n'.format(coin, xtci['version'], xtci['connections'], xtci['blocks'])
		try:
			if xtci['unlocked_until'] == 0:
				outs += '\nYour local wallet is encrypted and locked. You will need to tell me the magic phrase for certain functions to succeed.'
			else:
				timeremaining = int(xtci['unlocked_until']) - int(time.time())
				outs += '\nYour local wallet is encrypted, but I still remember your magic phrase for the next {} seconds, at which time it will fade from my memory.'.format(timeremaining)
			self.encrypted_wallet = True
		except KeyError as e:
			outs += "\nYour local wallet is not protected by a magic phrase. Your wish is my command."
		
		self.output(outs)
	
	def _prompt_get_balance(self, coin):
		amnt = self.get_balance()
		self.output('You have: {} {} in your coffers.'.format(self.formatted(amnt), coin))
	
	def get_balance(self):
		return self.access.getbalance()
	
	def sendto(self, toaddress, amount):
		self.try_unlock_wallet()
		tx = self.access.sendtoaddress(toaddress, amount)
		self.try_lock_wallet()
		return tx
	
	def _prompt_send(self, coin):
		promptmsg = 'To which address or netki domain would you like me to send {}? '.format(coin)
		
		toaddy = raw_input(promptmsg).strip()
		validaddy = self.access.validateaddress(toaddy)
		isvalid = validaddy['isvalid']
		while not isvalid:
			netki_addy = None
			if '.' in toaddy:
				print('Checking netki for a wallet by the name of {}'.format(toaddy))
				netki_addy = self.get_address_by_netki_wallet(toaddy, coin.lower(), printerrors=False)
				if netki_addy:
					validaddy = self.access.validateaddress(netki_addy)
					isvalid = validaddy['isvalid']
					if not isvalid:
						print('Address returned for {} ({}) is not a valid address for {}\n'.format(toaddy, netki_addy, coin.upper()))
						toaddy = raw_input(promptmsg)
						validaddy = self.access.validateaddress(toaddy)
						isvalid = validaddy['isvalid']
					else:
						print('The address that belongs to {} is {}. Setting that as the destination address.'.format(toaddy, netki_addy))
						toaddy = netki_addy
				else:
					print('No netki user was found.')
			else:
				print('Invalid address\n')
			
			if not netki_addy:
				toaddy = raw_input(promptmsg)
				validaddy = self.access.validateaddress(toaddy)
				isvalid = validaddy['isvalid']
		
		coin_amnt = self.get_balance()
		amount = raw_input('How many {0} do you wish me to send to {1} (you have {2} {0} available)? '.format(
			coin, toaddy, self.formatted(coin_amnt)
		)).strip()
		
		if not self.confirm_prompt('Do you really want to send {} {} to {}?'.format(self.formatted(amount), coin, toaddy)):
			print('\naborted...')
			return None
		
		tx = self.sendto(toaddy, float(amount))
		if tx:
			self.output('Sent tx: {}'.format(tx))
		return tx
	
	def getnewaddress(self, label=''):
		return self.access.getnewaddress(label)
	
	def _prompt_get_new_address(self, default_label=''):
		label = raw_input('What label would you like to use? [blank for default]: ')
		if label == '':
			label = default_label
		tx = self.getnewaddress(label)
		self.output('Successfully created new address: {}'.format(tx))
	
	def sign_tx(self, utx):
		stx = self.access.signrawtransaction(utx)
		assert stx['complete']
		
		return stx['hex']
	
	def broadcast_tx(self, stx):
		tx = self.access.sendrawtransaction(stx)
		return tx
	
	def sign_message(self, addy, message):
		self.try_unlock_wallet()
		tx = self.access.signmessage(addy, message)
		self.try_lock_wallet()
		return tx
	
	def _prompt_sign_message(self):
		addy = self.choose_address(allow_empty=True)
		message = raw_input('Please provide me with the message you would like to sign.\nMessage: ')
		tx = self.sign_message(addy, message)
		self.output('Address: {}\nSigned: {}\nMessage: {}'.format(addy, tx, message))
	
	def verify_message(self, address, signature, message):
		return self.access.verifymessage(address, signature, message)
	
	def _prompt_verify_message(self):
		signature = raw_input('Please provide me with the (base64 encoded) signed message: ').strip() # strip extraneous spaces
		message = raw_input('Please provide me with the unsigned, plaintext message: ')
		address = raw_input('Please provide me with the address that claims to have signed the message: ').strip()
		
		signed = self.verify_message(address, signature, message)
		if signed:
			self.output('I can confirm the message was definitely signed by {}'.format(address))
		else:
			self.output('The message failed verification. (double check that your input was correct)')
	
	def is_wallet_encrypted(self):
		try:
			info = self.access.getinfo()
			if 'unlocked_until' in info.keys():
				return True
			else:
				return False
		except self.RPCException as e:
			self.output('[code {}] {}'.format(e.error['code'], e.error['message']))
			return False
	
	def unlock_wallet(self, printsuccess=False, printerrors=False, modify_duration=False):
		if not self.is_wallet_encrypted():
			if printerrors:
				self.output('Your wallet is not encrypted. It\'s been unlocked this entire time!')
			return True
			
		try:
			wallet_passphrase = None
			duration = None
			while wallet_passphrase is None:
				wallet_passphrase = getpass('Please tell me your magic phrase. I promise not to tell anyone: ')
			if modify_duration:
				while duration is None:
					duration = raw_input('How long shall I keep the wallet unlocked (seconds)? [default: 300]: ')
					if duration == '':
						duration = 300
					else:
						try:
							assert int(duration)
						except AssertionError:
							print('Invalid duration')
							duration = None
			else:
				duration = 120 # default to 2 minutes
				
			isvalid = self.access.walletpassphrase(wallet_passphrase, int(duration))
			if isvalid == False: # isvalid == None is a valid response...
				return False
		except self.RPCException as e:
			self.output('[code {}] {}'.format(e.error['code'], e.error['message']))
			return False
		
		if printsuccess:
			self.output('I have successfully unlocked your wallet for {} seconds.'.format(duration))
		return True
	
	def try_lock_wallet(self, printsuccess=False, printerrors=False):
		if not self.is_wallet_encrypted():
			if printerrors:
				self.output('Your wallet is not encrypted. It\'s been unlocked this entire time!')
			return True
		
		try:
			self.access.walletlock()
		except Exception as e:
			print('lockwallet: {} ({})'.format(e, type(e)))
		if printsuccess:
			print('Successfully locked your wallet')
		return True
	
	def try_unlock_wallet(self, printsuccess=False, modify_duration=False, ask_until_correct=True):
		'''
		attempt to unlock the wallet
		return true if the wallet is not encrypted, is currently unlocked, or the user successfully unlocks it
		return false if the wallet is encrypted and the user fails to unlock
		'''
		try:
			info = self.access.getinfo()
			if info['unlocked_until'] == 0:
				if not self.unlock_wallet(printsuccess=printsuccess, modify_duration=modify_duration):
					if ask_until_correct:
						correct = False
						while not correct:
							correct = self.unlock_wallet(printsuccess=printsuccess, modify_duration=modify_duration)
					else:
						return False
		except KeyError:
			pass # wallet is unlocked
		return True
	
	def sign_and_send(self, utx):
		self.try_unlock_wallet()
		
		stx = self.sign_tx(utx)
		tx = self.broadcast_tx(stx)
		
		self.try_lock_wallet()
		
		return tx
	
	def get_wallet_addresses(self, allow_empty=False):
		wallet_addresses = self.access.listaddressgroupings()
		active = []
		
		for w in wallet_addresses:
			for tup in w:
				addy, balance = tup[0], tup[1]
				if allow_empty:
					active.append( (addy, balance) )
				else:
					if float(balance) > 0:
						active.append( (addy, balance) )
		
		just_addresses = [x[0] for x in active]
		
		addys_by_acc = self.get_wallet_addresses_a()
		for aa in addys_by_acc:
			if aa not in just_addresses and allow_empty:
				active.append( (aa, 0.0) )
				
		return active # returns a list of tuples [(address, btc balance), ...]
	
	def get_wallet_addresses_a(self):
		existing_accounts = self.access.listaccounts()
		accs = [ x[0] for x in existing_accounts.iteritems() ]
		
		wallet_addresses = []
		for a in accs:
			l = self.access.getaddressesbyaccount(a)
			for x in l:
				wallet_addresses.append(x)
		return wallet_addresses
	
	def import_privkey(self):
		if not self.confirm_prompt('This process will rescan your wallet, which is likely to take a long time. Are you sure that you want to continue? [y/N]: '):
			print('\naborted...')
			return None	
			
		privkey = raw_input('Please provide me with the private key you wish to import: ')
		label = raw_input('Please provide me with an optional label for this account [blank for none]: ')
		
		self.try_unlock_wallet()
		
		tx = self.access.importprivkey(privkey, label)
		self.output('I have successfully imported your private key: {}'.format(tx))
		return tx
	
	def import_watch_address(self):
		if not self.confirm_prompt('This process will rescan your wallet, which is likely to take a long time. Are you sure that you want to continue?\n'):
			print('\naborted...')
			return None
		
		addr = raw_input('Please provide me with the address you would like me to watch: ')
		label = raw_input('Please provide me with an optional label for this account [blank for none]: ')
		
		rescan = True # I think that this is always true, regardless
		
		tx = self.access.importaddress(addr, label=label, rescan=rescan)
		
		self.output('I have imported the watch-only address {}: {}'.format(addr, tx))
		return tx
	
	def change_passphrase(self, oldpw, newpw):
		return self.access.walletpassphrasechange(oldpw, newpw)
	
	def _prompt_change_passphrase(self):
		if not self.is_wallet_encrypted():
			self.output('Your wallet is not encrypted, I can\'t change it\'s passphrase!')
			return None
			
		old_passphrase = getpass('Please provide me with your current magic phrase: ')
		confirmed = False
		while not confirmed:
			new_passphrase = getpass('Please provide me with your new magic phrase: ')
			confirm_new_passphrase = getpass('Please confirm your new magic phrase: ')
			if new_prassphrase != confirm_new_passphrase:
				print('Your magic phrases do not match. Please try again.')
			else:
				confirmed = True
		
		if not self.confirm_prompt('Are you sure you want to change your magic phrase? '):
			print('abort')
			return None
		
		tx = self.change_passphrase(old_passphrase, new_passphrase)
		self.output('Successfully changed password: {}'.format(tx))
		return tx
	
	def encrypt_wallet(self, pw):
		return self.access.encryptwallet(pw)
	
	def _prompt_encrypt_wallet(self):
		if self.is_wallet_encrypted():
			self.output('Your wallet is already encrypted')
			return None
		
		confirmed = False
		while not confirmed:
			encrypt_passphrase = getpass('Please provide me with your magic phrase. I will use it to encrypt your wallet: ')
			confirm_passphrase = getpass('Please confirm your magic phrase: ')
			if encrypt_passphrase != confirm_passphrase:
				print('\nThe magic phrases do not match.\n')
			else:
				confirmed = True
		
		if not self.confirm_prompt('Do you really want to encrypt the wallet with this magic phrase? '):
			print('\naborted')
			return None
		
		tx = self.encrypt_wallet(encrypt_passphrase)
		self.output('I successfully encrypted your wallet: {}'.format(tx))
		return tx
	
	def get_address_by_netki_wallet(self, wallet, coin, printerrors=True):
		try:
			import requests
		except ImportError:
			self.output('requests module not found, netki lookup disabled -- enable it by installing requests: `pip install requests`')
			return None
		
		url = 'https://netki.com/api/wallet_lookup/'
		headers = {
			'Host': 'netki.com', 'User-Agent': 'WalletGenie netki integration',
			'Content-type': 'application/json'
		}
		try:
			try:
				response = requests.get('{}{}/{}'.format(url, wallet, coin.lower()), headers=headers)
			except NameError:# requests not imported
				if printerrors:
					print('requests is not imported, cannot lookup netki domain information.')
				return None
				
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

class FakeSecHead(object):
	def __init__(self, fp):
		self.fp = fp
		self.sechead = '[fakesec]\n'
	
	def readline(self):
		if self.sechead:
			try:
				return self.sechead
			finally:
				self.sechead = None
		else:
			return self.fp.readline()

class WalletGenieConfigParser(ConfigParser.SafeConfigParser, object):
	
	def __init__(self, defaults=None):
		super(WalletGenieConfigParser, self).__init__(defaults)
	
	def readfp(self, fp, filename=None):
		return super(WalletGenieConfigParser, self).readfp( FakeSecHead(fp), filename=filename )
	
	def write(self, fp):
		'''
		subclassed to not write out the individual section headers
		'''
		if self._defaults:
			fp.write("[DEFAULT]\n")
			for (key, value) in self._defaults.items():
				fp.write("%s = %s\n" % (key, value))
			fp.write("\n")
		for section in self.sections():
			sectdict = self._sections[section]
			for (key, value) in sectdict.items():
				if key == "__name__":
					continue
				fp.write("%s = %s\n" % (key, value))
		fp.write("\n")

class WalletGenieConfigurationError(Exception):
	def __init__(self, message):
		super(WalletGenieConfigurationError, self).__init__(message)

class WalletGenieConfig(WalletGenie):
	
	def __init__(self, config_dir=USER_CONFIG_DIR):
		if WINDOWS:
			config_dir += '\\'
		else:
			config_dir += '/'
		self.config_dir = config_dir
	
	def read_coin_config(self, config_file, header='fakesec'):
		scp = ConfigParser.SafeConfigParser()
		scp.readfp(FakeSecHead(open(config_file)))
		
		confitems = scp.items(header)
		retd = {}
		
		for key, value in confitems:
			retd[key] = value
		
		return retd
	
	def check_and_load(self, config_file, config_dir=USER_CONFIG_DIR, default_conf_loc=None, required_values=[], default_values={}, silent=True):
		if WINDOWS:
			enddir_symbol = '\\'
		else:
			enddir_symbol = '/'
		config_dir += enddir_symbol
		
		configs_full = self.checkForConfigs(config_dir)
		configs = [ cf[cf.rfind(enddir_symbol) + 1 : ] for cf in configs_full ] #strip out the full path and just get conf file names
		if not configs:
			if not silent:
				print('No configuration files')
			return None
			
		if config_file[ config_file.rfind(enddir_symbol) + 1 :  ] not in configs:
			# config file not found
			return None
		else:
			wgcp = WalletGenieConfigParser()
			wgcp.readfp(open('{}{}'.format(config_dir, config_file)))
			
			confitems = wgcp.items('fakesec')
			d = {}
			for item in confitems:
				d[item[0]] = item[1]
			
			try:
				for rv in required_values:
					assert rv in d.keys()
			except AssertionError as e:
				if not silent:
					print('Error reading config file: {}'.format(e))
				return None
			
			# append default values if they don't exist
			for key, value in default_values.iteritems():
				if key not in d.keys():
					d[key] = value
			
			return d
	
	def set_from_coin(self, out_config, default_conf_loc=None, coin_conf_header='fakesec'):
		filepath = None
		while filepath is None:
			filepath = raw_input(
				'Enter configuration file directory {}'.format(
					'[default: {}]'.format(default_conf_loc) if default_conf_loc is not None else ''
				)
			).strip()
			if filepath == '':
				if default_conf_loc is not None:
					filepath = default_conf_loc
				else:
					filepath = None
			try:
				d = self.read_coin_config(filepath, header=coin_conf_header)
				self.setConfig(out_config, d)
			except IOError as e:
				print('Error reading configuration file {}: {}'.format(filepath, e))
				filepath = None
	
	def set_from_coin_or_text(self, out_config, default_conf_loc=None, coin_conf_header='fakesec', config_vars=None):
		filepath = None
		
		try:
			prompt_disp = 'Read from coin configuration file'
			if default_conf_loc:
				if '/' in default_conf_loc:
					prompt_disp = 'Read from {}'.format(default_conf_loc[default_conf_loc.rfind('/') + 1 : ])
				else:
					prompt_disp = default_conf_loc
			choice = self.prompt(['Enter values manually', prompt_disp], title='How would you like to create this configuration?\n', choicemsg='Which method? ')
			d = {}
			if choice == 0:
				if not config_vars:
					return False
				
				for var, default_value in config_vars:
					if default_value is not None:
						val = raw_input('{} (default: {}): '.format(var, default_value))
						if val == '':
							val = default_value
					else:
						val = raw_input('{}: '.format(var))
					d[var] = val
				
				tryagain = True
				while tryagain:
					try:
						self.setConfig(out_config, d)
						return True
					except Exception as e:
						print('Error setting configuration file {} {}: ({})'.format(filepath, e, type(e)))
						yorn = raw_input('Try setting again?\n[y/N]: ').strip().lower()
						if yorn != 'y':
							tryagain = False
				return False
			
			while filepath is None:
				filepath = raw_input(
					'Enter configuration file directory{}'.format(
						' [default: {}]: '.format(default_conf_loc) if default_conf_loc is not None else ': '
					)
				)
				if filepath == '':
					if default_conf_loc is not None:
						filepath = default_conf_loc
					else:
						filepath = None
				try:
					d = self.read_coin_config(filepath, header=coin_conf_header)
					if config_vars:
						outd = {}
						for var, default_value in config_vars:
							if var not in d.keys() and default_value is not None:
								d[var] = default_value
							try:
								outd[var] = d[var]
							except KeyError as e:
								print('Cannot read value from configuration file: {}'.format(e))
					else:
						outd = d
					
					self.setConfig(out_config, outd)
				except IOError as e:
					print('Error reading configuration file {}: {}\n'.format(filepath, e))
					filepath = None
		except KeyboardInterrupt:
			return None
		return True
	
	def checkForConfigs(self, config_dir):
		configs = []
		if WINDOWS:
			enddir_symbol = '\\'
		else:
			enddir_symbol = '/'
		
		for f in glob.glob('{}*.conf'.format( '{}{}'.format(config_dir, enddir_symbol) if config_dir[-1] != enddir_symbol else config_dir )):
			configs.append(f)
		return configs
	
	def setConfig(self, config_file, infod, config_dir=USER_CONFIG_DIR):
		if WINDOWS:
			config_dir += '\\'
		else:
			config_dir += '/'
		
		wgcp = WalletGenieConfigParser()
		conffile = '{}{}'.format(config_dir, config_file)
		
		try:
			wgcp.readfp(open(conffile, 'w+'))
			for key, value in infod.iteritems():
				try:
					wgcp.set('fakesec', key, str(value))
				except Exception as e:
					print('Exception setting config: {} ({})'.format(e, type(e)))
			wgcp.write(open(conffile, 'w'))
		except IOError as e:
			if int(e.errno) == 2: # no such file
				try:
					wgcp.write(open(conffile, 'w+'))
				except IOError as e:
					print('IOError writing {}: {}'.format(conffile, e))
			else:
				print('IOError writing {}: {}'.format(conffile, e))
		
		print('Successfully wrote {} at {}'.format(config_file, config_dir))