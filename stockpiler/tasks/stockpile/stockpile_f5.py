#!/usr/bin/env python3

"""
Backup tasks for F5 devices
"""


import ipaddress
from logging import getLogger
import pathlib
from urllib.parse import quote_plus


from nornir.core.task import Result, Task
from nornir.plugins.tasks import files
from nornir.plugins.tasks.apis import http_method
from nornir.plugins.tasks.networking import netmiko_save_config, netmiko_send_command, tcp_ping


from stockpiler.tasks.stockpile.stockpile_results import StockpileResults

pass
