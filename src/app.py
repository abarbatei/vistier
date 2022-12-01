#!/usr/bin/env python3
import os

import yaml
from flask import Flask, request
from dotenv import load_dotenv
from waitress import serve

from libvistier import api_search_wallet_for_nfts, api_process_signature
from libvistier.utils import get_logger

logger = get_logger("VistierAPI")

load_dotenv()
app = Flask(__name__)


def init_settings():
    cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")
    with open(cfg_path, "rt") as input_stream:
        yaml_configs = yaml.safe_load(input_stream)

    return {
        "escrow_tx_workers": yaml_configs['ESCROW_TX_PROCESSING_WORKERS'],
        "escrow_tx_to_process": yaml_configs['ESCROW_TX_TO_PROCESS'],
        "escrow_max_tx_to_process": yaml_configs['ESCROW_MAX_TX_TO_PROCESS'],

        "sales_tx_workers": yaml_configs['SALES_TX_PROCESSING_WORKERS'],
        "sales_tx_to_process": yaml_configs['SALES_TX_TO_PROCESS_PER_NFT'],
        "sales_max_tx_to_process": yaml_configs['SALES_NFT_MAX_TX_TO_PROCESS'],
        "sales_max_nft_to_inspect": yaml_configs['SALES_NFT_MAX_TO_INSPECT'],
    }


settings = init_settings()


@app.route('/wallet-status', methods=['GET'])
async def wallet_status():
    response = {
        "status": "ok",
        "content": dict()
    }

    contract_address = request.args.get('address')
    candy_machine_ids = request.args.getlist('cmid')

    try:
        response['status'] = "ok"
        response['content'] = await api_search_wallet_for_nfts(settings, contract_address, candy_machine_ids)
        status_code = 200
    except ValueError as e:
        response['status'] = "error"
        response['content'] = " ".join(e for e in e.args)
        status_code = 500
    except Exception:
        response['status'] = "error"
        response['content'] = "Unexpected internal error"
        status_code = 500
        logger.exception(f"Error while parsing contract address: {contract_address} and with cmids: {candy_machine_ids}")

    return response, status_code, {'Content-Type': 'application/json; charset=utf-8'}


@app.route('/marketplace-signature/<signature>', methods=['GET'])
async def marketplace_signature(signature):
    response = {
        "status": "ok",
        "content": dict()
    }
    try:
        collection_treasuries = request.args.getlist('treasury')
        response['status'] = "ok"
        response['content'] = await api_process_signature(signature, collection_treasuries)
        status_code = 200
    except Exception:
        response['status'] = "error"
        response['content'] = "Unexpected internal error"
        logger.exception(f"Error while parsing signature {signature}")
        status_code = 500

    return response, status_code, {'Content-Type': 'application/json; charset=utf-8'}

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    serve(app, host='0.0.0.0', port=port)
