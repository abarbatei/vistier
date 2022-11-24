import os
import yaml
from flask import Flask, request
from dotenv import load_dotenv

from libvistier.entrypoint import api_entrypoint, api_process_signature

load_dotenv()
app = Flask(__name__)


def init_settings():
    cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")
    with open(cfg_path, "r") as input_stream:
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
    contract_address = request.args.get('address')
    candy_machine_ids = request.args.getlist('cmid')
    response = await api_entrypoint(settings, contract_address, candy_machine_ids)
    return response, 200, {'Content-Type': 'application/json; charset=utf-8'}


@app.route('/marketplace-signature/<signature>', methods=['GET'])
async def marketplace_signature(signature):
    collection_treasuries = request.args.getlist('treasury')
    response = await api_process_signature(signature, collection_treasuries)
    return response, 200, {'Content-Type': 'application/json; charset=utf-8'}


if __name__ == '__main__':
    app.run()
