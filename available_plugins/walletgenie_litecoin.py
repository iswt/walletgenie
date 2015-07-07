import sys

from walletgenie_plugins import BasePlugin, BasePluginCoin
from walletgenie_plugins import WalletGenieConfig, WalletGenieConfigurationError, WalletGenieImportError
try:
	from bitcoinrpc.authproxy import AuthServiceProxy
except ImportError:
	print('Unable to import bitcoinrpc, install it with: `pip install python-bitcoinrpc`')
	sys.exit(0)

class Litecoin(BasePluginCoin):
	
	coin_name = 'LTC' # shapeshift plugin
	
	def __init__(self, *args, **kwargs):
		self.config_file = 'wglitecoin.conf'
		self.required_config_vars = ['rpcpassword']
		self.default_config_vars = {'rpcssl': 0, 'rpcuser': 'rpc', 'rpcport': 9332, 'rpcurl': '127.0.0.1'}
		
		self.main_menu = {
			0: {
				'description': 'Genie, are you currently able to speak to the litecoin network?',
				'insert_before': '\n--- litecoin Functions ---\n',
				'callback': lambda: self._print_diagnostics('litecoin')
			},
			1: {
				'description': 'Genie, how many bitcoin do I have in my coffers?',
				'callback': lambda: self._prompt_get_balance('LTC')
			},
			2: {
				'description': 'Genie, I wish to send litecoin to an address.',
				'callback': lambda: self._prompt_send('LTC')
			},
			3: {
				'description': 'Genie, I wish to sign a message from an address I control.',
				'callback': self._prompt_sign_message
			},
			4: {
				'description': 'Genie, I wish to verify the origin of this signed message.',
				'callback': self._prompt_verify_message
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
				'description': 'Genie, I wish to create a new address into which I can receive more litecoin.',
				'callback': self._prompt_get_new_address
			},
			8: {
				'description': 'Genie, I wish to unlock my wallet so you can perform some transactions on my behalf.',
				'callback': lambda printsuccess=True, printerrors=True, modify_duration=True: self.unlock_wallet(printsuccess, printerrors, modify_duration)
			},
			9: {
				'description': 'Genie, I wish to lock my wallet to keep my litecoin safe from thieves.',
				'callback': lambda printsuccess=True, printerrors=True: self.try_lock_wallet(printsuccess, printerrors)
			},
			10: {
				'description': 'Genie, I wish to protect my bitcoin coffers with a magic phrase. Keep my bitcoin safe from thieves. TNO.',
				'callback': self._prompt_encrypt_wallet
			},
			11: {
				'description': 'Genie, I wish to change my magic phrase. There are scoundrels all around.',
				'callback': self._prompt_change_passphrase
			}
		}
		
		wgc = WalletGenieConfig()
		self.rpcd = wgc.check_and_load(
			self.config_file, required_values=self.required_config_vars, 		
			default_values=self.default_config_vars
		)
		if self.rpcd is None:
			print('\nIt appears that {} does not yet exist. If this is your first time running the walletgenie_litecoin plugin, you will need a configuration file detailing your RPC Connection information.\n'.format(self.config_file))
			confvars = [(x, None) for x in self.required_config_vars if x not in self.default_config_vars.keys()]
			confvars += self.default_config_vars.items()
			wgc.set_from_coin_or_text(
				self.config_file, default_conf_loc='/home/litecoin/.litecoin/litecoin.conf',
				config_vars=confvars
			)
			self.rpcd = wgc.check_and_load(self.config_file, required_values=self.required_config_vars, default_values=self.default_config_vars, silent=False)
			if not self.rpcd:
				print('\n\nUnable to load configuration file: {}\nAborting Litecoin plugin\n'.format(self.config_file))
				raise WalletGenieConfigurationError(self.config_file)
			
		super(Litecoin, self).__init__(
			'{}://{}:{}@{}:{}'.format(
				'https' if int(self.rpcd['rpcssl']) else 'http', self.rpcd['rpcuser'], self.rpcd['rpcpassword'], self.rpcd['rpcurl'], self.rpcd['rpcport']
			),
			*args, **kwargs
		)
	
	# shapeshift plugin functions
	def send(self, toaddy, amount):
		return self.sendto(toaddy, float(amount))
	
	def amount(self):
		return self.get_balance()
	
	def newaddress(self):
		return self.getnewaddress(label='shapeshift')