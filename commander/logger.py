import logging
from os import path


class Logger:
    def __init__(self, log_level, log_dir, log_name):
        self.core = logging.getLogger("Commander")
        self.core.setLevel(log_level)
        self.log_path = path.join(log_dir, log_name)
        if not path.isfile(self.log_path):
            try:
                open(self.log_path, 'a').close()
            except PermissionError:
                print("Running RATServer requires root like privileges, permission denied when creating path for log"
                      " file. Please run as sudo!")
                exit(3)
            except Exception as err:
                print("Unexpected error has occurred while creating the logger for server: {}".format(err))
                exit(4)
        self.fh = logging.FileHandler(self.log_path)
        self.fh.setLevel(log_level)
        self.log_formatter = logging.Formatter('%(asctime)s - %(name)s::%(module)s - %(levelname)s - %(message)s')
        self.fh.setFormatter(self.log_formatter)
        self.core.addHandler(self.fh)
