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
		raise ImportError('Unable to import ConfigParser, install it with: `pip install ConfigParser`')
try:
	import StringIO
except ImportError:
	from io import StringIO
import itertools
import decimal
import npyscreen
import glob

from walletgenie import USER_CONFIG_DIR, PLUGINS_DIR

class WGPlugin(object):
	
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
		return int( decimal.Decimal(num) * decimal.Decimal(1e8) )
	
	def from_satoshis(self, num):
		return decimal.Decimal(num) / decimal.Decimal(1e8)
		
	def formatted(self, f):
		return format(float(f), ',.8f').rstrip('0').rstrip('.')
	
	def on_plugin_update(self, plugins, loaded_plugins, active_plugin):
		self.available_plugins = plugins
		self.active_plugins = loaded_plugins
		self.active_plugin = active_plugin

class WalletGenieImportError(Exception):
	def __init__(self, message):
		super(WalletGenieImportError, self).__init__(message)

class WalletGenieConfigurationError(Exception):
	def __init__(self, message):
		super(WalletGenieConfigurationError, self).__init__(message)

class WalletGenieConfig(object):
	def __init__(self, config_dir=USER_CONFIG_DIR):
		self.config_dir = config_dir
	
	def read_coin_config(self, conf, header='WGDefault'):
		scp = ConfigParser.SafeConfigParser()
		try:
			scp.readfp(open(conf))
		except Exception as e:
			npyscreen.notify_confirm('readfp exception: {} ({})'.format(e, type(e)))
			
			with open(conf) as s:
				if sys.version_info[0] >= 3:
					lines = itertools.chain(('[{}]'.format(header),), s)
					scp.read_file(lines)
				else:
					f = StringIO("[WGDefault]\n" + s.read())
					scp.readfp(f)
		
		confitems = scp.items(header)
		retd = {}
		
		for key, value in confitems:
			retd[key] = value
		return retd
	
	def check_load_config(self, conf, wanted_values={}, silent=False):
		c = self.find_configs_by_dir(self.config_dir)
		if not c:
			if not silent:
				npyscreen.notify_confirm('No configuration files found')
			return None
		
		configs = [os.path.split(x)[1] for x in c]
		if not configs:
			if not silent:
				npyscreen.notify_confirm('No config files found')
			return None
		
		if conf not in configs:
			if not silent:
				npyscreen.notify_confirm('{} not found in configuration files\nconfigs: {}\n'.format(conf, configs))
			return None
		else:
			wgcp = ConfigParser.SafeConfigParser()
			with open(os.path.join(self.config_dir, conf)) as s:
				if sys.version_info[0] >= 3:
					lines = itertools.chain(('[WGDefault]',), s)
					wgcp.read_file(lines)
				else:
					f = StringIO("[WGDefault]\n" + s.read())
					wgcp.readfp(f)
			
			citems = wgcp.items('WGDefault')
			
			d = {}
			for item in citems:
				d[item[0]] = item[1]
			
			try:
				for k, v in wanted_values.items():
					if v != None:
						assert k in d.keys()
					else:
						if k not in d.keys():
							d[k] = v
			except AssertionError as e:
				if not silent:
					npyscreen.notify_confirm('Could not find proper values when reading configuration: {}'.format(str(e)))
				return None
			return d
		
	def find_configs_by_dir(self, confdir):
		spath = os.path.join(confdir, '*.conf')
		return glob.glob(spath)