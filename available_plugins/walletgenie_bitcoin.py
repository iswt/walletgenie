from walletgenie_plugins import BasePlugin, WalletGenieConfig, WalletGenieConfigurationError

import sys
import time
from getpass import getpass
try:
	from bitcoin.core import b2x, b2lx
	import bitcoin.rpc
except ImportError:
	print('Unable to import bitcoinlib -- install it with: `pip install python-bitcoinlib`')
	sys.exit(0)

class BitcoinRPCProxy(bitcoin.rpc.Proxy):
	'''
	wrap all _call functionality to catch JSONRPCException and print out the error
	'''
	def _call(self, service_name, *args):
		try:
			return super(BitcoinRPCProxy, self)._call(service_name, *args)
		except bitcoin.rpc.JSONRPCException as e:
			msg = '{}'.format(e.error['message'])
			border = '*' * len(msg)
			print('\n{0}\n\n{1}\n\n{0}'.format(border, msg))
			return False

class Bitcoin(BasePlugin):
	
	coin_name = 'BTC' # shapeshift plugin
	
	def __init__(self, *args, **kwargs):
		
		super(Bitcoin, self).__init__(*args, **kwargs)
		
		self.config_file = 'wgbitcoin.conf'
		self.required_config_vars = ['rpcpassword']
		self.default_config_vars = {'rpcuser': 'rpc', 'rpcssl': 0, 'rpcport': '8332', 'rpcurl': '127.0.0.1'}
		
		self.main_menu = {
			0: {
				'description': 'Genie, are you currently able to speak to the bitcoin network?',
				'insert_before': '\n--- Bitcoin Functions ---\n',
				'callback': self.print_diagnostics
			},
			1: {
				'description': 'Genie, how many bitcoin do I have in my coffers?',
				'callback': self.get_balance
			},
			2: {
				'description': 'Genie, I wish to send bitcoin to an address.',
				'callback': self.send_btc
			},
			3: {
				'description': 'Genie, I wish to sign a message from an address I control.',
				'callback': self.sign_message
			},
			4: {
				'description': 'Genie, I wish to verify the origin of this signed message.',
				'callback': self.verify_message
			},
			5: {
				'description': 'Genie, I wish to add another private key to my wallet.',
				'callback': self.import_privkey
			},
			6: {
				'description': 'Genie, I wish to watch this external address. Keep track of it for me.',
				'callback': self.import_watch_address
			},
			7: {
				'description': 'Genie, I wish to create a new address into which I can receive more bitcoin.',
				'callback': self.get_new_address
			},
			8: {
				'description': 'Genie, I wish to unlock my wallet so you can perform some transactions on my behalf.',
				'callback': lambda printsuccess=True, printerrors=True, modify_duration=True: self.unlock_wallet(printsuccess, printerrors, modify_duration)
			},
			9: {
				'description': 'Genie, I wish to lock my wallet to keep my bitcoin safe from thieves.',
				'callback': lambda printsuccess=True, printerrors=True: self.try_lock_wallet(printsuccess, printerrors)
			},
			10: {
				'description': 'Genie, I wish to protect my bitcoin coffers with a magic phrase. Keep my bitcoin safe from thieves. TNO.',
				'callback': self.encrypt_wallet
			},
			11: {
				'description': 'Genie, I wish to change my magic phrase. There are scoundrels all around.',
				'callback': self.change_passphrase
			}
		}
		
		self.selected_address = None
		self.selected_address_info = None # {isvalid, address, ismine, isscript, pubkey, iscompressed, account}
		self.encrypted_wallet = False
		
		wgc = WalletGenieConfig()
		self.rpcd = wgc.check_and_load(self.config_file, required_values=self.required_config_vars, default_values=self.default_config_vars)
		if self.rpcd is None:
			print('\nIt appears that {} does not yet exist. If this is your first time running the walletgenie_bitcoin plugin, you will need a configuration file detailing your RPC Connection information.\n'.format(self.config_file))
			confvars = [(x, None) for x in self.required_config_vars if x not in self.default_config_vars.keys()]
			confvars += self.default_config_vars.items()
			wgc.set_from_coin_or_text(
				self.config_file, default_conf_loc='/home/bitcoin/.bitcoin/bitcoin.conf',
				config_vars=confvars
			)
			self.rpcd = wgc.check_and_load(self.config_file, required_values=self.required_config_vars, default_values=self.default_config_vars, silent=False)
			if not self.rpcd:
				print('\n\nUnable to load configuration file: {}\nAborting Bitcoin plugin\n'.format(self.config_file))
				raise WalletGenieConfigurationError(self.config_file)
			
		self.access = BitcoinRPCProxy(
			service_url='{}://{}:{}@{}:{}'.format(
				'https' if int(self.rpcd['rpcssl']) else 'http', self.rpcd['rpcuser'], self.rpcd['rpcpassword'], self.rpcd['rpcurl'], self.rpcd['rpcport']
			)
		)
	
	def choose_address(self):
		active_addresses = self.get_wallet_addresses()
		
		disp = [x[0] for x in active_addresses]
		active_address = self.prompt(
			disp, title='\nLocal wallet (non-zero balance) addresses:\n', 
			choicemsg='\nWhich wallet number should I use? '
		)
		
		self.output('Address {} selected and active'.format(active_addresses[active_address][0]))
		
		retaddy, retbal = active_addresses[active_address][0], active_addresses[active_address][1]
		
		self.selected_address = retaddy
		self.selected_address_info = self.access.validateaddress(self.selected_address)
		self.selected_address_info['pubkey'] = b2x(self.selected_address_info['pubkey'])
		
		return retaddy, retbal
	
	 # **decorator functions ****************************************************************************************
	def address_required(func):
		def validate_and_call(*args, **kwargs):
			if not args[0].selected_address:
				print('I can\'t do that until you choose an active address...\n')
				args[0].choose_address()
			return func(*args, **kwargs)
		return validate_and_call
	
	def unlocked_wallet(func):
		def ensure_unlocked(*args, **kwargs):
			try:
				info = args[0].access.getinfo()
				if info['unlocked_until'] == 0:
					if not args[0].unlock_wallet():
						print('Error unlocking wallet...')
						return None
			except Exception as e:
				pass # wallet is unlocked
			
			return func(*args, **kwargs)
		
		return ensure_unlocked
	
	# **************************************************************************************************************
	def print_diagnostics(self):
		outs = 'I am attempting to speak to the bitcoin network for you...\n'
		btci = self.access.getinfo()
		outs += '\nUsing my awesome powers, I am now speaking to bitcoind v{}, which is connected to {} other nodes around the world.\n\nThe last block I have seen on the blockchain is {}.\n'.format(btci['version'], btci['connections'], btci['blocks'])
		try:
			if btci['unlocked_until'] == 0:
				outs += '\nYour local wallet is encrypted and locked. You will need to tell me the magic phrase for certain functions to succeed.'
			else:
				timeremaining = int(btci['unlocked_until']) - int(time.time())
				outs += '\nYour local wallet is encrypted, but I still remember your magic phrase for the next {} seconds, at which time it will fade from my memory.'.format(timeremaining)
			self.encrypted_wallet = True
		except KeyError as e:
			outs += "\nYour local wallet is not protected by a magic phrase. Your wish is my command."
		
		self.output(outs)
	
	def get_balance(self):
		amnt = self.access.getbalance()
		self.output('You have: {} BTC in your bitcoin coffers.'.format(self.from_satoshis(amnt)))
		return amnt
	
	# shapeshift plugin functions
	def send(self, toaddy, amount):
		self.try_unlock_wallet()
		tx = self.access.sendtoaddress(toaddy, self.to_satoshis(amount))
		self.try_lock_wallet()
		return b2lx(tx)
	
	def amount(self):
		return self.from_satoshis(self.access.getbalance())
	
	def newaddress(self):
		return self.access._call('getnewaddress', '')
	
	def shapeshift_withdrawal(self, coin, **kwargs):
		withdrawal_addy = raw_input('To which address or Let\'s Talk Bitcoin! user would you like to receive your {} to? '.format(coin.upper()))
		vret = kwargs['address_validator'](withdrawal_addy, coin)
		
		isvalid = vret['isvalid']
		while not isvalid:
			print('Checking Let\'s Talk Bitcoin! for a user by the name of {}'.format(withdrawal_addy))
			
			ltb_addy = self.get_address_by_ltb_user(withdrawal_addy)
			if not ltb_addy:
				print('Unable to locate any user by the name of {} at Let\'s Talk Bitcoin!'.format(withdrawal_addy))
				
				withdrawal_addy = raw_input('\nTo which address or Let\'s Talk Bitcoin! user would you like to receive your {} to? '.format(coin.upper()))
				vret = kwargs['address_validator'](withdrawal_addy, coin)
				isvalid = vret['isvalid']
			else:
				print('The verified LTB address for {} is {}. Setting that as the destination address.'.format(withdrawal_addy, ltb_addy))
				withdrawal_addy = ltb_addy
				vret = kwargs['address_validator'](ltb_addy, coin)
				
				isvalid = vret['isvalid']
				if not isvalid:
					print('Address for user is not a valid address for {}'.format(coin.upper()))
					withdrawal_addy = raw_input('\nTo which address or Let\'s Talk Bitcoin! user would you like to receive your {} to? '.format(coin.upper()))
					vret = kwargs['address_validator'](withdrawal_addy, coin)
					isvalid = vret['isvalid']
				
		return withdrawal_addy
		
	# ***************************	
	
	def send_btc(self):
		addy_amnt_tup = self._prompt_send_btc()
		if not addy_amnt_tup:
			return None
		else:
			toaddress, amount = addy_amnt_tup
			
		if not self.confirm_prompt('Do you really want to send {} BTC to {}?'.format(amount, toaddress), choicemsg='[y/N]: '):
			print('\naborted...')
			return None
		
		amount = self.to_satoshis(amount)
		
		self.try_unlock_wallet()
		tx = self.access.sendtoaddress(toaddress, amount)
		self.try_lock_wallet()
		
		tx = b2lx(tx)
		self.output('Sent. Transaction Hash: {}'.format(tx))
		return tx
	
	def _prompt_send_btc(self):
		toaddy = raw_input('To which address or Let\'s Talk Bitcoin! user would you like me to send BTC? ').strip()
		validaddy = self.access.validateaddress(toaddy)
		if not validaddy['isvalid']:
			print('Checking Let\'s Talk Bitcoin! for a user by the name of {}'.format(toaddy))
			ltb_addy = self.get_address_by_ltb_user(toaddy)
			if not ltb_addy:
				print('Unable to locate any user by the name of {} at Let\'s Talk Bitcoin!'.format(toaddy))
				return None
			else:
				print('The verified LTB address for {} is {}. Setting that as the destination address.'.format(toaddy, ltb_addy))
				toaddy = ltb_addy
		
		btc_amnt = self.access.getbalance()
		
		amount = raw_input('How many BTC do you wish me to send to {} (you have {} BTC available)?\n'.format(
			toaddy, self.from_satoshis(btc_amnt)
		)).strip()
		
		return toaddy, amount
	
	def sign_tx(self, utx):
		stx = self.access._call('signrawtransaction', utx)
		assert stx['complete']
		
		return stx['hex']
	
	def broadcast_tx(self, stx):
		tx = self.access._call('sendrawtransaction', stx)
		return tx
	
	@address_required
	def sign_message(self):
		message = raw_input('Please provide me with the message you would like to sign.\nMessage: ')
		
		self.try_unlock_wallet()
		tx = self.access.signmessage(self.selected_address, message)
		self.try_lock_wallet()
		
		self.output('Address: {}\nSigned: {}\nMessage: {}'.format(self.selected_address, tx, message))
		return tx
	
	def verify_message(self):
		signature = raw_input('Please provide me with the (base64 encoded) signed message: ').strip() # strip extraneous spaces
		message = raw_input('Please provide me with the unsigned, plaintext message: ')
		bitcoinaddress = raw_input('Please provide me with the address that claims to have signed the message: ').strip()
		signed = self.access.verifymessage(bitcoinaddress, signature, message)
		if signed:
			self.output('I can confirm the message was definitely signed by {}'.format(bitcoinaddress))
		else:
			self.output('The message failed verification. (double check that your input was correct)')
		return signed
		
	def import_privkey(self):
		if not self.confirm_prompt('This process will rescan your wallet, which is likely to take a long time. Are you sure that you want to continue?\n'):
			print('\naborted...')
			return None	
			
		privkey = raw_input('Please provide me with the private key you wish to import: ')
		label = raw_input('Please provide me with an optional label for this account [blank for none]: ')
		
		self.try_unlock_wallet()
		
		tx = self.access._call('importprivkey', privkey, label)
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
	
	def change_passphrase(self):
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
			return none
		
		tx = self.access.walletpassphrasechange(old_passphrase, new_passphrase)
		self.output('Successfully changed password: {}'.format(tx))
		return tx
	
	def get_new_address(self):
		existing_accounts = self.access._call('listaccounts')
		accs = ', '.join(sorted([x[0] for x in existing_accounts.iteritems() if x[0] != '']))
		
		account = raw_input('In which account should I create the address? Available accounts (leave blank for default): {} \n'.format(accs))
		newaddy = self.access.getnewaddress(account)
		self.output('I created the new address, {} in the account "{}"'.format(newaddy, account))
		return newaddy
	
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
		return active # returns a list of tuples [(address, btc balance), ...]
	
	def encrypt_wallet(self):
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
		
		if not self.confirm_prompt('Do you really want to encrypt the wallet with this magic phrase?'):
			print('\naborted')
			return None
		
		tx = self.access.encryptwallet(encrypt_passphrase)
		self.output('I successfully encrypted your wallet: {}'.format(tx))
		return tx
	
	def is_wallet_encrypted(self):
		try:
			info = self.access.getinfo()
			if 'unlocked_until' in info.keys():
				return True
			else:
				return False
		except bitcoin.rpc.JSONRPCException as e:
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
		except bitcoin.rpc.JSONRPCException as e:
			self.output('[code {}] {}'.format(e.error['code'], e.error['message']))
			return False
		
		if printsuccess:
			self.output('I have successfully unlocked your wallet for {} seconds.'.format(duration))
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
			#if info['unlocked_until'] > ensure we have enough time to sign and broadcast...
		except KeyError:
			pass # wallet is unlocked
		return True
	
	def try_lock_wallet(self, printsuccess=False, printerrors=False):
		if not self.is_wallet_encrypted():
			if printerrors:
				self.output('Your wallet is not encrypted. It\'s been unlocked this entire time!')
			return True
		
		try:
			self.access._call('walletlock')
		except Exception as e:
			print('lockwallet: {} ({})'.format(e, type(e)))
		if printsuccess:
			print('Successfully locked your wallet')
		return True
	
	def sign_and_send(self, utx):
		self.try_unlock_wallet()
		
		stx = self.sign_tx(utx)
		tx = self.broadcast_tx(stx)
		
		self.try_lock_wallet()
		
		return tx
	
	def get_address_by_ltb_user(self, user):
		try:
			import requests
			import json
		except ImportError:
			return None
		
		url = 'https://letstalkbitcoin.com/api/v1/users?search={}'.format(user)
		resp = requests.get(url)
		if int(resp.status_code) != 200:
			return None
		try:
			ret = json.loads(resp.text)
			#ltbaddy = ret['users'][0]['profile']['ltbcoin-address']['value']
			whichd = [ x for x in ret['users'] if x['username'].lower() == user.lower() ]
			if not whichd:
				return None
			
			ltbaddy = whichd[0]['profile']['ltbcoin-address']['value']
			return ltbaddy
		except Exception as e:
			return None
		