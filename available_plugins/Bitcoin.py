from wgplugins.WGPlugins import WGPlugin, WalletGenieConfig, WalletGenieImportError
from wgplugins.WGPlugins import PopupPrompt, ChoicePopup

from walletgenie import PasswordPrompt
try:
	from bitcoin.core import b2x, b2lx
	import bitcoin.rpc
except ImportError:
	raise WalletGenieImportError('Unable to import bitcoinlib -- install it with: `pip install python-bitcoinlib`')
try:
	import pyperclip
except ImportError:
	pass
import npyscreen
import json
import decimal

class BitcoinRPCProxy(bitcoin.rpc.Proxy):
	'''
	wrap all _call functionality to catch JSONRPCException and print out the error
	'''
	def _call(self, service_name, *args):
		try:
			return super(BitcoinRPCProxy, self)._call(service_name, *args)
		except bitcoin.rpc.JSONRPCException as e:
			msg = '{}'.format(e.error['message'])
			PopupPrompt(msg='{0}'.format(msg), title='RPC Error').edit()
			#npyscreen.notify_confirm(title='RPC Error', msg='{}'.format(msg))
			return False

class Bitcoin(WGPlugin):
	
	def __init__(self, *args, **kwargs):
		super(Bitcoin, self).__init__(*args, **kwargs)
		
		self.config_file = 'wgbitcoin.conf'
		self.conf_values = {
			'rpcpassword': None,
			'rpcuser': 'rpc', 'rpcssl': '0',
			'rpcport': '8332', 'rpcurl': '127.0.0.1'
		}
		
		self.main_menu = {
			'0': {'description': 'Show Network Diagnostics', 'callback': self.show_diagnostics},
			'1': {'description': 'Show Bitcoin Balance', 'callback': self.show_balance},
			'2': {'description': 'Sign a message', 'callback': self._prompt_sign_message},
			#'3': {'description': 'Verify a signed message', 'callback': self._prompt_verify_message} # enabling this makes all shortcuts call this callback function ?!
		}
		
		wgc = WalletGenieConfig()
		self.rpcd = wgc.check_load_config(self.config_file, wanted_values=self.conf_values)
		if not self.rpcd:
			npyscreen.notify_confirm('It appears that {} does not yet exist. If this is your first time running the Bitcoin plugin, you will need a config file detailing your RPC connection information'.format(self.config_file))
			if not wgc.set_from_coin_or_text(self.config_file, config_vars=self.conf_values):
				raise WalletGenieConfigurationError('Failed to set configuration file. Aborting Bitcoin plugin.')
			else:
				self.rpcd = wgc.check_load_config(self.config_file, wanted_values=self.conf_values)
				if not self.rpcd:
					raise WalletGenieConfigurationError('Could not load {}'.format(self.config_file))
		
		self.access = BitcoinRPCProxy(
			service_url='{}://{}:{}@{}:{}'.format(
				'https' if int(self.rpcd['rpcssl']) else 'http', self.rpcd['rpcuser'], self.rpcd['rpcpassword'], self.rpcd['rpcurl'], self.rpcd['rpcport']
			)
		)
	
	def show_diagnostics(self):
		outs = 'I am attempting to speak to the bitcoin network for you...\n'
		btci = self.access.getinfo()
		outs += '\n\nUsing my awesome powers, I am now speaking to bitcoind v{}, which is connected to {} other nodes around the world.\n\nThe last block I have seen on the blockchain is {}.\n'.format(btci['version'], btci['connections'], btci['blocks'])
		try:
			if btci['unlocked_until'] == 0:
				outs += '\n\nYour local wallet is encrypted and locked. You will need to tell me the magic phrase for certain functions to succeed.'
			else:
				timeremaining = int(btci['unlocked_until']) - int(time.time())
				outs += '\n\nYour local wallet is encrypted, but I still remember your magic phrase for the next {} seconds, at which time it will fade from my memory.'.format(timeremaining)
			self.encrypted_wallet = True
		except KeyError as e:
			outs += "\n\nYour local wallet is not protected by a magic phrase. Your wish is my command."
		
		self.output(outs)
	
	def show_balance(self):
		self.output('You have {} BTC in your bitcoin coffers'.format(self.from_satoshis(self.access.getbalance())))
	
	def sign_message(self, address, message):
		self.try_unlock_wallet()
		signed = self.access.signmessage(address, message)
		self.try_lock_wallet()
		return signed
	
	def _prompt_sign_message(self):
		Options = npyscreen.OptionList()
		options = Options.options
		
		addresses = self.get_wallet_addresses(allow_empty=True)
		
		options.append(npyscreen.OptionSingleChoice('Address:', choices=addresses))
		options.append(npyscreen.OptionFreeText('Message:', value=''))
		
		def validate_options(opts):
			for (var, val) in opts:
				if not val or val == '':
					npyscreen.notify_confirm('Option `{}` cannot be blank'.format(var))
					return True
		
		def opt_cancel():
			return False
		
		fsp = npyscreen.ActionFormV2(name = 'Enter Message Signing Details')
		ms = fsp.add(npyscreen.OptionListDisplay, name='Message Signing Details', values=options, scroll_exit=True, max_height=None)
		
		fsp.on_ok = lambda: validate_options([(o.get_real_name(), o.get()) for o in Options.options])
		fsp.on_cancel = lambda: opt_cancel()
		
		fsp.edit()
		
		d = {}
		for o in Options.options:
			d[o.get_real_name()] = o.get()
		
		msg = d['Message:']
		addresses = d['Address:']
		
		if msg == '' or addresses == '': # canceled
			return False 
		
		addy = addresses[0]
		
		tx = self.sign_message(addy, msg)
		if tx:
			outmsg = 'Address: {}\nSigned: {}\nMessage: {}'.format(addy, tx, msg)
			try:
				pyperclip.copy(outmsg)
				outmsg += '\n(text has been copied to the clipboard)'
			except NameError:
				outmsg += '\n(tip: `pip install pyperclip` if you want me to be able to copy this text)'
			self.output(outmsg)
	
	def _prompt_verify_message(self):
		Options = npyscreen.OptionList()
		options = Options.options
		
		addresses = self.get_wallet_addresses(allow_empty=True)
		
		options.append(npyscreen.OptionFreeText('Signature:', value=''))
		options.append(npyscreen.OptionFreeText('Message:', value=''))
		options.append(npyscreen.OptionFreeText('Address:', value=''))
		
		def validate_options(opts):
			for (var, val) in opts:
				if not val or val == '':
					npyscreen.notify_confirm('Option `{}` cannot be blank'.format(var))
					return True
		
		def opt_cancel():
			return False
		
		fsp = npyscreen.ActionFormV2(name = 'Enter Message Verification Details')
		ms = fsp.add(npyscreen.OptionListDisplay, name='Message Verification Details', values=options, scroll_exit=True, max_height=None)
		
		fsp.on_ok = lambda: validate_options([(o.get_real_name(), o.get()) for o in Options.options])
		fsp.on_cancel = lambda: opt_cancel()
		
		fsp.edit()
		
		d = {}
		for o in Options.options:
			d[o.get_real_name()] = o.get()
		
		signature = d['Signature:']
		message = d['Message:']
		address = d['Address:']
		
		if signature == '' or message == '' or address == '': # canceled
			return False 
		
		signed = self.access.verifymessage(address, signature, message)
		if signed:
			self.output('I can confirm the message was definitely signed by {}'.format(address))
		else:
			self.output('The message failed verification. (double check that your input was correct)')
	
	def get_wallet_addresses(self, allow_empty=False, return_balances=False):
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
		
		# listaddressgroupings() does not return all addresses in the wallet
		# iterate through the accounts and collect all of them
		existing_accounts = self.access._call('listaccounts')
		accs = [ x[0] for x in existing_accounts.items() ]
		
		addys_by_acc = []
		for a in accs:
			l = self.access._call('getaddressesbyaccount', a)
			for x in l:
				addys_by_acc.append(x)
		
		for aa in addys_by_acc:
			if aa not in just_addresses and allow_empty:
				active.append( (aa, 0.0) )
				
		if return_balances:
			return active # returns a list of tuples [(address, btc balance), ...]
		else:
			return [a[0] for a in active]
	
	def is_wallet_encrypted(self):
		info = self.access.getinfo()
		if 'unlocked_until' in info.keys():
			return True
		else:
			return False
	
	def unlock_wallet(self, duration=300):
		pp = PasswordPrompt()
		pp.edit()
		pwd = pp.pwd.value
		
		isvalid = self.access.walletpassphrase(pwd, int(duration))
		if isvalid == False: # isvalid == None means success, False failure
			return False
		
		return True
	
	def try_unlock_wallet(self, ask_until_correct=True):
		try:
			info = self.access.getinfo()
			if info['unlocked_until'] == 0:
				if not self.unlock_wallet():
					if ask_until_correct:
						correct = False
						while not correct:
							correct = self.unlock_wallet()
					else:
						return False
		except KeyError:
			pass # wallet is unlocked
		return True
	
	def try_lock_wallet(self):
		if not self.is_wallet_encrypted():
			return True
		try:
			self.access._call('walletlock')
		except Exception as e:
			self.output('There was an error locking your wallet: {}')
			return False
		return True
	