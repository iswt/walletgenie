import npyscreen

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
		
		self.allow_empty_strings = False
		if 'allow_blank_strings' in kwargs and kwargs['allow_blank_strings']:
			self.allow_empty_strings = True
			
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
			if not self.allow_empty_strings:
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
