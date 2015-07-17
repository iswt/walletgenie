#!/usr/bin/env python
# Copyright (c) 2015 In Satoshi We Trust LLC
# Distributed under the MIT software license, see the accompanying
# file LICENSE or http://opensource.org/licenses/MIT

import sys
import os
from os.path import expanduser
USER_HOME = expanduser('~')

if 'HOME' in os.environ:
	USER_DIR = os.path.join(USER_HOME, '.walletgenie')
elif 'APPDATA' in os.environ or 'LOCALAPPDATA' in os.environ:
	USER_DIR = os.path.join(os.environ['APPDATA'], 'Walletgenie')
else:
	print('No home directory found in environment variables')
	sys.exit(0)

filedir = os.path.dirname(os.path.realpath(__file__))
USER_CONFIG_DIR = os.path.join(USER_DIR, 'config')
PLUGINS_DIR = os.path.join(filedir, 'available_plugins')
CORE_PLUGINS_DIR = os.path.join(filedir, 'core_plugins')

import pkgutil
import time
import datetime
try:
	import npyscreen
except ImportError:
	print('Unable to import npyscreen, install it with `pip install npyscreen`')
	sys.exit(0)
import curses

import imp

class ChoiceOptionPrompt(npyscreen.ActionFormV2):
	#OK_BUTTON_BR_OFFSET = (2, 10)
	#CANCEL_BUTTON_BR_OFFSET = (2, 12)
	
	cancelled = False
	def __init__(self, *args, **kwargs):
		self.prompt_options = kwargs['prompt_options']
		for po in self.prompt_options:
			if 'kwargs' not in po:
				po['kwargs'] = {}
			if 'args' not in po:
				po['args'] = []
		
		self.disp_name = 'Enter details'
		if 'disp_name' in kwargs:
			self.disp_name = kwargs['disp_name']
			
		super(ChoiceOptionPrompt, self).__init__(*args, **kwargs)
	
	def create_control_buttons(self):
		self._add_button(
			'ok_button', 
			self.__class__.OKBUTTON_TYPE, self.__class__.OK_BUTTON_TEXT,
			0 - self.__class__.OK_BUTTON_BR_OFFSET[0],
			0 - self.__class__.OK_BUTTON_BR_OFFSET[1] - len(self.__class__.OK_BUTTON_TEXT),
			None
		)
	
	def create(self):
		self.name = self.disp_name
		
		self.Options = npyscreen.OptionList()
		self.options = self.Options.options
		
		self.validation_funcs = {}
		for po in self.prompt_options:
			opt = po['widget'](*po['args'], **po['kwargs'])
			self.options.append(opt)
			if 'validator' in po:
				self.validation_funcs[opt] = po['validator']
		
		self.option_display = self.add(npyscreen.OptionListDisplay, values=self.Options.options, scroll_exit=True, max_height=None)
		
		self.add_handlers({'^Q': self.onquit, 'q': self.onquit})
	
	def onquit(self, *args):
		self.cancelled = True
		self.exit_editing()
	
	def get_options(self):
		d = {}
		for o in self.Options.options:
			d[o.get_real_name()] = o.get()
		return d
	
	def on_ok(self):
		for o in self.Options.options:
			var = o.get_real_name()
			val = o.get()
			
			if o in self.validation_funcs:
				ret = self.validation_funcs[o](val)
				if type(ret) is str:
					npyscreen.notify_confirm(ret)
					return True
			
			if not val or val == '':
				npyscreen.notify_confirm('Option `{}` cannot be blank'.format(var))
				return True
			
		return False
	
	def on_cancel(self):
		return False

