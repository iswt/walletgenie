from wgplugins.WGPlugins import WGPluginForm, WalletGenieConfig, WalletGenieImportError
from wgplugins.WGPlugins import DefaultPluginForm, PluginForm
from lib.prompts import PopupPrompt, ChoicePopup, PasswordPrompt, ChoiceOptionPrompt, ExtendedBoxTitle
from lib.util import get_address_by_netki_wallet, get_address_by_ltb_user, make_human_readable
try:
	from bitcoin.core import b2x, b2lx, x, lx
	import bitcoin.rpc
except ImportError:
	raise WalletGenieImportError('Unable to import bitcoinlib -- install it with: `pip install python-bitcoinlib`')
try:
	import pyperclip
except ImportError:
	pass
import npyscreen
import curses
import json
import decimal
import datetime
import time

from wgplugins.WGPlugins import PluginForm
class PeerViewForm(PluginForm, npyscreen.FormMutt):
	def __init__(self, *args, **kwargs):
		super(PeerViewForm, self).__init__(*args, **kwargs)
	
	def create(self):
		super(PeerViewForm, self).create()

class SendViewForm(PluginForm, npyscreen.ActionFormV2):
	def __init__(self, *args, **kwargs):
		super(SendViewForm, self).__init__(*args, **kwargs)
	
	def create(self):
		super(SendViewForm, self).create()
	
	def draw_form(self):
		super(SendViewForm, self).draw_form()
		

class ReceiveViewForm(PluginForm, npyscreen.ActionFormV2):
	def __init__(self, *args, **kwargs):
		super(ReceiveViewForm, self).__init__(*args, **kwargs)
	
	def create(self):
		super(ReceiveViewForm, self).create()

class SignMessageViewForm(PluginForm, npyscreen.ActionFormV2):
	
	def __init__(self, validationfunc, signfunc, *args, **kwargs):
		super(SignMessageViewForm, self).__init__(*args, **kwargs)
		self.on_validate = validationfunc
		self.on_sign = signfunc
		self.allow_empty_strings = False
	
	def create(self):
		super(SignMessageViewForm, self).create()
		self.name = 'Sign message'
		
		self.Options = npyscreen.OptionList()
		self.options = self.Options.options
		
		self.options.append(npyscreen.OptionFreeText('Message:', value=''))
		
		self.address_select = npyscreen.OptionSingleChoice('Address:', choices=[])
		self.options.append(self.address_select)
		
		self.option_display = self.add(npyscreen.OptionListDisplay, values=self.Options.options, scroll_exit=True, max_height=None)
	
	def on_ok(self):
		msg = self.options[0].get()
		addy = self.options[1].get()
		
		if not self.allow_empty_strings:
			if not msg or msg == '':
				npyscreen.notify_confirm('Cannot leave `Message` field blank')
				return True
			if not addy:
				npyscreen.notify_confirm('Cannot leave `Address` field blank')
				return True
			ret = self.on_validate(addy[0])
			if type(ret) is str:
				npyscreen.notify_confirm(ret)
				return True
			
			self.on_sign(addy[0], msg)
			return False

class VerifyMessageViewForm(PluginForm, npyscreen.ActionFormV2):
	def __init__(self, verifyfunc, *args, **kwargs):
		super(VerifyMessageViewForm, self).__init__(*args, **kwargs)
		self.on_verify = verifyfunc
		self.allow_empty_strings = False
	
	def create(self):
		super(VerifyMessageViewForm, self).create()
		self.name = 'Verify message'
		
		self.Options = npyscreen.OptionList()
		self.Options.options.append(npyscreen.OptionFreeText('Signature:', value=''))
		self.Options.options.append(npyscreen.OptionFreeText('Message:', value=''))
		self.Options.options.append(npyscreen.OptionFreeText('Address:', value=''))
		
		self.option_display = self.add(npyscreen.OptionListDisplay, values=self.Options.options, scroll_exit=True, max_height=None)
	
	def on_ok(self):
		sig = self.Options.options[0].get()
		msg = self.Options.options[1].get()
		addy = self.Options.options[2].get()
		
		if not self.allow_empty_strings:
			if not sig or sig == '':
				npyscreen.notify_confirm('Cannot leave `Signature` field blank')
				return True
			if not msg or msg == '':
				npyscreen.notify_confirm('Cannot leave `Message` field blank')
				return True
			if not addy or addy == '':
				npyscreen.notify_confirm('Cannot leave `Address` field blank')
				return True
			
			self.on_verify(addy, sig, msg)
			return False

