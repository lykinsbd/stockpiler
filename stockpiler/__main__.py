#!/usr/bin/env python3

"""
Stockpiler is a Python/Nornir script for backing up network devices to a local Git repository.

See README.md for more information.

Requires Python 3.7 or higher.

"""

from argparse import ArgumentParser, Namespace
import getpass
import importlib.resources
from logging import getLogger
import os
import pathlib
import sys
from typing import Tuple


from nornir import InitNornir
from nornir.core import Nornir
from nornir.core.inventory import ConnectionOptions
from nornir.plugins.processors.print_result import PrintResult
from nornir.plugins.tasks.networking import netmiko_send_command, netmiko_send_config
from yaml import safe_load
from yaml.constructor import ConstructorError


from stockpiler.processors.process_backups import ProcessBackups
from stockpiler.tasks.device_backup import backup_cisco_asa


logger = getLogger("stockpiler")


def main() -> None:
    """
    Do stuff.  Run things.
    :return:
    """
    # Parse Arguments
    args = arg_parsing()

    # Begin Nornir setup
    norns = nornir_initialize(args=args)

    # Filter down the entire fleet as needed
    filtered_norns = filtering(args=args, norns=norns)
    logger.info(f"Executing on {len(filtered_norns.inventory)} devices based on the given filter")

    # Run our desired task
    if args.command:
        command_targets = filtered_norns.with_processors(processors=[PrintResult()])
        command_targets.run(task=netmiko_send_command, command_string=args.command)

    elif args.config:
        config_targets = filtered_norns.with_processors(processors=[PrintResult()])
        config_targets.run(task=netmiko_send_config, config_commands=args.config.split(";"))
    else:
        # Default task will be to backup devices (if none provided)
        proxies = None
        if args.proxy:
            proxies = {"https": f"socks5://{args.proxy}", "http": f"socks5://{args.proxy}"}
        backup_dir = pathlib.Path(args.output or "/opt/stockpiler/")

        bu_targets = filtered_norns.with_processors(processors=[ProcessBackups()])

        # Executing backup on devices:
        bu_targets.run(task=backup_cisco_asa, proxies=proxies, backup_dir=backup_dir)

    sys.exit()


def arg_parsing() -> Namespace:
    """
    Parse the CLI arguments and return them in an Argparse Namespace
    :return:
    """

    argparser = ArgumentParser(description="Stockpile Network Device Backups")
    argparser.add_argument(
        "-i", "--inventory", type=str, help="Provide a specific inventory file, default '/etc/stockpiler/hosts.yaml'"
    )
    argparser.add_argument(
        "-c", "--config_file", type=str, help="Provide a config file, default is packaged with this tool."
    )
    argparser.add_argument(
        "--ssh_config_file", type=str, help="Provide an SSH config file, default is packaged with this tool."
    )
    argparser.add_argument(
        "-o", "--output", type=str, help="Provide a directory to output device backups to, default '/opt/stockpiler'"
    )
    argparser.add_argument("-p", "--proxy", type=str, help="'host:port' for a Socks Proxy to use for connectivity.")
    argparser.add_argument(
        "--prompt_for_credentials",
        action="store_true",
        help="Enable user prompt to provide custom credentials, otherwise will only try environment variables of"
        " STOCKPILER_USER and STOCKPILER_PW.",
    )
    argparser.add_argument("-a", "--addresses", type=int, nargs="+", help="1 (or more) IP Address, space separated.")
    command_group = argparser.add_argument_group("command/config")
    command_group.add_argument("--command", type=str, help="1 command to execute on the selected devices.")
    command_group.add_argument(
        "--config",
        type=str,
        help="1 (or more) command or configuration line to execute on the selected devices, semicolon separated.",
    )
    argparser.add_argument(
        "-l",
        "--log_level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="What level are we logging at",
    )
    argparser.add_argument(
        "--logging_dir",
        default="/var/log/stockpiler/",
        type=str,
        help="output logs to specified directory, default is /var/log/stockpiler/",
    )

    return argparser.parse_args()


