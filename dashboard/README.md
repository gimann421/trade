# Status dashboard
`python dashboard/build.py` writes `dashboard/index.html` (git-ignored): one page, seven tabs, all data embedded.
Reads origin/paper-log, the Alpaca PAPER account (read only), memory/ledger.db, research/, setups/ and `dashboard/live.json`.
`live.json` (routines and threads) comes from platform tools a script cannot reach; the refresh routine rewrites it.
Never prints or embeds keys or SEC_CONTACT. Publishing is done by the refresh routine with the Artifact tool.
