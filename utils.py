import json
import logging
import sys
from colorama import Fore, Style, init as colorama_init
from solders.rpc.responses import GetTransactionResp

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


def get_logger(name):

    logger = logging.getLogger(name)

    if logger.hasHandlers():
        return logger

    logger.setLevel(logging.DEBUG)

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.INFO)
    stdout_handler.setFormatter(CustomFormatter())

    logger.addHandler(stdout_handler)

    return logger


def dump_transaction_data(tx_response: GetTransactionResp):
    txs = json.loads(tx_response.to_json())
    print(json.dumps(txs, indent=4))