def nornir_initialize(args: Namespace) -> Nornir:
    """
    Given the parsed argument Namespace object, initialize a Nornir inventory/execution object and return it.
    :param args: A parsed/instantiated argpase.Namespace object with our command line arguments
    :return:
    """

    log_file = pathlib.Path(args.logging_dir + "stockpiler.log")
    pathlib.Path(log_file).touch()

    logging_config = {
        "level": args.log_level,
        "file": str(log_file),
        "loggers": ["nornir", "paramiko", "netmiko", "stockpiler"],
    }
    if args.config_file:
        config_file = args.config_file
    else:
        with importlib.resources.path(package="stockpiler", resource="nornir_conf.yaml") as p:
            config_file = str(p)

    # See if an SSH config file is specified in args or in the config file, order of precedence is:
    #   First In the inventory: Device -> Group -> Defaults
    #   Then: Args -> Config File -> Packaged SSH Config File
    if args.ssh_config_file:
        ssh_config_file = args.ssh_config_file
    else:
        cf_path = pathlib.Path(config_file)
        if not cf_path.is_file():
            raise ValueError(f"The provided configuration file {str(cf_path)} is not found.")
        with cf_path.open() as cf:
            try:
                cf_yaml = safe_load(cf)
            except (ConstructorError, ValueError) as e:
                raise ValueError(f"Unable to parse the provided config file {str(cf_path)} to YAML: {str(e)}")
        cf_ssh_config_file = cf_yaml.get("ssh", {}).get("config_file", None)
        if cf_ssh_config_file is not None:
            ssh_config_file = cf_ssh_config_file
        else:
            with importlib.resources.path(package="stockpiler", resource="ssh_config") as p:
                ssh_config_file = str(p)

    # Initialize our nornir object/inventory
    logger.info("Reading config file and initializing inventory...")
    norns = InitNornir(config_file=config_file, logging=logging_config, ssh={"config_file": ssh_config_file})

    # Gather credentials:
    username, password, enable = gather_credentials(prompt_for_credentials=args.prompt_for_credentials)

    # Set these into the inventory:
    norns.inventory.defaults.username = username
    norns.inventory.defaults.password = password

    # If there is no Enable, set it to the same as the password.
    norns.inventory.defaults.connection_options["netmiko"] = ConnectionOptions(extras={"secret": enable or password})

    return norns


def gather_credentials(prompt_for_credentials: bool = False) -> Tuple[str, str, str]:
    """
    Gather needed credentials for backing up these devices.
    :param prompt_for_credentials: If set to True, Stockpiler will attempt to gather credentials from the CLI,
        normally it will only use environment variables.  This is useful in interactive applications.
    :return: A Tuple of username, password, and enable.
    """
    username = os.environ.get("STOCKPILER_USER", None)
    password = os.environ.get("STOCKPILER_PW", None)
    enable = os.environ.get("STOCKPILER_ENABLE", None)
    if username is None and password is None and not prompt_for_credentials:
        raise IOError("No credentials have been provided!")
    if username is None:
        username = input("Please provide a username for backup execution: ")
    if password is None:
        password = getpass.getpass("Please provide a password for backup execution: ")

    return username, password, enable


def filtering(args: Namespace, norns: Nornir) -> Nornir:
    """
    Provide inventory filtering based on attributes from args.

    :param args: The populated Namespace object returned by argparser.parse_args()
    :param norns: An instantiated Nornir object with our full inventory for filtering
    :return:
    """

    print("Filtering Target Hosts")

    def is_cli_selected_host(host):
        return host.data["ip"] in args.addresses

    if args.addresses:
        return norns.filter(filter_func=is_cli_selected_host)
    else:
        return norns


if __name__ == "__main__":
    main()
