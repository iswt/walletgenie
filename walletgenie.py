#!/usr/bin/env python
import sys
import os
from os.path import expanduser
USER_HOME = expanduser('~')

if 'HOME' in os.environ:
	USER_DIR = os.path.join(USER_HOME, '.walletgenie')
elif 'APPDATA' in os.environ or 'LOCALAPPDATA' in os.environ:
	USER_DIR = os.path.join(os.environ['APPDATA'], 'Walletgenie')
	
	# We're on windows, set the os.symlink appropriately
	# see: http://stackoverflow.com/a/28382515
	def symlink_ms(source, link_name):
		import ctypes
		csl = ctypes.windll.kernel32.CreateSymbolicLinkW
		csl.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32)
		csl.restype = ctypes.c_ubyte
		flags = 1 if os.path.isdir(source) else 0
		try:
			if csl(link_name, source.replace('/', '\\'), flags) == 0:
				raise ctypes.WinError()
		except:
			pass
	os.symlink = symlink_ms
else:
	print('No home directory found in environment variables')
	sys.exit(0)

USER_CONFIG_DIR = os.path.join(USER_DIR, 'config')
AVAILABLE_PLUGINS_DIR = os.path.join(os.path.dirname(__file__), 'available_plugins')
PLUGINS_DIR = os.path.join(os.path.dirname(__file__), 'walletgenie_plugins')
CORE_PLUGINS_DIR = os.path.join(os.path.dirname(__file__), 'core_plugins')

import time
import datetime
import pkgutil

import imp

