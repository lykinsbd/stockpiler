#!/usr/bin/env python3

"""
Process our backup tasks/results within the Nornir processor framework.

See https://nornir.readthedocs.io/en/latest/tutorials/intro/processors.html for more information.
"""

import csv
import datetime
import logging
import pathlib


from git import Actor, Repo
from nornir.core.inventory import Host
from nornir.core.processor import Processor
from nornir.core.task import AggregatedResult, MultiResult, Task


logger = logging.getLogger("stockpiler")


class ProcessBackups(Processor):
    def __init__(self, **kwargs) -> None:
        """
        Initialize some base values for this processor
        :param kwargs:
        """

        self.task_start_time = datetime.datetime.utcnow()
        super().__init__(**kwargs)

    def task_started(self, task: Task) -> None:

        print(f"Backup Task Start Time: {self.task_start_time.isoformat()}")

    def task_completed(self, task: Task, result: AggregatedResult) -> None:

        # Process our results into a CSV and write it to the backups directory.

        task_end_time = datetime.datetime.utcnow()
        print(f"Backup Task End Time: {task_end_time.isoformat()}")
        print(f"Backup Task Elapsed Time: {task_end_time - self.task_start_time}")

        # Plumb up Git repository
        repo = self.git_initialize(backup_dir=task.params["backup_dir"])
        author = Actor(name="Stockpiler", email="stockpiler@localhost.local")

        csv_out = pathlib.Path(f"{task.params['backup_dir']}/results.csv")
        print(f"Putting results into a CSV at {csv_out}")
        with csv_out.open(mode="w") as output_file:
            fieldnames = [i for i in next(result[x] for x in result)[0].result.keys() if i not in ["device_config"]]

            writer = csv.DictWriter(output_file, fieldnames=fieldnames)

            writer.writeheader()
            for host in result.keys():
                # Don't try to write this if it's not a dict.
                if not isinstance(result[host][0].result, dict):
                    continue
                writer.writerow({k: v for (k, v) in result[host][0].result.items() if k not in ["device_config"]})

        # Git Commit the changed backup files
        repo.git.add(
            all=True
        )  # Should be changed to explicitly add all filenames from the results... but that's harder
        repo.index.commit(message=f"Backup {datetime.datetime.utcnow().isoformat()}", author=author)

    def task_instance_started(self, task: Task, host: Host) -> None:
        pass  # This is required for implementation, but at this time we're taking no action here

    def task_instance_completed(self, task: Task, host: Host, result: MultiResult) -> None:
        print(f"  - {host.name}: Backup Successful: {not result.failed}")

    def subtask_instance_started(self, task: Task, host: Host) -> None:
        pass  # This is required for implementation, but at this time we're taking no action here

    def subtask_instance_completed(self, task: Task, host: Host, result: MultiResult) -> None:
        pass  # This is required for implementation, but at this time we're taking no action here

    # Helper functions, not core to Nornir internals of handling task stages.
    @staticmethod
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