class PluginPrompterForm(npyscreen.ActionFormV2):
	OK_BUTTON_TEXT = 'OK'
	CANCEL_BUTTON_TEXT = 'Cancel'
	want_cancel_button = False
	
	def __init__(self, *args, **kwargs):
		if 'want_cancel_button' in kwargs and kwargs['want_cancel_button']:
			self.want_cancel_button = True
		super(PluginPrompterForm, self).__init__(*args, **kwargs)
	
	def create_control_buttons(self):
		self._add_button(
			'ok_button', 
			self.__class__.OKBUTTON_TYPE, self.__class__.OK_BUTTON_TEXT,
			0 - self.__class__.OK_BUTTON_BR_OFFSET[0],
			0 - self.__class__.OK_BUTTON_BR_OFFSET[1] - len(self.__class__.OK_BUTTON_TEXT),
			None
		)
		if self.want_cancel_button:
			self._add_button(
				'cancel_button', 
				self.__class__.CANCELBUTTON_TYPE, 
				self.__class__.CANCEL_BUTTON_TEXT,
				0 - self.__class__.CANCEL_BUTTON_BR_OFFSET[0],
				0 - self.__class__.CANCEL_BUTTON_BR_OFFSET[1] - len(self.__class__.CANCEL_BUTTON_TEXT),
				None
			)
	
	def create(self):
		self.how_exited_handers[npyscreen.wgwidget.EXITED_ESCAPE] = self.switch_back
		self.name = 'Plugin Selection'
		self.select = None
		self.selected = None
		
		self.add_handlers({'^Q': self.switch_back, 'q': self.switch_back})
	
	def switch_back(self, uknown=None):
		if not self.select.get_selected_objects():
			npyscreen.notify_confirm('You must select a plugin!')
		else:
			self.parentApp.switchFormPrevious()
	
	def on_ok(self):
		self.selected = self.select.get_selected_objects()
		self.switch_back()

class MinimalActionFormV2WithMenus(npyscreen.ActionFormV2WithMenus):
	def create_control_buttons(self):
		self._add_button(
			'ok_button', 
			self.__class__.OKBUTTON_TYPE, self.__class__.OK_BUTTON_TEXT,
			0 - self.__class__.OK_BUTTON_BR_OFFSET[0],
			0 - self.__class__.OK_BUTTON_BR_OFFSET[1] - len(self.__class__.OK_BUTTON_TEXT),
			None
		)

class PopupPrompt(MinimalActionFormV2WithMenus):
	DEFAULT_LINES = 12
	DEFAULT_COLUMNS = 60
	SHOW_ATX = 12
	SHOW_ATY = 3
	OK_BUTTON_TEXT = 'OK'
	
	def __init__(self, *args, **kwargs):
		self.disp_msg = ''
		if 'msg' in kwargs:
			self.disp_msg = kwargs['msg']
		self.disp_name = ''
		if 'title' in kwargs:
			self.disp_name = kwargs['title']
		super(PopupPrompt, self).__init__(*args, **kwargs)
	
	def create_control_buttons(self):
		self._add_button(
			'ok_button', 
			self.__class__.OKBUTTON_TYPE, self.__class__.OK_BUTTON_TEXT,
			0 - self.__class__.OK_BUTTON_BR_OFFSET[0],
			0 - self.__class__.OK_BUTTON_BR_OFFSET[1] - len(self.__class__.OK_BUTTON_TEXT),
			None
		)
	
	def create(self):
		self.add(npyscreen.TitleFixedText, name=self.disp_name, value=self.disp_msg, editable=False, wrap=True)
	
	def on_ok(self):
		return False
	
class PasswordPrompt(npyscreen.ActionFormV2):
	#SHOW_ATX = 20
	#SHOW_ATY = 15
	OK_BUTTON_TEXT = 'OK'
	
	def create_control_buttons(self):
		self._add_button(
			'ok_button', 
			self.__class__.OKBUTTON_TYPE, self.__class__.OK_BUTTON_TEXT,
			0 - self.__class__.OK_BUTTON_BR_OFFSET[0],
			0 - self.__class__.OK_BUTTON_BR_OFFSET[1] - len(self.__class__.OK_BUTTON_TEXT),
			None
		)
	
	def create(self):
		self.pwd = self.add(npyscreen.TitlePassword, name='Password: ')
	
	def on_ok(self):
		return False

