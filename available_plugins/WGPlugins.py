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
	from StringIO import StringIO
except ImportError:
	from io import StringIO
import itertools
import decimal
import npyscreen
import glob

from walletgenie import USER_CONFIG_DIR, PLUGINS_DIR
from walletgenie import PopupPrompt, ChoicePopup

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
	
	def on_plugin_update(self, plugins, loaded_plugins, active_plugin):
		self.available_plugins = plugins
		self.active_plugins = loaded_plugins
		self.active_plugin = active_plugin
	
	def output(self, message, title='Output'):
		#PopupPrompt(msg=message).edit()
		npyscreen.notify_confirm(message, title=title, wide=True)
	
	def to_satoshis(self, num):
		return int( decimal.Decimal(num) * decimal.Decimal(1e8) )
	
	def from_satoshis(self, num):
		return decimal.Decimal(num) / decimal.Decimal(1e8)
		
	def formatted(self, f):
		return format(decimal.Decimal(f), ',.8f').rstrip('0').rstrip('.')
	
class WalletGenieImportError(Exception):
	def __init__(self, message):
		super(WalletGenieImportError, self).__init__(message)

class WalletGenieConfigurationError(Exception):
	def __init__(self, message):
		super(WalletGenieConfigurationError, self).__init__(message)

class WalletGenieConfigParser(ConfigParser.SafeConfigParser, object):
	
	def __init__(self, defaults=None):
		super(WalletGenieConfigParser, self).__init__(defaults)
	
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

class WalletGenieConfig(object):
	def __init__(self, config_dir=USER_CONFIG_DIR):
		self.config_dir = config_dir
	
	def read_coin_config(self, conf, header='WGDefault'):
		scp = ConfigParser.SafeConfigParser()
		try:
			scp.readfp(open(conf))
		except Exception as e:
			#npyscreen.notify_confirm('readfp exception: {} ({})'.format(e, type(e)))
			
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
	
	def set_from_coin_or_text(self, conf, default_conf_loc=None, coin_conf_header='WGDefault', config_vars=None):
		filepath = None
		try:
			prompt_disp = 'Read from coin configuration file'
			if default_conf_loc:
				if '/' in default_conf_loc or '\\' in default_conf_loc:
					prompt_disp = 'Read from {}'.format(os.path.strip(default_conf_loc)[1])
				else:
					prompt_disp = default_conf_loc
			
			cp = ChoicePopup(choices=['Enter values manually', prompt_disp], name='Select an option')
			cp.edit()
			if cp.selectedid == 0:
				if not config_vars:
					return False
				
				Options = npyscreen.OptionList()
				options = Options.options
				for var, default_value in config_vars.items():
					# TODO: give plugins the option of specifying their own widget options
					options.append(
						npyscreen.OptionFreeText(var, value=('' if not default_value else default_value), default=('' if not default_value else default_value))
					)
				
				def validate_options(opts):
					#npyscreen.notify_confirm('{}'.format(opts))
					for (var, val) in opts:
						if not val or val == '':
							npyscreen.notify_confirm('Config option `{}` cannot be blank'.format(var))
							return True
				
				def reset_options(parent, opts):
					for o in opts:
						o.value = o.default
					parent.display() # update the values on the screen
					return True
				
				fsp = npyscreen.ActionFormV2(name = 'Enter configuration details')
				ms = fsp.add(npyscreen.OptionListDisplay, name='config options', values=options, scroll_exit=True, max_height=None)
				
				fsp.on_ok = lambda: validate_options([(o.get_real_name(), o.get()) for o in Options.options])
				fsp.on_cancel = lambda: reset_options(fsp, Options.options)
				
				fsp.edit()
				
				outd = {}
				for o in Options.options:
					outd[o.get_real_name()] = o.get()
					#npyscreen.notify_confirm('o.get(): {}\no.realname(): {}\no.default: {}\n'.format(o.get(), o.get_real_name(), o.default))
				
				self.set_config(conf, outd)
			
			else:
				fsp = None
				while not fsp:
					fsp = npyscreen.selectFile(must_exist=True, confirm_if_exists=False)#starting_value=default_conf_loc
					try:
						d = self.read_coin_config(fsp, header=coin_conf_header)
						if config_vars:
							outd = {}
							for var, default_value in config_vars.items():
								if var not in d.keys() and default_value is not None:
									d[var] = default_value
								try:
									outd[var] = d[var]
								except KeyError as e:
									PopupPrompt(msg='{}'.format(e), title='Error reading config file').edit()
									fsp = None
						else:
							outd = d
						
						self.set_config(conf, outd)
					except IOError as e:
						PopupPrompt(msg='{}'.format(e), title='Error reading {}'.format(fsp))
						print('Error reading configuration file {}: {}\n'.format(filepath, e))
						fsp = None
			
			#fsp = npyscreen.FileSelector(must_exist=True, confirm_if_exists=False)
			#fsp.edit()
			#fsp.wCommand.value
			
		except KeyboardInterrupt:
			return None
		return True
	
	def set_config(self, conf, infod):
		try:
			wgcp = WalletGenieConfigParser()
			conf_to_write = os.path.join(self.config_dir, conf)
			with open(conf_to_write, 'r') as s:
				if sys.version_info[0] >= 3:
					lines = itertools.chain(('[WGDefault]',), s)
					wgcp.read_file(lines)
				else:
					f = StringIO("[WGDefault]\n" + s.read())
					wgcp.readfp(f)
			for key, val in infod.items():
				try:
					wgcp.set('WGDefault', key, str(val))
				except Exception as e:
					PopupPrompt(msg='Exception setting configuration file: {}'.format(e)).edit()
			wgcp.write(open(conf_to_write, 'w+'))
		except IOError as e:
			npyscreen.notify_confirm('IOError writing {}: {}'.format(conf, e))
			return None
		npyscreen.notify_confirm('Successfully wrote {} at {}'.format(conf, self.config_dir))