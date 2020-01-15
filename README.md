# Stockpiler
Stockpiler gathers backups of network devices via Nornir, a Python based automation tool.

Stockpiler utilizes Nornir, Netmiko, and GitPython for a fully self-contained
 backup solution.

It will read in device inventory/config from `/etc/stockpiler/`, and
 output backups to `/opt/stockpiler/` by default.
 Both are configurable by command line arguments.

# Installation

Installation at this time, is from source only,
Pypi packages will be avalible with 1.0 relase.

## Installation Caveats

1. Stockpiler currently utilizes an upstream/develop branch of Netmiko.
This requires some specific handling (as outlined below), until Netmiko 3.0.0 is released
and other libraries update their dependencies.
2. Stockpiler requires Python 3.7 or higher.

## Installation Steps

1. Clone the code for Stockpiler to a directory:
    `git clone https://github.com/rackerlabs/stockpiler.git`
2. Create a virtual environment in that directory:
    `python3 -m venv stockpiler`
3. Navigate to the new directory and activate it:
    `cd stockpiler;source bin/activate`
4. Install Nornir:
    `pip install nornir`
5. Edit the dependencies, this will require you to find the Napalm and Nornir `METADATA` files in your virtual
 environment:
    * Paths should be similar to:
        * `lib/python3.7/site-packages/napalm-2.5.0.dist-info/METADATA`
        * `lib/python3.7/site-packages/nornir-2.3.0.dist-info/METADATA`
    * In each file, find the lines similar to below that reference Netmiko:
        * `Requires-Dist: netmiko (==2.4.2)`
        * `Requires-Dist: netmiko (>=2.3.3,<3.0.0)`
    * Edit it to include 3.0.0, similar to the below:
        * `Requires-Dist: netmiko (>=2.4.2)`
        * `Requires-Dist: netmiko (>=2.3.3)`
6. Install Netmiko 3.0.0 from Develop branch:
    `pip install -e 'git+https://github.com/ktbyers/netmiko.git@develop#egg=netmiko'`
7. Install Stockpiler:
    `pip install .`

# Configuration

As Stockpiler utilizes Nornir for the underlying inventory and task handling, see the Nornir
 documentation for more information on creating an inventory file or your configuration options

While we have provided a simple `nornir_conf.yaml` file, you are welcome to provide your own or customize
 the one provided by the package.
* https://nornir.readthedocs.io/en/latest/configuration/index.html