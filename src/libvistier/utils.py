import os
import sys
import json
import logging

from colorama import Fore, Style, init as colorama_init
from solders.rpc.responses import GetTransactionResp
from dotenv import load_dotenv

load_dotenv()
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

    if os.environ.get("DEBUG_LOG_FILE", "false") == "true":
        formatter = logging.Formatter('%(asctime)s [%(levelname)7s][%(name)s]: %(message)s')
        file_handler = logging.FileHandler("debug_log.txt", encoding='utf8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    logger.addHandler(stdout_handler)

    return logger


def dump_transaction_data(tx_response: GetTransactionResp):
    txs = json.loads(tx_response.to_json())
    print(json.dumps(txs, indent=4))


def split(list_, parts_cnt):
    # https://stackoverflow.com/questions/2130016/splitting-a-list-into-n-parts-of-approximately-equal-length
    k, m = divmod(len(list_), parts_cnt)
    return (list_[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in range(parts_cnt))