class WalletGenie():
	
	_version = '0.15'
	welcome_msg = '* Hello, I am the Wallet Genie v{} *'.format(_version)
	
	plugins = None
	active_plugin = None # which plugin (e.g. key in the loaded_plugins dictionary) is currently active
	loaded_plugins = {} # loaded_plugins[plugin_name] = {name, loader, plugin_class}
	
	def __init__(self):
		print('\n{0}\n{1}\n{0}\n'.format('*'*len(self.welcome_msg), self.welcome_msg))
		#create user dirrectory if it does not already exist
		#see: http://stackoverflow.com/a/273227
		try:
			if not os.path.exists(USER_CONFIG_DIR):
				os.makedirs(USER_CONFIG_DIR)
		except Exception as e:
			pass
		
		# load core plugins
		pluginpath = CORE_PLUGINS_DIR
		plugins = self.find_plugins(plugin_dir = pluginpath)
		
		self.core_plugins = {}
		if plugins:
			for plugin in plugins:
				plugin_class = plugin.title()
				self.core_plugins[plugin] = {
					'loader': self.import_plugin(plugin, path=CORE_PLUGINS_DIR)
				}
				loaded_class = getattr(self.core_plugins[plugin]['loader'], plugin_class)
				self.core_plugins[plugin]['plugin_class'] = loaded_class()
		
		# load coin plugins
		pluginpath = PLUGINS_DIR
		self.plugins = sorted(self.find_plugins(plugin_dir = pluginpath))
		if len(self.plugins) == 0:
			available_plugin_path = AVAILABLE_PLUGINS_DIR
			aplugins = sorted(self.find_plugins(plugin_dir = available_plugin_path))
			
			invalid = True
			while invalid:
				try:
					print('Available plugins:\n')
					for i, ap in enumerate(aplugins):
						print('{0: >2} -> {1}'.format(i + 1, ap))
					choice = raw_input('\nWhich plugin(s) do you wish to enable? (comma separated numbers): ').replace(' ', '')
					
					if ',' in choice:
						choices = choice.split(',')
						invalid = False
						for c in choices:
							if int(c) - 1 not in range(0, len(aplugins)):
								invalid = True
					else:
						invalid = int(choice) - 1 not in range(0, len(aplugins))
						if not invalid:
							choices = [choice]
				except Exception as e:
					print('Invalid number: {}'.format(e))
					invalid = True
			
			for choice in choices:
				src = '{}/{}.py'.format(
					os.path.relpath(AVAILABLE_PLUGINS_DIR, PLUGINS_DIR),
					aplugins[int(choice) - 1]
				)
				dest = '{}/{}.py'.format(PLUGINS_DIR, aplugins[int(choice) - 1])
				os.symlink(src, dest)
			# load the new plugins
			self.plugins = sorted(self.find_plugins(plugin_dir = PLUGINS_DIR))
			for p in self.plugins:
				self.load_plugin(p, path='walletgenie_plugins', use_imp=False)
		else:
			for p in self.plugins:
				self.load_plugin(p, path='walletgenie_plugins', use_imp=False)
		
		available_plugins = sorted(self.find_plugins(plugin_dir = AVAILABLE_PLUGINS_DIR))
		loaded_p = [p[1]['name'] for p in self.loaded_plugins.iteritems()]
		self.unloaded_plugins = []
		for ap in available_plugins:
			if ap not in loaded_p:
				self.unloaded_plugins.append(ap)
		
	def import_plugin(self, plugin, path=PLUGINS_DIR, use_imp=True):
		if not use_imp:
			return __import__('{}.{}'.format(path, plugin), fromlist=[plugin])
		else:
			try:
				return imp.load_source(plugin, '{}/{}.py'.format(path, plugin))
			except IOError as e:
				print('\Enrror opening {}/{}: {}\n'.format(path, plugin, e))
				sys.exit(0)
	
	def find_plugins(self, plugin_dir=PLUGINS_DIR):
		modules = pkgutil.iter_modules(path=[plugin_dir])
		ret_modules = []
		for loader, mod_name, ispkg in modules:
			if mod_name not in sys.modules and mod_name not in ['walletgenie_plugins']:
				ret_modules.append(mod_name)
		return ret_modules
	
	def get_plugin_class(self, plugin):
		words = plugin.split('_')[1 : ]
		ret = ''
		for w in words:
			ret += w.title()
		return ret
	
	def prompt(self, what, title=None, choicemsg='What is thy bidding, o\'Master of the wallet? ', errormsg='invalid choice...'):
		return prompt(what, title=title, choicemsg=choicemsg, errormsg=errormsg)
	
	def prompt_for_main_menu(self, choices, title=None, topmenu=None, choicemsg='What is thy bidding, o\'Master of the wallet? ', errormsg='invalid choice...'):
		if not choices:
			return None
		
		if title:
			print('{}'.format(title))
		
		if topmenu:
			totalstr = '|  {}'.format(topmenu[0][1]['description'])
			for tup in topmenu[1 : ]:
				totalstr += '  |  {}'.format(tup[1]['description'])
			totalstr = totalstr.replace('\n', '')
			totalstr += '  |'
			
			print('{0}\n{1}\n{0}'.format('-'*len(totalstr), totalstr))
			
		choice = None
		for i, (stuff, stuffd) in enumerate(choices):
			if 'insert_before' in stuffd.keys():
				print(stuffd['insert_before'])
			print('{0: >2} -> {1}'.format(i + 1, stuff))
		
		while choice is None:
			choice = raw_input('\n{}'.format(choicemsg))
			try:
				if choice.lower() not in [str(tup[0]).lower() for tup in topmenu]:
					if int(choice) not in range(1, len(choices) + 1):
						print(errormsg)
						choice = None
					else:
						return int(choice) - 1
				else:
					return choice
			except:
				print(errormsg)
				choice = None
	
	def prompt_plugin_choice(self):
		if not self.plugins:
			return None
		
		if len(self.plugins) == 1: # automatically prompt to choose the only available plugin
			if self.plugins[0] in self.loaded_plugins.keys():
				print('Only one plugin is available, and it is already loaded. You cannot load the same plugin multiple times.\n')
				return None
			else:
				print('Only one plugin, `{}`, is available for loading. Loading it now...\n'.format(self.plugins[0]))
				choice = 0
		else:
			diff = [(x, 'Load `{}` plugin'.format(x)) for x in self.plugins if x not in self.loaded_plugins.keys()]
			if not diff:
				print('\nI have found {} plugins, but they are all already loaded'.format(len(self.plugins)))
				return None
				
			disp = [x[1] for x in diff]
			choice = self.prompt(disp, title='I have found {} plugins. Which would you like to use?\n'.format(len(disp)))
			if diff[choice][0] in self.loaded_plugins.keys(): # plugin has already been loaded
				print('Error, cannot load the same plugin multiple times: {}'.format(self.plugins[choice]))
				return None
			
		self.load_plugin(diff[choice][0])
		
	def load_plugin(self, plugin, path=PLUGINS_DIR, use_imp=True):
		loader = self.import_plugin(plugin, path=path, use_imp=use_imp) 
		
		# instantiate the new class
		classname = self.get_plugin_class(plugin)
		loaded_class = getattr(loader, classname)
		try:
			plug = loaded_class(self.plugins, self.loaded_plugins, self.active_plugin, self.load_plugin)
		except Exception as e:
			print('Error initiating {}: [{}] {}'.format(plugin, type(e), e))
			return None
			
		self.active_plugin = plugin
		self.loaded_plugins[plugin] = { 
			'name': plugin, 
			'loader': loader,
			'plugin_class': plug
		}
		
		print('Successfully loaded {}'.format(plugin))
		self.update_plugins()
	
	def update_plugins(self):
		for plugin, plugind in self.loaded_plugins.iteritems():
			if 'plugin_class' in plugind.keys():
				plugind['plugin_class'].on_plugin_update(self.plugins, self.loaded_plugins, self.active_plugin)
		
		for plugin, plugind in self.core_plugins.iteritems():
			if 'plugin_class' in plugind.keys():
				plugind['plugin_class'].on_plugin_update(self.plugins, self.loaded_plugins, self.active_plugin)
	
	def enable_plugin(self):
		if not self.unloaded_plugins:
			return False
			
		plugins_to_load = []
		if len(self.unloaded_plugins) > 1:
			disp = self.unloaded_plugins + ['Enable them all!']
			choice = self.prompt(self.unloaded_plugins, title='which plugin would you like to enable?', choicemsg='Which plugin? ')
			if choice == len(disp) - 1:
				plugins_to_load = self.unloaded_plugins
			else:
				plugins_to_load = [self.unloaded_plugins[choice]]
		else:
			plugins_to_load = [self.unloaded_plugins[0]]
		
		for p in plugins_to_load:
			src = '{}/{}.py'.format(
				os.path.relpath(AVAILABLE_PLUGINS_DIR, PLUGINS_DIR),
				p
			)
			dest = '{}/{}.py'.format(PLUGINS_DIR, p)
			os.symlink(src, dest)
		
		self.plugins = sorted(self.find_plugins(plugin_dir = PLUGINS_DIR))
		for p in plugins_to_load:
			self.load_plugin(p, path='walletgenie_plugins', use_imp=False)
		
		self.unloaded_plugins = [p for p in self.unloaded_plugins if p not in plugins_to_load]
	
	def switch_plugin(self, promptall=False, print_warnings=True):
		if promptall:
			plugs = self.loaded_plugins.keys()
		else:
			plugs = [x for x in self.loaded_plugins.keys() if x != self.active_plugin]
		
		if not plugs:
			print('No other plugins are available (loaded).')
			return False
		
		plugs = sorted(plugs)
		if len(plugs) == 1:
			if print_warnings:
				print('Only 1 other plugin is available, switching to {}'.format(plugs[0]))
			self.active_plugin = plugs[0]
		else:
			disp_plugs = [p[p.rfind('_')+1:] if '_' in p else p for p in plugs] #this works??
			choice = self.prompt(disp_plugs, title='\nChoose a plugin\n', choicemsg='Which plugin? ')
			self.active_plugin = plugs[choice]
		
		self.update_plugins()
	
	def prompt_main_menu(self):
		if not self.active_plugin:
			print('No plugin selected')
			sys.exit(0)
		else:
			topmenu = [
				#('l', {'description': '(l)oad a plugin', 'callback': self.prompt_plugin_choice}), 
				('c', {
					'description': '(c)hange plugin' if len(self.loaded_plugins) > 2 else 'swit(c)h plugin', 
					'callback': self.switch_plugin
				})
			]
			
			if self.unloaded_plugins:
				if len(self.unloaded_plugins) > 1:
					desc = '(e)nable a plugin'
				else:
					desc = '(e)nable {} plugin'.format(
						self.unloaded_plugins[0][ self.unloaded_plugins[0].rfind('_') + 1 : ] if '_' in self.unloaded_plugins[0] else self.unloaded_plugins[0]
					)
				topmenu.append( ('e', {'description': desc, 'callback': self.enable_plugin}) )
			
			for plugin, plugind in self.core_plugins.iteritems():
				for tup in plugind['plugin_class'].topmenu:
					topmenu.append(tup)
			topmenu.append(('q', {'description': '(q)uit', 'callback': self.quit}))
			
			disp = [(x[1]['description'], x[1]) for x in sorted(self.loaded_plugins[self.active_plugin]['plugin_class'].main_menu.iteritems())]
			choice = self.prompt_for_main_menu(disp, title='\nMain Menu\n', topmenu=topmenu)
			
			try:
				if type(choice) is str:
					for tup in topmenu:
						if choice.lower() == tup[0].lower():
							tup[1]['callback']()
				else:
					self.loaded_plugins[self.active_plugin]['plugin_class'].main_menu[choice]['callback']()
			except KeyboardInterrupt: # user trying to ^C out of a menu choice
				print('\n\naborted... returning to main menu\n')
	
	def quit(self):
		print('cleaning up...')
		for plug, plugd in self.loaded_plugins.iteritems(): 
			plugd['plugin_class'].cleanup()
		print('goodbye master')
		sys.exit(0)
	
def prompt(what, title=None, choicemsg='What is thy bidding, o\'Master of the wallet? ', errormsg='invalid choice...'):
	if not what:
		return None
	
	if title:
		print('{}'.format(title))
	
	choice = None
	for i, stuff in enumerate(what):
		print('{0: >2} -> {1}'.format(i + 1, stuff))
	
	while choice is None:
		choice = raw_input('\n{}'.format(choicemsg))
		try:
			if int(choice) not in range(1, len(what) + 1):
				print(errormsg)
				choice = None
			else:
				return int(choice) - 1
		except:
			print(errormsg)
			choice = None

if __name__ == '__main__':
	wg = WalletGenie()
	try:
		wg.switch_plugin(promptall=True, print_warnings=False) # let the user initially choose a plugin to use
		while True:
			wg.prompt_main_menu()
	except KeyboardInterrupt:
		print('\n')
		wg.quit()