# walletgenie #

Walletgenie is a CLI RPC frontend to digital currency daemons.

Currently supports bitcoin-core and counterparty-server.

![Walletgenie on Mac](http://i.imgur.com/LWYm8De.png "Walletgenie on Mac")

## License ##

walletgenie is released under the terms of the MIT license. See [LICENSE](https://github.com/iswt/walletgenie/blob/master/LICENSE) for more information or visit http://opensource.org/licenses/MIT.

## Current Features ##

* Communicates with RPC daemon(s) on local machine or via network (ssh tunnel).
* Plugin design for multi-coin support. Currently supports bitcoin-core and counterparty-server.
* ShapeShift integration. Shift bitcoin and supported Counterparty assets right from your wallets.
* Lets Talk Bitcoin! username lookup support for verified Bitcoin/Counterparty address.

## Future goals ##

* rewrite in curses / ncurses
* python3 compatibility
* more coin plugins - priority to ShapeShift supported coins/assets
* netki.com & onename.com address support

## Dependencies ##

Current requirements are python2.7, with individual plugins requiring more:

* ShapeShift plugin: `requests`
* bitcoin plugin (walletgenie_bitcoin.py): `python-bitcoinlib`, `requests` (if using LTB user search)
* counterparty plugin (walletgenie_counterparty.py): `requests`, `tabulate`

### Instructions ###

* clone from github at https://github.com/iswt/walletgenie
  * Initial run will prompt you to enable plugin(s) and setup configuration files in your home directory (~/.walletgenie if on linux/unix/osx, %appdata%/walletgenie on Windows (see note below)
* Additional plugins can be enabled (with "e") via the main menu when appropriate
* Change between active plugins with "c", ShapeShift with "s", Quit with "q", ^C to cancel/escape to prior menu

The configuration files store information about the RPC connections walletgenie needs to make.

Plugins are enabled by creating a symlink of the plugin that you wish to enable from the available_plugins/ directory into the walletgenie_plugins/ directory. Likewise plugins are disabled by their symlinks being removed from the walletgenie_plugins/ directory.

*Note to Windows Vista+ users:* By default, only the Administrator user has the privileges required to be able to create symlinks. Either use an Administrator shell when enabling the plugins (so that walletgenie can make the symlinks for you), make the symlinks yourself, or grant your user privileges to create symlinks (see this stack overflow thread: http://stackoverflow.com/questions/815472/how-do-i-grant-secreatesymboliclink-on-windows-vista-home-edition/2085468#2085468). Read [Issue 1578269](https://bugs.python.org/issue1578269) for more information.