class ChoicePopup(MinimalActionFormV2WithMenus):
	DEFAULT_LINES = 14
	DEFAULT_COLUMNS = 80
	SHOW_ATX = 10
	SHOW_ATY = 2
	OK_BUTTON_TEXT = 'OK'
	
	def __init__(self, *args, **kwargs):
		self.disp_choices = None
		if 'choices' not in kwargs:
			self.editing = False
		else:
			self.disp_choices = kwargs['choices']
		
		self.disp_name = 'Select an option'
		if 'name' in kwargs:
			self.disp_name = kwargs['name']
		
		super(ChoicePopup, self).__init__(*args, **kwargs)
	
	def create(self):
		self.select = self.add(
			npyscreen.TitleSelectOne, name=self.disp_name, 
			values=self.disp_choices,
			scroll_exit=True, width=1
		)
		self.selected = None
	
	def on_ok(self):
		objs = self.select.get_selected_objects()
		if objs:
			self.selected = objs[0]
			self.selectedid = self.select.values.index(self.selected)
			return False
		else:
			PopupPrompt(msg='You must select something.', title='Error!').edit()
			self.select.value = [0] # just set the first item to be selected
			self.display() # refresh the widget so the value appears to be selected (otherwise it will be selected, it will just be invisible to the user)
			return True