class BitcoinRPCProxy(bitcoin.rpc.Proxy):
	'''
	wrap all _call functionality to catch JSONRPCException and print out the error
	'''
	def _call(self, service_name, *args):
		try:
			return super(BitcoinRPCProxy, self)._call(service_name, *args)
		except bitcoin.rpc.JSONRPCException as e:
			msg = '{}'.format(e.error['message'])
			PopupPrompt(msg='{0}'.format(msg), title='RPC Error').edit()
			#npyscreen.notify_confirm(title='RPC Error', msg='{}'.format(msg))
			return False

class Bitcoin(DefaultPluginForm):
	
	coin_name = 'Bitcoin'
	coin_symbol = 'BTC'
	
	def __init__(self, *args, **kwargs):
		super(Bitcoin, self).__init__(*args, **kwargs)
		
		self.config_file = 'wgbitcoin.conf'
		self.conf_values = {
			'rpcpassword': None,
			'rpcuser': 'rpc', 'rpcssl': '0',
			'rpcport': '8332', 'rpcurl': '127.0.0.1'
		}
		
		wgc = WalletGenieConfig()
		self.rpcd = wgc.check_load_config(self.config_file, wanted_values=self.conf_values)
		if not self.rpcd:
			npyscreen.notify_confirm('It appears that {} does not yet exist. If this is your first time running the Bitcoin plugin, you will need a config file detailing your RPC connection information'.format(self.config_file))
			if not wgc.set_from_coin_or_text(self.config_file, config_vars=self.conf_values):
				raise WalletGenieConfigurationError('Failed to set configuration file. Aborting Bitcoin plugin.')
			else:
				self.rpcd = wgc.check_load_config(self.config_file, wanted_values=self.conf_values)
				if not self.rpcd:
					raise WalletGenieConfigurationError('Could not load {}'.format(self.config_file))
		
		self.access = BitcoinRPCProxy(
			service_url='{}://{}:{}@{}:{}'.format(
				'https' if int(self.rpcd['rpcssl']) else 'http', self.rpcd['rpcuser'], self.rpcd['rpcpassword'], self.rpcd['rpcurl'], self.rpcd['rpcport']
			)
		)
		btci = self.access.getinfo()
		btcni = self.access.getnetworkinfo()
		if not btci or not btcni:
			raise WalletGenieConfigurationError('Could not initiate Bitcoin with the provided credentials')
		version_str = '{0:.0f}.{1:.0f}.{2:.0f}.{3:.0f}'.format(
			btci['version'] / 1000000,
			(btci['version'] % 1000000) / 10000,
			(btci['version'] % 10000) / 100,
			btci['version'] % 100
		)
		self.wStatus1.value = ' Bitcoind v{} / {} '.format(version_str, btcni['subversion'].replace('/', ''))
		
		# common background widget values
		self.nodecount = btci['connections']
		self.blockheight = btci['blocks']
		self.tslb = 0
		self.balance = self.from_satoshis(self.access.getbalance())
		self.unconfirmed_balance = None
		self.uploaded = 0
		self.downloaded = 0
		
		self.update_form_values(check_balance=False, check_peers=False, getinfo=False)
	
	def create(self):
		'''
		Classes inheriting from DefaultPluginForm MUST have at least one editable widget on the form
		'''
		super(Bitcoin, self).create()
		
		self.address_widget_max_width = 58 # 34 + 4 + 20
		
		needed_half = False # used when instantiating the mempool widget below
		addy_max_width = self.address_widget_max_width
		if self.columns / 2 <= addy_max_width:
			addy_max_width = int(self.columns / 2) - 5
			self.address_widget_max_width = addy_max_width
			needed_half = True
		self.addresses_widget = self.add(
			ExtendedBoxTitle, name='Addresses', values=[], rely=5,
			max_height=int(self.lines / 3) - 1, max_width=addy_max_width, wrap=True, scroll_exit=False
		)
		
		self.show_empty_addresses_widget = self.add(
			npyscreen.Checkbox, name = 'Show empty addresses',
			max_width=addy_max_width, rely=4, value=False
		)
		def on_empty_address_toggle(*args):
			self.update_form_values(check_addresses=True,
				check_balance=False, check_unconfirmed_balance=False, check_peers=False, getinfo=False,
				check_transactions=False, check_mempool=False, check_bandwidth=False
			)
		self.show_empty_addresses_widget.whenToggled = on_empty_address_toggle
		
		mempool_max_width = int(self.columns / 2) - 1
		mempool_relx = int(self.columns / 2)
		if not needed_half:
			mempool_relx = addy_max_width + 5 + 1
			mempool_max_width = self.columns - (addy_max_width + 5 + 2)
			
		self.latest_mempool_widget = self.add(
			ExtendedBoxTitle, name='Mempool', values=['test'], scroll_exit=False,
			relx=mempool_relx, rely=4,
			max_width=mempool_max_width, max_height=int(self.lines / 3)
		)
		
		self.latest_tx_widget = self.add(
			ExtendedBoxTitle, name='Latest Transactions', values=[],
			scroll_exit=False, max_height=int(self.lines / 2) - 3
		)
		
		self.register_form_func('i', self.on_sign_message_view)
		self.register_form_func('v', self.on_verify_message_view)
		
		self.register_form_func('s', self.on_send_view)
		self.register_form_func('r', self.on_receive_view)
		self.register_form_func('p', self.on_peer_view)
		#self.set_default_form('w')
		
		self.add_handlers({'^R': self.update_form_values})
		
		self.bottom_commands = [
			('Send', 0), ('Receive', 0), ('Sign', 1), ('Verify', 0), ('Peers', 0), ('^Quit', [0,1])
		]
	
	def draw_form(self):
		MAXY, MAXX = self.lines, self.columns
		
		tslb = '{}'.format(make_human_readable(self.tslb, time=True))
		
		total_str = '{} ({} ago) / {:>3} Peers / {} | {}'.format(
			self.blockheight, tslb, self.nodecount, self.uploaded, self.downloaded
		)
		
		peerstr = '{}'.format(self.nodecount)
		count_color = 'GOOD' if self.nodecount >= 8 else 'WARNING'
		xrel = self.address_widget_max_width + 6
		
		peer_col = curses.A_BOLD | self.parent.theme_manager.findPair(self, count_color)
		downloaded_col = curses.A_BOLD | self.parent.theme_manager.findPair(self, 'GOODHL')
		uploaded_col = curses.A_BOLD | self.parent.theme_manager.findPair(self, 'STANDOUT')
		blkheight_col = curses.A_BOLD | self.parent.theme_manager.findPair(self, 'STANDOUT')
		
		blktc = 'GOOD'
		if self.tslb > 600: # 10m
			blktc = 'CAUTION'
		elif self.tslb > 1800: # 30m
			blktc = 'WARNING'
		elif self.tslb > 3600: # 1h
			blktc = 'CRITICAL'
		
		blktime_col = curses.A_BOLD | self.parent.theme_manager.findPair(self, blktc)
		
		if xrel + len(total_str) >= MAXX - 3:
			if xrel + len('Block {} was found {} ago'.format(self.blockheight, tslb)) >= MAXX - 3:
				self.curses_pad.addstr(3, xrel, '{}'.format(self.blockheight), blkheight_col)
			else:
				b1 = 'Block '
				b2 = '{}'.format(self.blockheight)
				b3 = ' was found '
				b4 = '{}'.format(tslb)
				b5 = ' ago'
				
				slen = xrel
				
				self.curses_pad.addstr(3, xrel, b1)
				slen += len(b1)
				self.curses_pad.addstr(3, slen, b2, blkheight_col)
				slen += len(b2)
				self.curses_pad.addstr(3, slen, b3)
				slen += len(b3)
				self.curses_pad.addstr(3, slen, b4, blktime_col)
				slen += len(b4)
				self.curses_pad.addstr(3, slen, b5)
				slen += len(b5)
			
			slen = xrel # restart from same x
			
			if xrel + len('{} Peers / {} | {}'.format(peerstr, self.downloaded, self.uploaded)) >= MAXX - 3:
				self.curses_pad.addstr(2, slen, peerstr, peer_col)
				slen += len(peerstr)
				self.curses_pad.addstr(2, slen, ' Peers')
			else:
				p1 = ' Peers'
				p2 = ' / '
				self.curses_pad.addstr(2, slen, peerstr, peer_col)
				slen += len(peerstr)
				self.curses_pad.addstr(2, slen, p1)
				slen += len(p1)
				self.curses_pad.addstr(2, slen, p2, curses.A_BOLD)
				slen += len(p2)
				
				u1 = '{}'.format(self.uploaded)
				d1 = '{}'.format(self.downloaded)
				self.curses_pad.addstr(2, slen, d1, downloaded_col)
				slen += len(d1)
				self.curses_pad.addstr(2, slen, ' | ', curses.A_BOLD)
				slen += 3
				self.curses_pad.addstr(2, slen, u1, uploaded_col)
				slen += len(u1)
			
		else:
			slen = xrel
			
			b1 = ' (found '
			b2 = '{}'.format(tslb)
			b3 = ' ago)'
			blkstr = '{}'.format(self.blockheight)
			self.curses_pad.addstr(2, slen, blkstr, blkheight_col)
			slen += len(blkstr)
			self.curses_pad.addstr(2, slen, b1)
			slen += len(b1)
			self.curses_pad.addstr(2, slen, b2, blktime_col)
			slen += len(b2)
			self.curses_pad.addstr(2, slen, b3)
			slen += len(b3)
			self.curses_pad.addstr(2, slen, ' / ', curses.A_BOLD)
			slen += 3
			
			p1 = ' Peers'
			self.curses_pad.addstr(2, slen, peerstr, peer_col)
			slen += len(peerstr)
			self.curses_pad.addstr(2, slen, p1)
			slen += len(p1)
			self.curses_pad.addstr(2, slen, ' / ', curses.A_BOLD)
			slen += 3
			
			uptot = '{}'.format(self.uploaded)
			downtot = '{}'.format(self.downloaded)
			self.curses_pad.addstr(2, slen, downtot, downloaded_col)
			slen += len(downtot)
			self.curses_pad.addstr(2, slen, ' | ', curses.A_BOLD)
			slen += 3
			self.curses_pad.addstr(2, slen, uptot, uploaded_col)
		
		balance_str1 = 'Balance:    '
		self.curses_pad.addstr(2, 2, balance_str1)
		balance_str2 = '{} BTC'.format(str(self.balance))
		self.curses_pad.addstr(2, 2 + len(balance_str1), balance_str2, curses.A_BOLD | self.parent.theme_manager.findPair(self, 'GOOD'))
		if self.unconfirmed_balance is not None:
			balance_str = balance_str1 + balance_str2
			self.curses_pad.addstr(2, 2 + len(balance_str), ' / ', curses.A_BOLD)
			self.curses_pad.addstr(2, 4 + len(balance_str), ' {} BTC'.format(self.unconfirmed_balance), curses.A_BOLD | self.parent.theme_manager.findPair(self, 'CAUTION'))
		
		super(Bitcoin, self).draw_form()
	
	def resize(self):
		super(Bitcoin, self).resize()
		
		self.address_widget_max_width = 58 # 34 + 4 + 20
		addy_max_width = self.address_widget_max_width
		if self.columns / 2 <= addy_max_width:
			addy_max_width = int(self.columns / 2) - 5
			self.address_widget_max_width = addy_max_width
		self.addresses_widget.max_width = addy_max_width
		for w in self.addresses_widget._my_widgets:
			w.width = self.addresses_widget.max_width - 3
		
		if self.columns / 2 <= self.address_widget_max_width:
			self.latest_mempool_widget.max_width = int(self.columns / 2) - 1
			self.latest_mempool_widget.relx = int(self.columns / 2)
		else:
			self.latest_mempool_widget.max_width = self.columns - (self.address_widget_max_width + 5 + 2)
			self.latest_mempool_widget.relx = addy_max_width + 5 + 1
		for w in self.latest_mempool_widget._my_widgets:
			w.relx = self.latest_mempool_widget.relx + 2
			w.width = self.latest_mempool_widget.max_width - 3
		
		self.addresses_widget.resize()
		self.latest_mempool_widget.resize()
		
		self.latest_tx_widget.max_height = int(self.lines / 2) - 3
		for w in self.latest_tx_widget._my_widgets:
			w.width = self.latest_tx_widget.max_width - 3
		self.latest_tx_widget.resize()
	
	def update_form_values(self, *args, 
			check_balance=True, check_unconfirmed_balance=True, check_peers=True, 
			getinfo=True, check_transactions=True, check_addresses=True, check_mempool=True, 
			check_bandwidth=True, check_tslb=True):
		
		if check_balance:
			self.balance = self.from_satoshis(self.access.getbalance())
		if check_unconfirmed_balance:
			self.unconfirmed_balance = self.from_satoshis(self.access.getunconfirmedbalance())
			if self.unconfirmed_balance <= 0.0:
				self.unconfirmed_balance = None
		if getinfo:
			btci = self.access.getinfo()
			self.blockheight = btci['blocks']
		if check_tslb:
			blkinfo = self.access.getblock( lx(self.access.getbestblockhash()) )
			blkheader = blkinfo.get_header()
			#self.tslb = blkheader.nTime
			self.tslb = time.time() - blkheader.nTime
			#tslb = datetime.datetime.utcnow() - datetime.datetime.fromtimestamp(blkheader.nTime)
			#self.tslb = tslb.seconds // 60 % 60 # keep it in minutes
		if check_peers:
			btci = self.access.getnetworkinfo()
			self.nodecount = btci['connections']
		if check_bandwidth:
			nt = self.access.getnettotals()
			self.downloaded = make_human_readable(nt['totalbytesrecv'])
			self.uploaded = make_human_readable(nt['totalbytessent'])
		if check_transactions:
			txs = self.access.listtransactions()
			self.latest_tx_widget.values = []
			for tx in reversed(txs):
				whichway = '=>'# u'\u279C' 
				if tx['category'] == 'receive':
					whichway = '<='# u'\u2B05'
				if 'address' in tx: # move operations do not have the address, txid or block fields
					addy = tx['address']
					self.latest_tx_widget.values.append(json.dumps(
						[
							tx['confirmations'], str(datetime.datetime.fromtimestamp(tx['time'])),
							str(tx['amount']), whichway, addy
						]
					))
		if check_addresses:
			allow_empty = self.show_empty_addresses_widget.value
			addybal = self.get_wallet_addresses(allow_empty=allow_empty, return_balances=True)
			self.addresses_widget.values = []
			for addy, bal in sorted(addybal, key=lambda x: x[1])[::-1]:
				self.addresses_widget.values.append(
					json.dumps(['{}'.format(addy), '{:>12} BTC'.format(bal)])
				)
		if check_mempool:
			rmpi = self.access.getrawmempool()
			rpi = self.access.getmempoolinfo()
			
			self.latest_mempool_widget.name = 'Mempool / {} txs / {}'.format(self.formatted(rpi['size']), make_human_readable(rpi['bytes']))
			rawt = self.access._batch(
				[
					{'method': 'getrawtransaction', 'version': '1.1',
					'params': [b2lx(tx), 1], 'id': str(i)} for i, tx in enumerate(rmpi if len(rmpi) <= 50 else rmpi[: 50])
				]
			)
			self.latest_mempool_widget.values = []
			for d in reversed(rawt):
				val = decimal.Decimal('0.0')
				for vo in d['result']['vout']:
					val += vo['value']
				tx = d['result']['txid']
				
				self.latest_mempool_widget.values.append('{:>12} BTC   {}'.format(val, tx))
			
		self.display() # update the values being drawn to the screen
		self.latest_mempool_widget.update() # and then update all widgets to avoid blanking
		self.latest_tx_widget.update() # perhaps this is inefficient?
		self.addresses_widget.update()
	
	def on_peer_view(self):
		f = PeerViewForm()
		return f
	
	def on_send_view(self):
		f = SendViewForm()
		return f
	
	def on_receive_view(self):
		f = ReceiveViewForm()
		return f
	
	def on_sign_message_view(self):
		def validate(addy):
			if not self.is_address_valid(addy):
				return '{} is not a valid Bitcoin address'.format(addy)
			return True
		
		def sign(addy, msg):
			signed = self.sign_message(addy, msg)
			if signed:
				outmsg = 'Address: {}\nSigned: {}\nMessage: {}'.format(addy, signed, msg)
				try:
					pyperclip.copy(outmsg)
					outmsg += '\n(text has been copied to the clipboard)'
				except NameError:
					outmsg += '\n(tip: `pip install pyperclip` if you want me to be able to copy this text)'
				
				self.output(outmsg, title='Signed message')
		
		f = SignMessageViewForm(validate, sign)
		f.address_select.choices = self.get_wallet_addresses(allow_empty=True)
		return f
	
	def on_verify_message_view(self):
		def verify(addy, sig, msg):
			signed = self.access.verifymessage(addy, sig, msg)
			if signed:
				self.output('I can confirm the message was definitely signed by {}'.format(addy), title='Successful verification', wide=False)
			else:
				self.output('The message failed verification. (double check that your input was correct)', title='Message failed verification', wide=False)
		f = VerifyMessageViewForm(verify)
		return f
	
	def show_balance(self, *args):
		self.output('You have {} BTC in your bitcoin coffers'.format(self.from_satoshis(self.access.getbalance())))
	
	def sign_tx(self, utx):
		stx = self.access._call('signrawtransaction', utx)
		if not stx or not stx['complete']:
			return None
		return stx['hex']
	
	def broadcast_tx(self, stx):
		tx = self.access._call('sendrawtransaction', stx)
		return tx
	
	def sign_and_broadcast(self, utx):
		self.try_unlock_wallet()
		stx = self.sign_tx(utx)
		if not stx:
			return None
		tx = self.broadcast_tx(stx)
		if not tx:
			return None
		return tx
	
	def sign_message(self, address, message):
		self.try_unlock_wallet()
		signed = self.access.signmessage(address, message)
		self.try_lock_wallet()
		return signed
	
	def get_wallet_addresses(self, allow_empty=False, return_balances=False):
		wallet_addresses = self.access.listaddressgroupings()
		active = []
		
		for w in wallet_addresses:
			for tup in w:
				addy, balance = tup[0], tup[1]
				if allow_empty:
					active.append( (addy, balance) )
				else:
					if float(balance) > 0:
						active.append( (addy, balance) )
		
		just_addresses = [x[0] for x in active]
		
		# listaddressgroupings() does not return all addresses in the wallet
		# iterate through the accounts and collect all of them
		existing_accounts = self.access._call('listaccounts')
		accs = [ x[0] for x in existing_accounts.items() ]
		
		addys_by_acc = []
		for a in accs:
			l = self.access._call('getaddressesbyaccount', a)
			for x in l:
				addys_by_acc.append(x)
		
		for aa in addys_by_acc:
			if aa not in just_addresses and allow_empty:
				active.append( (aa, 0.0) )
				
		if return_balances:
			return active # returns a list of tuples [(address, btc balance), ...]
		else:
			return [a[0] for a in active]
	
	def _prompt_import_privkey(self, *args):
		if not npyscreen.notify_yes_no('This process will rescan your wallet, which is likely to take a (potentially very) long time. Are you sure that you want to continue?'):
			return False
		
		cop = ChoiceOptionPrompt(disp_name = 'Import new private key', allow_blank_strings = True, prompt_options = [
			{'widget': npyscreen.OptionFreeText, 'args': ['privkey:'], 'kwargs': {'value': ''}},
			{'widget': npyscreen.OptionFreeText, 'args': ['label:'], 'kwargs': {'value': ''}}
		])
		cop.edit()
		d = cop.get_options()
		privkey = d['privkey:']
		label = d['label:']
		
		self.try_unlock_wallet()
		suc = self.access._call('importprivkey', privkey, label)
		self.try_lock_wallet()
		
		if suc:
			self.output('I have successfully imported your private key: {}'.format(suc))
		else:
			return None
	
	def _prompt_import_watch_address(self, *args):
		if not npyscreen.notify_yes_no('This process will rescan your wallet, which is likely to take a (potentially very) long time. Are you sure that you want to continue?'):
			return False
		
		def validaddy(addy):
			if self.is_address_valid(addy):
				return True
			else:
				return '{} is not a valid Bitcoin address'.format(addy)
		
		cop = ChoiceOptionPrompt(disp_name = 'Import new watch address', allow_blank_strings = True, prompt_options = [
			{'widget': npyscreen.OptionFreeText, 'args': ['address:'], 'kwargs': {'value': ''}, 'validator': validaddy},
			{'widget': npyscreen.OptionFreeText, 'args': ['label:'], 'kwargs': {'value': ''}}
		])
		cop.edit()
		d = cop.get_options()
		addr = d['address:']
		label = d['label:']
		
		ret = self.access.importaddress(addr, label=label, rescan=True)
		self.output('I have successfully imported the watch-only address {}'.format(addr))
		return ret
		
	
	def is_address_valid(self, address):
		valid = self.access.validateaddress(address)
		if not valid['isvalid']:
			return False
		return True
	
	def is_wallet_encrypted(self):
		info = self.access.getinfo()
		if 'unlocked_until' in info.keys():
			return True
		else:
			return False
	
	def import_privkey(self, privkey, label=''):
		self.try_unlock_wallet()
		imported = self.access._call('importprivkey', privkey, label)
		self.try_lock_wallet()
		return imported
	
	def unlock_wallet(self, duration=300):
		pp = PasswordPrompt()
		pp.edit()
		pwd = pp.pwd.value
		
		isvalid = self.access.walletpassphrase(pwd, int(duration))
		if isvalid == False: # isvalid == None means success, False failure
			return False
		
		return True
	
	def try_unlock_wallet(self, ask_until_correct=True):
		try:
			info = self.access.getinfo()
			if info['unlocked_until'] == 0:
				if not self.unlock_wallet():
					if ask_until_correct:
						correct = False
						while not correct:
							correct = self.unlock_wallet()
					else:
						return False
		except KeyError:
			pass # wallet is unlocked
		return True
	
	def try_lock_wallet(self):
		if not self.is_wallet_encrypted():
			return True
		try:
			self.access._call('walletlock')
		except Exception as e:
			self.output('There was an error locking your wallet: {}')
			return False
		return True
	