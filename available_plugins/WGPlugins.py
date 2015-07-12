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
		

import decimal
from walletgenie import USER_CONFIG_DIR

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