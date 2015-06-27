import os
import sys
import glob
try:
	import ConfigParser
except ImportError:
	try:
		import configparser as ConfigParser
	except ImportError:
		print('Unable to import ConfigParser, install it with: `pip install ConfigParser`')
		sys.exit(0)

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
	
	def __init__(self, config_dir='{}/'.format(USER_CONFIG_DIR)):
		self.config_dir = config_dir
	
	def read_coin_config(self, config_file, header='fakesec'):
		scp = ConfigParser.SafeConfigParser()
		scp.readfp(FakeSecHead(open(config_file)))
		
		confitems = scp.items(header)
		retd = {}
		
		for key, value in confitems:
			retd[key] = value
		
		return retd
	
	def check_and_load(self, config_file, config_dir='{}/'.format(USER_CONFIG_DIR), default_conf_loc=None, required_values=[], default_values={}, silent=True):
		configs_full = self.checkForConfigs(config_dir)
		configs = [ cf[cf.rfind('/') + 1 : ] for cf in configs_full ] #strip out the full path and just get conf file names
		if not configs:
			if not silent:
				print('No configuration files')
			return None
			
		if config_file[ config_file.rfind('/') + 1 :  ] not in configs:
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
			choice = self.prompt(['Enter values manually', 'Choose coin configuration to read from'], title='How do you want to enter credentials?\n', choicemsg='(number)-> ')
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
						for var, default_value in config_vars:
							if var not in d.keys() and default_value:
								d[var] = default_value
					
					self.setConfig(out_config, d)
				except IOError as e:
					print('Error reading configuration file {}: {}\n'.format(filepath, e))
					filepath = None
		except KeyboardInterrupt:
			return None
		return True
	
	def checkForConfigs(self, config_dir):
		configs = []
		for f in glob.glob('{}*.conf'.format( '{}/'.format(config_dir) if config_dir[-1] != '/' else config_dir )):
			configs.append(f)
		return configs
	
	def setConfig(self, config_file, infod, config_dir='{}/'.format(USER_CONFIG_DIR)):
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