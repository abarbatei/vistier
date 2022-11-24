import logging
import sys
from colorama import Fore, Style, init as colorama_init

colorama_init()


class CustomFormatter(logging.Formatter):

    print_format = "%(asctime)s | %(message)s"

    FORMATS = {
        logging.DEBUG: Fore.WHITE + print_format + Style.RESET_ALL,
        logging.INFO: Fore.LIGHTWHITE_EX + print_format + Style.RESET_ALL,
        logging.WARNING: Fore.LIGHTYELLOW_EX + print_format + Style.RESET_ALL,
        logging.ERROR: Fore.LIGHTRED_EX + print_format + Style.RESET_ALL,
        logging.CRITICAL: Fore.LIGHTRED_EX + print_format + Style.RESET_ALL
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


def get_logger(name, file_name=None):

    if not file_name:
        file_name = 'debug_log.txt'
    logger = logging.getLogger(name)

    if logger.hasHandlers():
        return logger

    logger.setLevel(logging.DEBUG)

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.INFO)
    stdout_handler.setFormatter(CustomFormatter())

    formatter = logging.Formatter('%(asctime)s [%(levelname)7s][%(name)s]: %(message)s')
    file_handler = logging.FileHandler(file_name, encoding='utf8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stdout_handler)

    return logger