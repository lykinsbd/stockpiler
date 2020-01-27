#!/usr/bin/env python3

"""
Base backup related objects and functions
"""

from netmiko import platforms
from nornir.core.task import Result, Task


from stockpiler.tasks.stockpile.stockpile_cisco import stockpile_cisco_generic, stockpile_cisco_asa


# Maps Netmiko platform to our Stockpiler tasks, default is `stockpile_cisco_generic` unless otherwise specified.
StockpileMap = {platform: stockpile_cisco_generic for platform in platforms}
StockpileMap["cisco_asa"] = stockpile_cisco_asa
# Todo: Add F5, Netscaler, and other platform support.


def stockpile_device_config(task: Task, **kwargs) -> Result:
    """
    Trigger a "stockpile" or backup of a device configuration.  Will use the StockpileMapper dict to determine what
    plugin/task to utilize.
    :param task: Nornir task execution object.
    :param kwargs: Additional arguments to pass to the actual stockpile task.
    :return:
    """

    stockpile_task = StockpileMap[task.host.platform]
    return stockpile_task(task, **kwargs)
