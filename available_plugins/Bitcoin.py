from wgplugins.WGPlugins import WGPlugin, WalletGenieConfig, WalletGenieImportError
try:
	from bitcoin.core import b2x, b2lx
	import bitcoin.rpc
except ImportError:
	raise WalletGenieImportError('Unable to import bitcoinlib -- install it with: `pip install python-bitcoinlib`')
import npyscreen
import json
import decimal

class Bitcoin(WGPlugin):
	
	def __init__(self, *args, **kwargs):
		super(Bitcoin, self).__init__(*args, **kwargs)
		
		self.config_file = 'wgbitcoin.conf'
		self.conf_values = {
			'rpcpassword': None,
			'rpcuser': 'rpc', 'rpcssl': 0,
			'rpcport': '8332', 'rpcurl': '127.0.0.1'
		}
		
		wgc = WalletGenieConfig()
		self.rpcd = wgc.check_load_config(self.config_file, wanted_values=self.conf_values)
		#if self.rpcd:
		npyscreen.notify_confirm('{}'.format(self.rpcd))