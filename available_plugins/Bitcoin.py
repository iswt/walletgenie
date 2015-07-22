from wgplugins.WGPlugins import WGPluginForm, WalletGenieConfig, WalletGenieImportError
from wgplugins.WGPlugins import DefaultPluginForm, PluginForm
from lib.prompts import PopupPrompt, ChoicePopup, PasswordPrompt, ChoiceOptionPrompt
from lib.util import get_address_by_netki_wallet, get_address_by_ltb_user
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

from wgplugins.WGPlugins import PluginForm
class PeerViewForm(PluginForm, npyscreen.FormMutt):
#class PeerViewForm(PluginFormMutt):
	
	def create(self):
		super(PeerViewForm, self).create()
		#self.wStatus1.value = 'Bitcoin'

class WalletViewForm(PluginForm, npyscreen.ActionFormV2):
	pass

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

class Bitcoin(DefaultPluginForm):
	
	coin_name = 'Bitcoin'
	coin_symbol = 'BTC'
	
	def __init__(self, *args, **kwargs):
		super(Bitcoin, self).__init__(*args, **kwargs)
		
		self.config_file = 'wgbitcoin.conf'
		self.conf_values = {
			'rpcpassword': None,
			'rpcuser': 'rpc', 'rpcssl': '0',
			'rpcport': '8332', 'rpcurl': '127.0.0.1'
		}
		
		self.main_menu = {
			'1': {'description': 'Show Network Diagnostics', 'callback': self.show_diagnostics},
			'2': {'description': 'Show Bitcoin Balance', 'callback': self.show_balance},
			'3': {'description': 'Sign a message', 'callback': self._prompt_sign_message},
			'4': {'description': 'Verify a signed message', 'callback': self._prompt_verify_message},
			'5': {'description': 'Import a new private key', 'callback': self._prompt_import_privkey},
			'6': {'description': 'Import a new watch-only address', 'callback': self._prompt_import_watch_address},
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
	
	def create(self):
		super(Bitcoin, self).create()
		#self.bottom_commands = [('Wallet', 0), ('Peers', 0)]
		self.bottom_commands = [('Foo', 0), ('Bar', 0), ('Baz', 0)]
		
		self.register_form_func('p', self.on_peer_view)
		self.register_form_func('w', self.on_wallet_view)
		
		#self.wStatus1.value = ' | Bitcoin plugin'
		#self.wStatus1.value = 'My test app'
		
		#self.add(npyscreen.TitleFixedText, name='ok', value='Test')
		#self.add_widget(npyscreen.TitleFixedText, name='ok', value='Test')
		#self.add(npyscreen.TitleFixedText, name='ok2', value='Test2', hidden=True)
		#self.add(npyscreen.TitleFixedText, name='ok3', value='Test3')
		
		#self.add_views(self, {
		#	'w': (self.on_wallet_view, None),
		#	'p': (self.on_peer_view, None),
		#})
		
		#self.add_handlers({'c': self.activate_console})
	
	def on_peer_view(self):
		f =PeerViewForm()
		f.wStatus1.value = 'Bitcoin form'
		return f
	
	def on_wallet_view(self):
		f = WalletViewForm()
		return f
	
	def show_diagnostics(self, *args):
		outs = 'I am attempting to speak to the bitcoin network for you...\n'
		btci = self.access.getinfo()
		
		version_str = '{}.{}.{}.{}'.format(
			btci['version'] / 1000000,
			(btci['version'] % 1000000) / 10000,
			(btci['version'] % 10000) / 100,
			btci['version'] % 100
		)
		outs += '\n\nUsing my awesome powers, I am now speaking to bitcoind v{}, which is connected to {} other nodes around the world.\n\nThe last block I have seen on the blockchain is {}.\n'.format(version_str, btci['connections'], btci['blocks'])
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
	
	def show_balance(self, *args):
		self.output('You have {} BTC in your bitcoin coffers'.format(self.from_satoshis(self.access.getbalance())))
	
	def sign_tx(self, utx):
		stx = self.access._call('signrawtransaction', utx)
		if not stx or not stx['complete']:
			return None
		return stx['hex']
	
	def broadcast_tx(self, stx):
		tx = self.access._call('sendrawtransaction', stx)
		return tx
	
	def sign_and_broadcast(self, utx):
		self.try_unlock_wallet()
		stx = self.sign_tx(utx)
		if not stx:
			return None
		tx = self.broadcast_tx(stx)
		if not tx:
			return None
		return tx
	
	def sign_message(self, address, message):
		self.try_unlock_wallet()
		signed = self.access.signmessage(address, message)
		self.try_lock_wallet()
		return signed
	
	def _prompt_sign_message(self, *args):
		addresses = self.get_wallet_addresses(allow_empty=True)
		cop = ChoiceOptionPrompt(disp_name = 'Message Signing Details', prompt_options = [
			{'widget': npyscreen.OptionFreeText, 'args': ['Message:'], 'kwargs': {'value': ''}},
			{'widget': npyscreen.OptionSingleChoice, 'args': ['Address:'], 'kwargs': {'choices': addresses}}
		])
		cop.edit()
		d = cop.get_options()
		msg = d['Message:']
		addresses = d['Address:']
		
		if cop.cancelled:
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
			self.output(outmsg, title='Signed message')
	
	def _prompt_verify_message(self, *args):
		def validaddy(addy):
			if self.is_address_valid(addy):
				return True
			else:
				return '{} is not a valid Bitcoin address'.format(addy)
		
		cop = ChoiceOptionPrompt(disp_name = 'Message Verification Details', prompt_options = [
			{'widget': npyscreen.OptionFreeText, 'args': ['Signature:'], 'kwargs': {'value': ''}},
			{'widget': npyscreen.OptionFreeText, 'args': ['Message:'], 'kwargs': {'value': ''}},
			{'widget': npyscreen.OptionFreeText, 'args': ['Address:'], 'kwargs': {'value': ''}, 'validator': validaddy},
		])
		cop.edit()
		d = cop.get_options()
		
		signature = d['Signature:']
		message = d['Message:']
		address = d['Address:']
		
		if cop.cancelled:
			return False 
		
		signed = self.access.verifymessage(address, signature, message)
		if signed:
			self.output('I can confirm the message was definitely signed by {}'.format(address), title='Successful verification')
		else:
			self.output('The message failed verification. (double check that your input was correct)', title='Message failed verification')
	
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
	
	def _prompt_import_privkey(self, *args):
		if not npyscreen.notify_yes_no('This process will rescan your wallet, which is likely to take a (potentially very) long time. Are you sure that you want to continue?'):
			return False
		
		cop = ChoiceOptionPrompt(disp_name = 'Import new private key', allow_blank_strings = True, prompt_options = [
			{'widget': npyscreen.OptionFreeText, 'args': ['privkey:'], 'kwargs': {'value': ''}},
			{'widget': npyscreen.OptionFreeText, 'args': ['label:'], 'kwargs': {'value': ''}}
		])
		cop.edit()
		d = cop.get_options()
		privkey = d['privkey:']
		label = d['label:']
		
		self.try_unlock_wallet()
		suc = self.access._call('importprivkey', privkey, label)
		self.try_lock_wallet()
		
		if suc:
			self.output('I have successfully imported your private key: {}'.format(suc))
		else:
			return None
	
	def _prompt_import_watch_address(self, *args):
		if not npyscreen.notify_yes_no('This process will rescan your wallet, which is likely to take a (potentially very) long time. Are you sure that you want to continue?'):
			return False
		
		def validaddy(addy):
			if self.is_address_valid(addy):
				return True
			else:
				return '{} is not a valid Bitcoin address'.format(addy)
		
		cop = ChoiceOptionPrompt(disp_name = 'Import new watch address', allow_blank_strings = True, prompt_options = [
			{'widget': npyscreen.OptionFreeText, 'args': ['address:'], 'kwargs': {'value': ''}, 'validator': validaddy},
			{'widget': npyscreen.OptionFreeText, 'args': ['label:'], 'kwargs': {'value': ''}}
		])
		cop.edit()
		d = cop.get_options()
		addr = d['address:']
		label = d['label:']
		
		ret = self.access.importaddress(addr, label=label, rescan=True)
		self.output('I have successfully imported the watch-only address {}'.format(addr))
		return ret
		
	
	def is_address_valid(self, address):
		valid = self.access.validateaddress(address)
		if not valid['isvalid']:
			return False
		return True
	
	def is_wallet_encrypted(self):
		info = self.access.getinfo()
		if 'unlocked_until' in info.keys():
			return True
		else:
			return False
	
	def import_privkey(self, privkey, label=''):
		self.try_unlock_wallet()
		imported = self.access._call('importprivkey', privkey, label)
		self.try_lock_wallet()
		return imported
	
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
	