class WalletGenie_MainForm(MinimalActionFormV2WithMenus):
	OK_BUTTON_TEXT = 'Quit (q)'
	
	_version = '0.15'
	_welcome_msg = 'Hello, I am the Wallet Genie.'.format(_version)
	
	plugins = None
	active_plugin = None # which plugin (e.g. key in the loaded_plugins dictionary) is currently active
	loaded_plugins = {} # loaded_plugins[plugin_name] = {name, loader, plugin_class}
	
	LASTFORM = None
	
	def create(self):
		
		self.how_exited_handers[npyscreen.wgwidget.EXITED_ESCAPE] = self.exit_app
		self.name = 'Wallet Genie v{}'.format(self._version)
		
		self.add(npyscreen.TitleFixedText, name=' ', value=self._welcome_msg, editable=False)
		self.add(npyscreen.TitleFixedText, name='shortcut', value='Plugin functions', editable=False, rely=10)
		
		self.helper_menu = self.add_menu(name='Options', shortcut='^X')
		self.helper_menu.addItem('Enable a Plugin (e)', self.enable_plugin, '1')
		self.helper_menu.addItem('Switch Plugin (c)', self.switch_plugin, '2')
		
		self.add_handlers({
			'^Q': self.exit_app, 'q': self.exit_app,
			'e': self.enable_plugin, 'c': self.switch_plugin,
			's': self.exit_app,
		})
	
	def postInit(self):
		fp, pathname, description = imp.find_module('available_plugins')
		self._enabled_plugins = imp.load_module('wgplugins', fp, pathname, description)
		self._import_plugin = lambda name: imp.load_source('wgplugins.{}'.format(name), os.path.join(PLUGINS_DIR, '{}.py'.format(name)))
		
		self.check_plugins()
		
		self.ppf = PluginPrompterForm()
		self.ppf.select = self.ppf.add(
			npyscreen.TitleMultiSelect, name='Select which plugins you would like to enable', 
			values=self._available_plugins, #value=[self._available_plugins.index(x) for x in self._available_plugins],
			scroll_exit=True, width=1
		)
		self.parentApp.registerForm('PluginSelectForm', self.ppf)
		
		self.switch_plugin_form = PluginPrompterForm(want_cancel_button=True)
		self.switch_plugin_form.select = self.switch_plugin_form.add(npyscreen.TitleSelectOne, name='Select a plugin', values=self._available_plugins, scroll_exit=True, width=1)
		self.parentApp.registerForm('SwitchPluginForm', self.switch_plugin_form)
		
	def activate(self):
		if not self.ppf.selected and not self.loaded_plugins:
			self.parentApp.switchForm('PluginSelectForm')
		else:
			if self.LASTFORM == 'PluginSelectForm': # coming from the enable/disable plugin form
				chosen = self.ppf.selected
				if not chosen:
					chosen = []
				
				tobeunloaded = [p for p in self.loaded_plugins.keys() if p not in chosen]
				tobeloaded = [p for p in chosen if p not in self.loaded_plugins.keys()]
				
				for p in tobeunloaded:
					if p in self.loaded_plugins.keys():
						self.unload_plugin(p)
				if not tobeloaded:
					pass
				else:
					for p in tobeloaded:
						if p not in self.loaded_plugins.keys():
							self.load_plugin(p)
					self.set_active_plugin(tobeloaded[-1])
			
			elif self.LASTFORM == 'SwitchPluginForm':
				if self.switch_plugin_form.selected:
					self.switch_active_plugin(self.switch_plugin_form.selected[0])
			
			else:
				if not self.active_plugin:
					if not self.loaded_plugins:
						self.parentApp.switchForm('PluginSelectForm')
					else:
						self.parentApp.switchForm('SwitchPluginForm')
				else:
					self.edit()
	
	def add_plugin_widgets(self, plugin):
		if plugin not in self.loaded_plugins.keys():
			return None
		
		if 'widgets' not in self.loaded_plugins[plugin].keys():
			self.loaded_plugins[plugin]['widgets'] = []
		
		for i, (shortcut, menud) in enumerate(sorted(self.loaded_plugins[plugin]['plugin_class'].main_menu.items())):
			if i == 0:
				self.loaded_plugins[plugin]['widgets'].append(
					self.add(npyscreen.TitleFixedText, name=shortcut, value=menud['description'], editable=False, rely=12)
				)
			else:
				self.loaded_plugins[plugin]['widgets'].append(
					self.add(npyscreen.TitleFixedText, name=shortcut, value=menud['description'], editable=False)
				)
			# try to add the shortcut to the main form
			# don't overwrite existing handlers (shapeshift etc.)
			if shortcut not in self.handlers.keys():
				self.add_handlers({shortcut: menud['callback']})
	
	def remove_plugin_widgets(self, plugin):
		if plugin not in self.loaded_plugins.keys():
			return None
		
		if 'widgets' not in self.loaded_plugins[plugin] or not self.loaded_plugins[plugin]['widgets']:
			return None
		
		#for w in self.loaded_plugins[plugin]['widgets']:
		#	self.remove(w)
		
		for i, (shortcut, menud) in enumerate(sorted(self.loaded_plugins[plugin]['plugin_class'].main_menu.items())):
			if shortcut in self.handlers.keys():
				del self.handlers[shortcut]
		
	def show_plugin_widgets(self, plugin, show_widgets=True):
		'''
		show / hide individual plugin main menu
		this also removes the handlers associated
		'''
		if plugin not in self.loaded_plugins.keys():
			return None
		if 'widgets' not in self.loaded_plugins[plugin] or not self.loaded_plugins[plugin]['widgets']:
			return None
		
		for w in self.loaded_plugins[plugin]['widgets']:
			w.hidden = not show_widgets
		
		for i, (shortcut, menud) in enumerate(sorted(self.loaded_plugins[plugin]['plugin_class'].main_menu.items())):
			if show_widgets:
				if shortcut not in self.handlers.keys():
					self.add_handlers({shortcut: menud['callback']})
			else:
				if shortcut in self.handlers.keys():
					del self.handlers[shortcut]
		
		self.display() # update 
	
	def onFormChange(self, lastform):
		self.LASTFORM = lastform
	
	def check_plugins(self):
		self._available_plugins = self.find_plugins(plugin_dir=PLUGINS_DIR)
	
	def find_plugins(self, plugin_dir=PLUGINS_DIR, exclusions=['WGPlugins']):
		modules = pkgutil.iter_modules(path=[plugin_dir])
		ret_modules = []
		for loader, mod_name, ispkg in modules:
			if mod_name not in sys.modules and mod_name not in exclusions:
				ret_modules.append(mod_name)
		return ret_modules
	
	def get_plugin_class(self, plugin):
		if '_' in plugin:
			words = plugin.split('_')[1 : ]
		else:
			words = [plugin]
		ret = ''
		for w in words:
			ret += w.title()
		return ret
	
	def switch_plugin(self, unknown=None):
		self.parentApp.switchForm('SwitchPluginForm')
	
	def set_active_plugin(self, plugin):# convenience function
		return self.switch_active_plugin(plugin)
	
	def switch_active_plugin(self, plugin):
		if plugin is None:
			for p in self.loaded_plugins.keys():
				self.show_plugin_widgets(p, False)
			self.active_plugin = None
			return True
		
		if plugin not in self.loaded_plugins.keys():
			return None
		
		# hide all other loaded plugins and show this one
		tohide = [x for x in self.loaded_plugins.keys() if x != plugin]
		for p in tohide:
			self.show_plugin_widgets(p, False)
		
		self.show_plugin_widgets(plugin, True)
		self.active_plugin = plugin
		
		# update the enable/disable plugin and choose plugin selection dialogs
		self.switch_plugin_form.select.value = sorted(self.loaded_plugins.keys()).index(self.active_plugin)
		
		self.check_plugins()
		loaded_names = list(self.loaded_plugins.keys())
		self.ppf.select.value = [self._available_plugins.index(x) for x in loaded_names if x in self._available_plugins]
		self.switch_plugin_form.select.values = sorted(loaded_names)
		
		self.update_plugins()
	
	def enable_plugin(self, unknown=None):
		self.parentApp.switchForm('PluginSelectForm')
	
	def load_plugin(self, plugin):
		loader = self.import_plugin(plugin)
		if not loader:
			return None
		
		# instantiate the new class
		classname = self.get_plugin_class(plugin)
		loaded_class = getattr(loader, classname)
		try:
			plug = loaded_class(self.plugins, self.loaded_plugins, self.active_plugin, self.load_plugin)
			try:
				assert plug.main_menu
			except (AttributeError, AssertionError):
				npyscreen.notify_confirm('{} could not be initiated'.format(plugin))
				plug.cleanup()
				return None
		except IOError as e:
			npyscreen.notify_confirm('Error initiating {}: {}'.format(plugin, e))
			return None
			
		self.switch_active_plugin(plugin)
		self.loaded_plugins[plugin] = { 
			'name': plugin, 
			'loader': loader,
			'plugin_class': plug
		}
		
		self.add_plugin_widgets(plugin)
		
		npyscreen.notify_confirm('Successfully loaded {}'.format(plugin))
		self.update_plugins()
		return True
	
	def unload_plugin(self, plugin):
		if plugin not in self.loaded_plugins.keys():
			return None
		
		self.loaded_plugins[plugin]['plugin_class'].cleanup()
		
		del self.loaded_plugins[plugin]
		if self.active_plugin == plugin:
			self.active_plugin = None
		
		self.remove_plugin_widgets(plugin)
		
		self.update_plugins()
		return True
	
	def import_plugin(self, plugin):
		try:
			return self._import_plugin(plugin)
		except Exception as e:
			npyscreen.notify_confirm('Error initializing {} plugin: {}'.format(plugin, e))
			return None
		
	def update_plugins(self):
		for plugin, plugind in self.loaded_plugins.items():
			if 'plugin_class' in plugind.keys():
				plugind['plugin_class'].on_plugin_update(self.plugins, self.loaded_plugins, self.active_plugin)
	
	def exit_app(self, unknown=None):
		self.editing = False
		try:
			self.parentApp.setNextForm(None)
			self.parentApp.switchFormNow()
			self.exit_app()
		except RuntimeError as e: # maximum recursion depth exceeded
			print('fixme: RuntimeError -> {}'.format(e))
			pass
		
	def on_ok(self):
		self.exit_app()

class WalletGenieApp(npyscreen.NPSAppManaged):
	themes = {
		'Colorful': npyscreen.Themes.ColorfulTheme, 'Default': npyscreen.Themes.DefaultTheme,
		'Light Transparent': npyscreen.Themes.TransparentThemeLightText, 'Dark Transparent': npyscreen.Themes.TransparentThemeDarkText
	}
	def onStart(self):
		npyscreen.setTheme(self.themes['Default'])
		self.wgmf = WalletGenie_MainForm()
		self.registerForm('MAIN', self.wgmf)
		self.wgmf.postInit()
	
	def onInMainLoop(self):
		lastform = self.LAST_ACTIVE_FORM_NAME
		#for fname, f in self._Forms.iteritems():
		#	f.onFormChange(lastform, 
		self._Forms['MAIN'].onFormChange(lastform)
		

if __name__ == '__main__':
	wg = WalletGenieApp()
	try:
		wg.run()
	except KeyboardInterrupt:
		pass
	
	print('goodbye')
	sys.exit(0)