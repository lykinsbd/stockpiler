#!/usr/bin/env python3

"""
Stockpiler is a Python/Nornir script for backing up network devices to a local Git repository.

See README.md for more information.

Requires Python 3.7 or higher.

"""

from argparse import ArgumentParser, Namespace
import datetime
import getpass
import importlib.resources
from logging import getLogger
import os
import pathlib
import sys
from urllib.parse import quote_plus


from git import Actor, Repo
from nornir import InitNornir
from nornir.core import Nornir
from nornir.core.inventory import ConnectionOptions
from nornir.core.task import MultiResult, Task
from nornir.plugins.tasks import files
from nornir.plugins.tasks.apis import http_method
from nornir.plugins.tasks.networking import netmiko_save_config, netmiko_send_command, netmiko_send_config, tcp_ping
from yaml import safe_load
from yaml.constructor import ConstructorError


logger = getLogger("stockpiler")


def main() -> None:
    """
    Do stuff.  Run things.
    :return:
    """
    # Parse Arguments
    args = arg_parsing()
    log_file = args.logging_dir + "stockpiler.log"
    pathlib.Path(log_file).touch()

    # Begin Nornir setup
    logging_config = {
        "level": args.log_level,
        "file": log_file,
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
    norns = InitNornir(config_file=config_file, logging=logging_config, ssh={"config_file": ssh_config_file})
    logger.info("Reading config file and initializing inventory...")

    # Gather credentials:
    username = os.environ.get("STOCKPILER_USER", None)
    password = os.environ.get("STOCKPILER_PW", None)
    enable = os.environ.get("STOCKPILER_ENABLE", None)
    if username is None and password is None and args.no_custom_creds:
        raise IOError("No credentials have been provided!")
    if username is None:
        username = input("Please provide a username for backup execution: ")
    if password is None:
        password = getpass.getpass("Please provide a password for backup execution: ")

    # Set these into the inventory:
    norns.inventory.defaults.username = username
    norns.inventory.defaults.password = password

    # If there is no Enable, set it to the same as the password.
    norns.inventory.defaults.connection_options["netmiko"] = ConnectionOptions(extras={"secret": enable or password})

    # Plumb up Git repository
    if args.output is None:
        backup_dir = pathlib.Path("/opt/stockpiler/")
    else:
        backup_dir = pathlib.Path(args.output)
    repo = git_initialize(backup_dir=pathlib.Path(backup_dir))
    author = Actor(name="Stockpiler", email="stockpiler@localhost.local")

    # Filter down the entire fleet as needed
    target_hosts = filtering(args=args, norns=norns)
    logger.info(f"Executing on {len(target_hosts.inventory)} devices based on the given filter")

    # Prepping task
    task_kwargs = {}
    if args.command:
        task_kwargs["command_string"] = args.command
        task = netmiko_send_command
    elif args.config:
        task_kwargs["config_commands"] = args.config.split(";")
        task = netmiko_send_config
    else:
        task = backup_asa
        if args.proxy:
            task_kwargs["proxies"] = {"https": f"socks5://{args.proxy}", "http": f"socks5://{args.proxy}"}
        task_kwargs["file_path"] = backup_dir

    # Executing backup on devices:
    print(f"Device work start time: {datetime.datetime.now().isoformat()}")
    results = target_hosts.run(task=task, **task_kwargs)
    print(f"Device work end time: {datetime.datetime.now().isoformat()}")

    # Git Commit the changed backup files
    repo.git.add(all=True)  # Should be changed to explicitly add all filenames from the results... but that's harder
    repo.index.commit(message=f"Backup {datetime.datetime.now().isoformat()}", author=author)

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
        "--no_custom_creds",
        action="store_true",
        help="Disable user prompt to provide custom credentials, will only try environment variables of"
        " STOCKPILER_USER and STOCKPILER_PW",
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


def git_initialize(backup_dir: pathlib.Path) -> Repo:
    """
    Given a directory we're going to conduct backups on, either initialize it, or ensure it is ready for backups.
    Then return an initialized Git Repo object
    :param backup_dir: An instantiated pathlib.Path object where we want backups to go
    :return: An instantiated git.Repo object where we want backups to go
    """

    # Ensure this path exists, and create it if not
    if not backup_dir.is_dir():
        logger.info("%s does not exist, creating it", str(backup_dir))
        backup_dir.mkdir(parents=True)

    # Check if there's already a git repo there, create one if not
    if not pathlib.Path(backup_dir / ".git").is_dir():
        logger.info("%s exists, but does not appear to be a git repository, creating one there", str(backup_dir))
        repo = Repo.init(path=str(backup_dir))

    # Since the path exists, it has a `.git` dir, instantiate a repo object on that
    else:
        logger.info("%s/.git/ exists, reading repository", str(backup_dir))
        repo = Repo(path=str(backup_dir))

    return repo


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


def backup_asa(
    task: Task, file_path: pathlib.Path, backup_command: str = "more system:running-config", proxies: dict = None
) -> MultiResult:
    """
    Gather the text configuration from an ASA and write that to a file (overwriting any existing file by that name)
    :param task:
    :param file_path: An instantiated pathlib.Path object for the directory where we're going to write this
    :param backup_command: What command to execute for backup, defaults to `more system:running-config`
    :param proxies: Optional Dict of SOCKS proxies to use for HTTP connectivity
    :return: Return the Nornir Results of this action
    """

    http_mgmt_port = task.host.get("http_mgmt_port", 8443)
    http_management = task.host.get("http_management", False)

    # Check if we are using HTTP and if we can hit TCP port; skip if proxies, the TCP check won't do us any good.
    if http_management and proxies is not None:
        http_port_check_ok = True
    elif http_management:
        http_port_check_ok = task.run(task=tcp_ping, ports=[http_mgmt_port], timeout=1).result[http_mgmt_port]
    else:
        http_port_check_ok = False

    # Try and backup via HTTPS, fallback to
    while True:
        if http_port_check_ok:
            logger.debug("Attempting to backup %s via HTTPS", task.host)
            url = "https://{0}:{1}/admin/exec/".format(task.host.hostname, http_mgmt_port)
            asa_http_kwargs = {
                "method": "GET",
                "auth": (task.host.username, task.host.password),
                "headers": {"User-Agent": "ASDM"},
                "verify": False,
                "proxies": proxies,
            }
            # Save the config on the box
            task.run(task=http_method, url=url + quote_plus("wr mem"), **asa_http_kwargs)

            # Get a backup
            backup_results = task.run(task=http_method, url=url + quote_plus(backup_command), **asa_http_kwargs)

            if backup_results[0].response.ok:
                device_config = backup_results[0].response.text
                break

        logger.error("Failed to backup %s via HTTPS, falling back to SSH", task.host)
        # Save the config on the box:
        task.run(task=netmiko_save_config)
        # Gather a backup:
        backup_results = task.run(task=netmiko_send_command, command_string=backup_command)

        device_config = backup_results[0].result
        break

    file_name = pathlib.Path(file_path / f"{str(task.host)}.txt")
    result = task.run(task=files.write_file, filename=str(file_name), content=device_config)
    return result


if __name__ == "__main__":
    main()
