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


class ProcessStockpiles(Processor):
    def __init__(self, **kwargs) -> None:
        """
        Initialize some base values for this processor
        :param kwargs:
        """

        self.task_start_time = datetime.datetime.utcnow()
        super().__init__(**kwargs)

    def task_started(self, task: Task) -> None:
        """
        When the overall stockpile task starts, print the start time.
        :param task:
        :return:
        """

        print(f"Backup Task Start Time: {self.task_start_time.isoformat()}")

    def task_completed(self, task: Task, result: AggregatedResult) -> None:
        """
        When the overall stockpile task finishes, do the following:
            1) Print finish time and calculate run time
            2) Initialize our Git repository
            3) Write a CSV report on this backup task
            4) Add all written files to this commit, and commit it
        :param task:
        :param result:
        :return:
        """

        # Process our results into a CSV and write it to the stockpile output directory.

        task_end_time = datetime.datetime.utcnow()
        print(f"Backup Task End Time: {task_end_time.isoformat()}")
        print(f"Backup Task Elapsed Time: {task_end_time - self.task_start_time}")

        # Plumb up Git repository
        repo = self.git_initialize(stockpile_directory=task.params["stockpile_directory"])
        author = Actor(name="Stockpiler", email="stockpiler@localhost.local")

        csv_out = pathlib.Path(f"{task.params['stockpile_directory']}/results.csv")
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

        # Git Commit the changed/stockpiled files
        repo.git.add(
            all=True
        )  # Should be changed to explicitly add all filenames from the results... but that's harder
        repo.index.commit(message=f"Stockpile Built at {datetime.datetime.utcnow().isoformat()}", author=author)

    def task_instance_started(self, task: Task, host: Host) -> None:
        pass  # This is required for implementation, but at this time we're taking no action here

    def task_instance_completed(self, task: Task, host: Host, result: MultiResult) -> None:
        """
        Print Successful/Failed for each individual stockpile attempt.
        :param task:
        :param host:
        :param result:
        :return:
        """
        print(f"  - {host.name}: Stockpile {'Failed' if result.failed else 'Successful'}")

    def subtask_instance_started(self, task: Task, host: Host) -> None:
        pass  # This is required for implementation, but at this time we're taking no action here

    def subtask_instance_completed(self, task: Task, host: Host, result: MultiResult) -> None:
        pass  # This is required for implementation, but at this time we're taking no action here

    # Helper functions, not core to Nornir internals of handling task stages.
    @staticmethod
    def git_initialize(stockpile_directory: pathlib.Path) -> Repo:
        """
        Given a directory we're going to stash backups/stockpile into, either initialize it,
        or ensure it is ready for stockpiling.
        Then return an initialized Git Repo object
        :param stockpile_directory: An instantiated pathlib.Path object where we want the stockpile to go
        :return: An instantiated git.Repo object where we want backups to go
        """

        # Ensure this path exists, and create it if not
        if not stockpile_directory.is_dir():
            logger.info("%s does not exist, creating it", str(stockpile_directory))
            stockpile_directory.mkdir(parents=True)

        # Check if there's already a git repo there, create one if not
        if not pathlib.Path(stockpile_directory / ".git").is_dir():
            logger.info(
                "%s exists, but does not appear to be a git repository, creating one there", str(stockpile_directory)
            )
            repo = Repo.init(path=str(stockpile_directory))

        # Since the path exists, it has a `.git` dir, instantiate a repo object on that
        else:
            logger.info("%s exists, reading repository", str(pathlib.Path(stockpile_directory / ".git")))
            repo = Repo(path=str(stockpile_directory))

        return repo
