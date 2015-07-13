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

class PluginPrompterForm(npyscreen.ActionFormV2):
	OK_BUTTON_TEXT = 'OK'
	CANCEL_BUTTON_TEXT = 'Cancel'
	
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
	
	def on_cancel(self):
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

class WalletGenie_MainForm(MinimalActionFormV2WithMenus):
	OK_BUTTON_TEXT = 'Quit (q)'
	
	_version = '0.15'
	_welcome_msg = '* Hello, I am the Wallet Genie v{} *'.format(_version)
	
	plugins = None
	active_plugin = None # which plugin (e.g. key in the loaded_plugins dictionary) is currently active
	loaded_plugins = {} # loaded_plugins[plugin_name] = {name, loader, plugin_class}
	
	LASTFORM = None
	
	def create(self):
		
		self.how_exited_handers[npyscreen.wgwidget.EXITED_ESCAPE] = self.exit_app
		self.name = self._welcome_msg
		
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
		
		self.switch_plugin_form = PluginPrompterForm()
		self.switch_plugin_form.select = self.switch_plugin_form.add(npyscreen.TitleSelectOne, name='Select a plugin', values=self._available_plugins, scroll_exit=True, width=1)
		self.parentApp.registerForm('SwitchPluginForm', self.switch_plugin_form)
		
	def activate(self):
		if not self.ppf.selected and not self.loaded_plugins:
			self.parentApp.switchForm('PluginSelectForm')
		else:
			if self.LASTFORM == 'PluginSelectForm': # coming from the enable/disable plugin form
				chosen_plugins = self.ppf.selected
				
				if not chosen_plugins:
					chosen_plugins = []
				
				for p in chosen_plugins:# load these plugins, if they are not already loaded
					if p not in self.loaded_plugins.keys():
						#npyscreen.notify_confirm('Load {}'.format(p))
						self.load_plugin(p)
						
				for p in [x for x in self._available_plugins if x not in chosen_plugins]:# disable these plugins
					if p in self.loaded_plugins.keys():
						#npyscreen.notify_confirm('Unload {}'.format(p))
						self.unload_plugin(p)
				
				self.check_plugins()
				loaded_names = list(self.loaded_plugins.keys())
				self.ppf.select.value = [self._available_plugins.index(x) for x in loaded_names if x in self._available_plugins]
				
				self.switch_plugin_form.select.values = sorted(loaded_names)
				if self.active_plugin:
					if self.active_plugin in loaded_names:
						self.switch_plugin_form.select.value = loaded_names.index(self.active_plugin)
					else:
						self.active_plugin = None
			
			if not self.active_plugin:
				if self.LASTFORM == 'SwitchPluginForm':
					if self.switch_plugin_form.selected:
						self.check_plugins()
						self.active_plugin = self.switch_plugin_form.selected[0]
						self.switch_plugin_form.select.value = sorted(self.loaded_plugins.keys()).index(self.active_plugin)
				else:
					if self.switch_plugin_form.select.values:
						self.parentApp.switchForm('SwitchPluginForm')
					else:
						self.parentApp.switchForm('PluginSelectForm')
			else:
				self.edit()
	
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
			#plug = loaded_class()
		except IOError as e:
			npyscreen.notify_confirm('Error initiating {}: {}'.format(plugin, e))
			return None
			
		self.active_plugin = plugin
		self.loaded_plugins[plugin] = { 
			'name': plugin, 
			'loader': loader,
			'plugin_class': plug
		}
		
		npyscreen.notify_confirm('Successfully loaded {}'.format(plugin))
		self.update_plugins()
	
	def unload_plugin(self, plugin):
		if plugin not in self.loaded_plugins.keys():
			return None
		
		self.loaded_plugins[plugin]['plugin_class'].cleanup()
		
		del self.loaded_plugins[plugin]
		if self.active_plugin == plugin:
			self.active_plugin = None
		
		self.update_plugins()
	
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
		npyscreen.setTheme(self.themes['Colorful'])
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