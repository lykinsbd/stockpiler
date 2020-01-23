# Stockpiler
Stockpiler gathers backups of network devices via Nornir - a Python based automation tool.

Stockpiler utilizes Nornir, Netmiko, and GitPython for a fully self-contained
 backup solution, and has been tested to function on Linux, MacOS, and Windows.

By default, it will read in device inventory/config from `/etc/stockpiler/`, and output backups to `/opt/stockpiler/`.
 Both are configurable by command line arguments.

# Installation

Notes:

1. Stockpiler utilizes a very recent release of Netmiko. This requires some specific handling (as outlined below),
   until other libraries update their dependencies.
2. Stockpiler requires Python 3.7 or higher.
3. Stockpiler utilizes Python Virtual Envrionments for isolation of the code/executable.

## Installation Steps

1. Create a directory for the Stockpiler virtual environment:
    `mkdir stockpiler`
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
6. Install Netmiko >= 3.0.0:
    `pip install 'netmiko>=3.0.0'`
7. Install Stockpiler:
    `pip install stockpiler`

# Configuration

As Stockpiler utilizes Nornir for the underlying inventory and task handling, see the Nornir
 documentation for more information on creating an inventory file or your configuration options

While we have provided a simple `nornir_conf.yaml` file, you are welcome to provide your own or customize
 the one provided by the package.
* https://nornir.readthedocs.io/en/latest/configuration/index.html

If you are using Windows (or wish to host your inventory in a different location than `/etc/stockpiler/inventory`), you
 will need to create a custom Nornir config file with your inventory paths.
