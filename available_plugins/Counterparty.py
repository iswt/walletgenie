
from wgplugins.WGPlugins import WGPlugin

class Counterparty(WGPlugin):
	
	def __init__(self, *args, **kwargs):
		super(Counterparty, self).__init__(*args, **kwargs)
		
		self.main_menu = {
			'0': {'description': 'Show CounterParty Network Diagnostics', 'callback': self.show_diagnostics},
		}
	
	def show_diagnostics(self, *args):
		pass