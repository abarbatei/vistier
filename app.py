from flask import Flask, request

from entrypoint import api_entrypoint, api_process_signature
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)


@app.route('/')
def index():
    return 'Home page'


@app.route('/wallet-status', methods=['GET'])
async def wallet_status():
    contract_address = request.args.get('address')
    candy_machine_ids = request.args.getlist('cmid')
    response = await api_entrypoint(contract_address, candy_machine_ids)
    return response, 200, {'Content-Type': 'application/json; charset=utf-8'}


@app.route('/marketplace-signature/<signature>', methods=['GET'])
async def marketplace_signature(signature):
    collection_treasuries = request.args.getlist('treasury')
    response = await api_process_signature(signature, collection_treasuries)
    return response, 200, {'Content-Type': 'application/json; charset=utf-8'}


if __name__ == '__main__':
    app.run()
