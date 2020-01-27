#!/usr/bin/env python3

"""
Base stockpile results object
"""

from datetime import datetime
from typing import Dict, Optional, Union


class StockpileResults(Dict[str, Union[bool, int, str]]):

    """
    A Dict like object to hold the results of a backup attempt

    Example:
    {
        "ip": "123.123.123.123",
        "hostname": "fw_Fw_FW",
        "http_mgmt_port": 8443,
        "http_port_check_ok": True,
        "ssh_mgmt_port": 22,
        "ssh_port_check_ok": True,
        "backup_successful": True,
        "save_config_successful": True,
        "http_used": True,
        "ssh_used": False,
        "last_backup_attempt": 2020-01-25T13:25:53.540015,
        "last_successful_backup": None,
        "device_config": None,
    }
    """

    def __init__(
        self,
        name: str,
        ip: str,
        hostname: str,
        http_management: bool = False,
        http_mgmt_port: int = 443,
        http_port_check_ok: bool = False,
        ssh_mgmt_port: int = 22,
        ssh_port_check_ok: bool = False,
        backup_successful: bool = False,
        save_config_successful: bool = False,
        http_used: bool = False,
        ssh_used: bool = False,
        last_backup_attempt: str = datetime.utcnow().isoformat(),
        last_successful_backup: Optional[datetime] = None,
        device_config: Optional[str] = None,
        **kwargs: Union[bool, int, str],
    ) -> None:
        """
        Initialize a StockpileResults object to hold our backup results
        :param name: A name for this object, usually will be the `task.host` from Nornir inventory plus _backup
        :param ip: IP address of the device we attempted to backup
        :param hostname: Hostname of the device we attempted to backup, usually the output of task.host
        :param http_management: Is this device able to be managed via HTTP?
        :param http_mgmt_port: What port do we manage it via HTTPS on? (Default 443)
        :param http_port_check_ok: Is the http_mgmt_port available?
        :param ssh_mgmt_port: What port do we manage this device on for SSH?
        :param ssh_port_check_ok: Is the ssh_mgmt_port available?
        :param backup_successful: Was this backup attempt successful?
        :param save_config_successful: Was saving the config successful?
        :param http_used: Did we use HTTP in this backup attempt?
        :param ssh_used: Did we use SSH in this backup attempt?
        :param last_backup_attempt: When did we attempt this backup?
        :param last_successful_backup: When was the last successful backup?
        :param device_config: The device configuration we gathered (if any)
        :param **kwargs: Any other outstanding items you need in this results Dict
        """
        self.name = name

        # Pass on all of our arguments to the underlying dict creation
        arguments = {k: v for (k, v) in locals().items() if k not in ["self", "__class__", "kwargs", "name"]}
        arguments.update(**kwargs)
        super().__init__(**arguments)

    def __repr__(self) -> str:
        return "{} ({}): {}".format(self.__class__.__name__, self.name, super().__repr__())
