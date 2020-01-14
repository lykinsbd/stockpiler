#!/usr/bin/env python3

"""
Backup tasks for Cisco devices
"""


import datetime
import ipaddress
from logging import getLogger
import pathlib
from typing import Dict, Union
from urllib.parse import quote_plus


from nornir.core.task import Result, Task
from nornir.plugins.tasks import files
from nornir.plugins.tasks.apis import http_method
from nornir.plugins.tasks.networking import netmiko_save_config, netmiko_send_command, tcp_ping


logger = getLogger("stockpiler")


def backup_cisco_asa(
    task: Task, file_path: pathlib.Path, backup_command: str = "more system:running-config", proxies: dict = None
) -> Result:
    """
    Gather the text configuration from an ASA and write that to a file (overwriting any existing file by that name)
    :param task:
    :param file_path: An instantiated pathlib.Path object for the directory where we're going to write this
    :param backup_command: What command to execute for backup, defaults to `more system:running-config`
    :param proxies: Optional Dict of SOCKS proxies to use for HTTP connectivity
    :return: Return a Nornir Result object.  The Result.result attribute will contain:
        A Dict containing information on if backup was successful and what method was used.
        Example:
        {
            "ip": "123.123.123.123",
            "hostname": "fw_Fw_FW",
            "account_number": 1234,
            "http_mgmt_port": 8443,
            "http_port_check_ok": True,
            "ssh_mgmt_port": 22,
            "ssh_port_check_ok": True,
            "backup_successful": True,
            "write_mem_successful": True,
            "http_used": True,
            "ssh_used": False,
            "last_backup_attempt": datetime.datetime.now().isoformat(),
            "last_successful_backup": None,
        }
    """

    # Dict of our eventual return info, should probably look at turning this into an object.
    backup_info = {
        "ip": task.host,
        "hostname": task.host.get("device_name", task.host),
        "account_number": task.host.get("account_number", 0),
        "http_management": task.host.get("http_management", False),
        "http_mgmt_port": task.host.get("http_mgmt_port", 8443),
        "http_port_check_ok": False,
        "ssh_mgmt_port": task.host.get("port", 22) or 22,  # Need `or` statement as we're getting None from inventory
        "ssh_port_check_ok": False,
        "backup_successful": False,
        "write_mem_successful": False,
        "http_used": False,
        "ssh_used": False,
        "last_backup_attempt": datetime.datetime.utcnow().isoformat(),
        "last_successful_backup": None,
    }  # type: Dict[str, Union[bool, int, str]]
    device_config = None

    # Check if we are using HTTP and if we can hit TCP port; skip if proxies, the TCP check won't do us any good.
    if backup_info["http_management"] and proxies is not None:
        backup_info["http_port_check_ok"] = True
    elif backup_info["http_management"]:
        backup_info["http_port_check_ok"] = task.run(
            task=tcp_ping, ports=[backup_info["http_mgmt_port"]], timeout=1
        ).result[backup_info["http_mgmt_port"]]

    # Validate SSH TCP port, in case we need it (as fallback) or if HTTP mgmt disabled:
    backup_info["ssh_port_check_ok"] = task.run(task=tcp_ping, ports=[backup_info["ssh_mgmt_port"]], timeout=1).result[
        backup_info["ssh_mgmt_port"]
    ]

    # If we can't hit either port, what are we doing here?  GET TO THE CHOPPA!
    if not backup_info["http_port_check_ok"] and not backup_info["ssh_port_check_ok"]:
        logger.error(
            "Unable to reach either HTTP (%s) or SSH (%s) management ports on %s",
            backup_info["http_mgmt_port"],
            backup_info["ssh_mgmt_port"],
            task.host,
        )
        return Result(host=task.host, result=backup_info, changed=False, failed=not backup_info["backup_successful"])

    # Attempt backup via HTTPS if port check was OK (and it is configured for https management in inventory)
    if backup_info["http_port_check_ok"]:
        logger.debug("Attempting to backup %s:%s via HTTPS", task.host, backup_info["http_mgmt_port"])

        # Disable TLS warnings if task.host.hostname is an IP address:
        try:
            _ = ipaddress.ip_address(task.host.hostname)
            import urllib3

            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            verify = False
        except ValueError:
            verify = True

        # Setup Requests options/payload
        url = f"https://{task.host.hostname}:{backup_info['http_mgmt_port']}/admin/exec/"
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
            device_config = backup_results[0].response.text
            backup_info["backup_successful"] = True
            backup_info["http_used"] = True
            logger.debug("Successfully backed up %s", task.host)

        # Save the config on the box:
        wr_mem_results = task.run(task=http_method, url=url + quote_plus("write mem"), **asa_http_kwargs)
        if (
            wr_mem_results[0].response.ok
            and "command authorization failed" not in backup_results[0].response.text.lower()
        ):
            backup_info["write_mem_successful"] = True
            logger.debug("Successfully saved configuration on %s", task.host)

    # Attempt backup via SSH, if HTTPS fails or HTTPS management was not enabled.
    if not backup_info["backup_successful"] and backup_info["ssh_port_check_ok"]:
        logger.debug("Attempting to backup %s:%s via SSH", task.host, backup_info["ssh_mgmt_port"])

        # Gather a backup:
        backup_results = task.run(task=netmiko_send_command, command_string=backup_command)
        if not backup_results[0].failed and "command authorization failed" not in backup_results[0].result.lower():
            device_config = backup_results[0].result
            backup_info["backup_successful"] = True
            backup_info["ssh_used"] = True
            logger.debug("Successfully backed up %s", task.host)

        # Save the config on the box:
        wr_mem_results = task.run(task=netmiko_save_config)
        if not wr_mem_results[0].failed and "command authorization failed" not in wr_mem_results[0].result.lower():
            backup_info["write_mem_successful"] = True
            logger.debug("Successfully saved configuration on %s", task.host)

    # Attempt to save the backup if we have one
    if backup_info["backup_successful"]:
        backup_info["last_successful_backup"] = datetime.datetime.utcnow().isoformat()
        file_name = pathlib.Path(file_path / f"{str(task.host)}.txt")
        task.run(task=files.write_file, filename=str(file_name), content=device_config)
    else:
        # If we've failed both backup attempts, log that.
        logger.error("Failed to backup %s via HTTPS or SSH", task.host)

    return Result(host=task.host, result=backup_info, changed=False, failed=not backup_info["backup_successful"])
