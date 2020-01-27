#!/usr/bin/env python3

"""
Backup tasks for Cisco devices
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


logger = getLogger("stockpiler")


def stockpile_cisco_generic(
    task: Task, stockpile_directory: pathlib.Path, backup_command: str = "more system:running-config"
) -> Result:
    """
    Gather the text configuration from a Cisco IOS (or similar) device, and write that to a file
    (overwriting any existing file by that name)
    :param task:
    :param stockpile_directory: An instantiated pathlib.Path object for the directory where we're going to write this
    :param backup_command: What command to execute for backup, defaults to `more system:running-config`
    :return: Return a Nornir Result object.  The Result.result attribute will contain a
        stockpiler.tasks.device_backup.StockpileResults object which is a dict-like object containing information on if
        backup was successful and what method was used, the config, etc.
    """

    # Dict-like object of our eventual return info
    stockpile_info = StockpileResults(
        name=f"{task.host}_backup",
        ip=task.host.hostname,
        hostname=task.host.get("device_name", task.host),
        ssh_mgmt_port=task.host.get("port", 22) or 22,  # Need `or` statement as we're getting None from inventory
    )

    # Validate SSH TCP port:
    stockpile_info["ssh_port_check_ok"] = task.run(
        task=tcp_ping, ports=[stockpile_info["ssh_mgmt_port"]], timeout=1
    ).result[stockpile_info["ssh_mgmt_port"]]

    # If we can't SSH port, what are we doing here?  GET TO THE CHOPPA!
    if not stockpile_info["ssh_port_check_ok"]:
        logger.error(
            "Unable to reach SSH (%s) management port on %s", stockpile_info["ssh_mgmt_port"], task.host,
        )
        return Result(
            host=task.host, result=stockpile_info, changed=False, failed=not stockpile_info["backup_successful"]
        )

    # Attempt backup via SSH.
    logger.debug("Attempting to backup %s:%s via SSH", task.host, stockpile_info["ssh_mgmt_port"])

    # Gather a backup:
    backup_results = task.run(task=netmiko_send_command, command_string=backup_command)
    if not backup_results[0].failed and "command authorization failed" not in backup_results[0].result.lower():
        stockpile_info["device_config"] = backup_results[0].result
        stockpile_info["backup_successful"] = True
        stockpile_info["ssh_used"] = True
        logger.debug("Successfully backed up %s", task.host)

    # Save the config on the box:
    save_config_results = task.run(task=netmiko_save_config)
    if (
        not save_config_results[0].failed
        and "command authorization failed" not in save_config_results[0].result.lower()
    ):
        stockpile_info["save_config_successful"] = True
        logger.debug("Successfully saved configuration on %s", task.host)

    # Attempt to save the backup if we have one
    if stockpile_info["backup_successful"]:
        file_name = pathlib.Path(stockpile_directory / f"{str(task.host)}.txt")
        task.run(task=files.write_file, filename=str(file_name), content=stockpile_info["device_config"])
    else:
        logger.error("Failed to backup %s", task.host)

    return Result(host=task.host, result=stockpile_info, changed=False, failed=not stockpile_info["backup_successful"])


def stockpile_cisco_asa(
    task: Task,
    stockpile_directory: pathlib.Path,
    backup_command: str = "more system:running-config",
    proxies: dict = None,
) -> Result:
    """
    Gather the text configuration from an ASA and write that to a file (overwriting any existing file by that name)
    :param task:
    :param stockpile_directory: An instantiated pathlib.Path object for the directory where we're going to write this
    :param backup_command: What command to execute for backup, defaults to `more system:running-config`
    :param proxies: Optional Dict of SOCKS proxies to use for HTTP connectivity
    :return: Return a Nornir Result object.  The Result.result attribute will contain a
        stockpiler.tasks.device_backup.StockpileResults object which is a dict-like object containing information on if
        backup was successful and what method was used, the config, etc.
    """

    # Dict-like object of our eventual return info
    stockpile_info = StockpileResults(
        name=f"{task.host}_backup",
        ip=task.host.hostname,
        hostname=task.host.get("device_name", task.host),
        http_management=task.host.get("http_management", False),
        http_mgmt_port=task.host.get("http_mgmt_port", 8443),
        ssh_mgmt_port=task.host.get("port", 22) or 22,  # Need `or` statement as we're getting None from inventory
    )

    # Check if we are using HTTP and if we can hit TCP port; skip if proxies, the TCP check won't do us any good.
    if stockpile_info["http_management"] and proxies is not None:
        stockpile_info["http_port_check_ok"] = True
    elif stockpile_info["http_management"]:
        stockpile_info["http_port_check_ok"] = task.run(
            task=tcp_ping, ports=[stockpile_info["http_mgmt_port"]], timeout=1
        ).result[stockpile_info["http_mgmt_port"]]

    # Validate SSH TCP port, in case we need it (as fallback) or if HTTP mgmt disabled:
    stockpile_info["ssh_port_check_ok"] = task.run(
        task=tcp_ping, ports=[stockpile_info["ssh_mgmt_port"]], timeout=1
    ).result[stockpile_info["ssh_mgmt_port"]]

    # If we can't hit either port, what are we doing here?  GET TO THE CHOPPA!
    if not stockpile_info["http_port_check_ok"] and not stockpile_info["ssh_port_check_ok"]:
        logger.error(
            "Unable to reach either HTTP (%s) or SSH (%s) management ports on %s",
            stockpile_info["http_mgmt_port"],
            stockpile_info["ssh_mgmt_port"],
            task.host,
        )
        return Result(
            host=task.host, result=stockpile_info, changed=False, failed=not stockpile_info["backup_successful"]
        )

    # Attempt backup via HTTPS if port check was OK (and it is configured for https management in inventory)
    if stockpile_info["http_port_check_ok"]:
        logger.debug("Attempting to backup %s:%s via HTTPS", task.host, stockpile_info["http_mgmt_port"])

        # Disable TLS warnings if task.host.hostname is an IP address:
        try:
            _ = ipaddress.ip_address(task.host.hostname)
            import urllib3

            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            verify = False
        except ValueError:
            verify = True

        # Setup Requests options/payload
        url = f"https://{task.host.hostname}:{stockpile_info['http_mgmt_port']}/admin/exec/"
        asa_http_kwargs = {
            "method": "GET",
            "auth": (task.host.username, task.host.password),
            "headers": {"User-Agent": "ASDM"},
            "verify": verify,
            "proxies": proxies,
        }

        # Gather a backup:
        backup_results = task.run(task=http_method, url=url + quote_plus(backup_command), **asa_http_kwargs)
        if (
            backup_results[0].response.ok
            and "command authorization failed" not in backup_results[0].response.text.lower()
        ):
            stockpile_info["device_config"] = backup_results[0].response.text
            stockpile_info["backup_successful"] = True
            stockpile_info["http_used"] = True
            logger.debug("Successfully backed up %s", task.host)

        # Save the config on the box:
        wr_mem_results = task.run(task=http_method, url=url + quote_plus("write mem"), **asa_http_kwargs)
        if (
            wr_mem_results[0].response.ok
            and "command authorization failed" not in backup_results[0].response.text.lower()
        ):
            stockpile_info["save_config_successful"] = True
            logger.debug("Successfully saved configuration on %s", task.host)

    # Attempt backup via SSH, if HTTPS fails or HTTPS management was not enabled.
    if not stockpile_info["backup_successful"] and stockpile_info["ssh_port_check_ok"]:
        logger.debug("Attempting to backup %s:%s via SSH", task.host, stockpile_info["ssh_mgmt_port"])

        # Gather a backup:
        backup_results = task.run(task=netmiko_send_command, command_string=backup_command)
        if not backup_results[0].failed and "command authorization failed" not in backup_results[0].result.lower():
            stockpile_info["device_config"] = backup_results[0].result
            stockpile_info["backup_successful"] = True
            stockpile_info["ssh_used"] = True
            logger.debug("Successfully backed up %s", task.host)

        # Save the config on the box:
        wr_mem_results = task.run(task=netmiko_save_config)
        if not wr_mem_results[0].failed and "command authorization failed" not in wr_mem_results[0].result.lower():
            stockpile_info["save_config_successful"] = True
            logger.debug("Successfully saved configuration on %s", task.host)

    # Attempt to save the backup if we have one
    if stockpile_info["backup_successful"]:
        file_name = pathlib.Path(stockpile_directory / f"{str(task.host)}.txt")
        task.run(task=files.write_file, filename=str(file_name), content=stockpile_info["device_config"])
    else:
        # If we've failed both backup attempts, log that.
        logger.error("Failed to backup %s via HTTPS or SSH", task.host)

    return Result(host=task.host, result=stockpile_info, changed=False, failed=not stockpile_info["backup_successful"])
