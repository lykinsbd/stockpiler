# stockpiler
Stockpiler gathers backups of network devices via Nornir, a Python based automation tool.

Stockpiler utilizes Nornir, Netmiko, and GitPython for a fully self-contained
 backup solution.

It will read in device inventory/config from `/etc/stockpiler/`, and
 output backups to `/opt/stockpiler/` by default.
 Both are configurable by command line arguments.

