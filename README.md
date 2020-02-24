# Stockpiler
Stockpiler gathers network device configurations and stores them in a local Git repository.

Stockpiler utilizes Nornir, Netmiko, and GitPython for a fully self-contained
 backup solution, and has been tested to function on Linux, MacOS, and Windows.

## Using Stockpiler

Once installed in an environment Stockpiler can be called directly/ad-hoc, or more commonly, by a Cron Job or other 
 system scheduling tool such as creating a Systemd service.

The most basic execution of Stockpiler would be simply executing the following:

    stockpiler

This will read the credentials from the Inventory or the environment, then attempt a backup of devices in the Nornir
 Inventory at `/etc/stockpiler/inventory` and put the resultant backups into a Git repository in `/opt/stockpiler`.

However, there are many configuration options available as well to specify Inventory location, provide custom credentials,
 utilize a SOCKS proxy, and so forth.

Another, more complex execution example could be:

     stockpiler \
     --inventory /home/brett/mah_inventory \
     --output /home/brett/stockpiler_backups \
     --proxy localhost:8000 \
     --log_level DEBUG \
     --logging_dir /home/brett/stockpiler_logs \
     --prompt_for_credentials
 
See `stockpiler --help` for full command information.

### Credentials

By default, Stockpiler will look in the follwoing three Environment Variables for the username/password/enable_password to use:

* `STOCKPILER_USER`
* `STOCKPILER_PW`
* `STOCKPILER_ENABLE`

Note that if `STOCKPILER_ENABLE` is not set, Stockpiler will utilize the `STOCKPILER_PW` for both values.

In addition, if these values are not set, you must tell Stockpiler to prompt you for credentials with the argument
 `--prompt_for_credentials`.  By default **it will not do so, as it is intended to be run in a non-interactive scenario**,
  i.e. by a Cron job, and will simply raise an IOError and exit.


### Configuration

As Stockpiler utilizes Nornir for the underlying inventory and task handling, see the 
 [Nornir documentation](https://nornir.readthedocs.io/en/latest/tutorials/intro/inventory.html) for more information
 on creating an inventory file or your configuration options

While we have provided a simple `nornir_conf.yaml` file, you are welcome to provide your own or customize
 the one provided by the package.
See the [Nornir documentation on Configuration](https://nornir.readthedocs.io/en/latest/configuration/index.html)
 for more information on the options available to you.

If you are using Windows (or wish to host your inventory in a different location than `/etc/stockpiler/inventory`), you
 will need to create a custom Nornir config file with your inventory paths.


## Installation

Notes:

1. Stockpiler utilizes a very recent release of Netmiko. This requires some specific handling (as outlined below),
   until other libraries update their dependencies.
2. Stockpiler **requires Python 3.7 or higher**.
3. Stockpiler utilizes Python Virtual Environments for isolation of the code/environment.

### Installation Steps

1. Create a directory for the Stockpiler virtual environment:
    `mkdir stockpiler`
2. Create a virtual environment in that directory:
    `python3 -m venv stockpiler`
3. Navigate to the new directory and activate it:
    `cd stockpiler;source bin/activate`
4. Install Stockpiler:
    `pip install stockpiler`
5. Edit the dependencies, this will require you to find the Napalm and Nornir `METADATA` files in your virtual
 environment:
    * Paths should be similar to:
        * `lib/python3.7/site-packages/napalm-2.5.0.dist-info/METADATA`
    * In each file, find the lines similar to below that reference Netmiko:
        * `Requires-Dist: netmiko (==2.4.2)`
    * Edit it to include 3.0.0, similar to the below:
        * `Requires-Dist: netmiko (>=2.4.2)`
