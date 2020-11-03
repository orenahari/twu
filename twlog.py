import logging


class TimeWatchLogger(logging.Logger):
    """
    Subclass for the logger - predefined
    """

    def __init__(self, log_level=logging.DEBUG):
        super().__init__(name='time_watch_logger')
        self.handlers = []
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        # console_handler.setFormatter(logging.Formatter('%(levelname)8s - %(asctime)s - %(module)s - %(message)s'))
        console_handler.setFormatter(TWFormatter())
        self.addHandler(console_handler)


class TWFormatter(logging.Formatter):
    yellow = "\x1b[33;21m"
    red = "\x1b[31;21m"
    reset = "\x1b[0m"

    def format(self, record):

        if record.levelno == logging.INFO:
            formatter = logging.Formatter('%(levelname)8s - %(asctime)s - %(module)6s - %(message)s')
            return formatter.format(record)
        elif record.levelno == logging.DEBUG:
            formatter = logging.Formatter('%(levelname)8s - %(asctime)s - %(module)6s       + %(message)s')
            return formatter.format(record)

# class CustomFormatter(logging.Formatter):
#     """Logging Formatter to add colors and count warning / errors"""
#
#     grey = "\x1b[38;21m"
#     yellow = "\x1b[33;21m"
#     red = "\x1b[31;21m"
#     bold_red = "\x1b[31;1m"
#     reset = "\x1b[0m"
#     format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"
#
#     FORMATS = {
#         logging.DEBUG: grey + format + reset,
#         logging.INFO: grey + format + reset,
#         logging.WARNING: yellow + format + reset,
#         logging.ERROR: red + format + reset,
#         logging.CRITICAL: bold_red + format + reset
#     }
#
#     def format(self, record):
#         log_fmt = self.FORMATS.get(record.levelno)
#         formatter = logging.Formatter(log_fmt)
#         return formatter.format(record)
