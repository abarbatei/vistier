import json
from typing import List

from solders.rpc.responses import GetTransactionResp
from solders.transaction_status import EncodedTransactionWithStatusMeta
from .templates import MarketplaceInstructions, MarketplaceIds
from ..utils import get_logger

MAGIC_EDEN_ESCROW_WALLET = "1BWutmTvYPwDtmw9abTkS4Ssr8no61spGAvW1X6NDix"
logger = get_logger("VistierAPI")


class MagicEdenTransaction:

    @staticmethod
    def is_marketplace_tx(encoded_tx: EncodedTransactionWithStatusMeta) -> bool:
        return len(set(str(a) for a in encoded_tx.transaction.message.account_keys).intersection(
            MarketplaceIds.MagicEden.ids)) > 0

    def __init__(self, transaction_response: GetTransactionResp) -> None:
        #
        self.ids = MarketplaceIds.MagicEden.ids
        self.fee_ids = MarketplaceIds.MagicEden.fee_ids
        self.encoded_tx = transaction_response.value.transaction

        self.marketplace_fee_lamports = 0
        self.creators_fee_lamports = 0
        self.price_lamports = None
        self.type = None
        self.executed_instructions = None
        self.sold_nft_name = None
        self.nft_mint = None

        self.sell_signature = self.encoded_tx.transaction.signatures[0]
        self.sell_block_time = transaction_response.value.block_time

        self._process_logs()
        self._determine_transaction_type()

        self.seller_address = None
        self.buyer_address = None

        if self.is_sale() or self.is_listing():
            self._set_participants()

    @property
    def marketplace_name(self) -> str:
        return "MagicEden"

    @property
    def price(self) -> int:
        return self.price_lamports / 10 ** 9

    @property
    def marketplace_fee(self) -> int:
        return self.marketplace_fee_lamports / 10 ** 9

    @property
    def creators_fee(self) -> int:
        return self.creators_fee_lamports / 10 ** 9

    def is_sale(self) -> bool:
        return self.type == MarketplaceInstructions.Sale

    def is_listing(self) -> bool:
        return self.type == MarketplaceInstructions.Listing

    def is_escrow(self) -> bool:
        return self.is_listing()

    def _process_logs(self) -> None:
        """
        Can probably get this information using https://docs.solana.fm/v3-api-reference/enriched-transfers
        or Magic Eden API
        """
        all_elements = list()
        element = {"logs": []}
        for log_msg in self.encoded_tx.meta.log_messages:
            try:
                if not log_msg.startswith("Program "):
                    logger.warning(f"Unknown log message case: {log_msg}, skipping")
                    continue
                log_msg = log_msg.replace("Program ", "")

                if log_msg.startswith("return: "):
                    _, _, return_value = log_msg.split(" ")
                    element['return'] = return_value
                elif log_msg.startswith("log: "):
                    log_msg = log_msg.replace("log: ", "")

                    if log_msg.startswith("Instruction: "):
                        element['instruction'] = log_msg[len("Instruction: "):]
                        continue
                    if log_msg.startswith("{") and log_msg.endswith("}"):
                        element['extra_data'] = json.loads(log_msg)
                    element['logs'].append(log_msg)
                else:
                    parts = log_msg.split(" ")
                    if parts[0] in ['11111111111111111111111111111111']:
                        # skipping, pollutes with no added value and crashes code
                        continue

                    if len(parts) == 2:
                        program_id, status = parts
                        # only care about the status of the high level execution
                        if element.get("program_id") == program_id:
                            element["status"] = status
                    elif len(parts) == 3:
                        program_id, command, level = parts

                        if element.get("instruction"):
                            all_elements.append(element)

                        element = {"logs": [], 'depth': int(level[1:-1]), "program_id": program_id}
                    else:
                        # print(f"Untreated cases: {log_msg}")
                        # for example: TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA consumed 4645 of 463072 compute units
                        pass

            except Exception as e:
                logger.error(f"exception when processing line: {log_msg}:\n{e.args}")
        if element.get("instruction"):
            all_elements.append(element)

        self.executed_instructions = all_elements

    def _determine_transaction_type(self) -> None:

        has_execute_sell = False
        has_sell = False
        has_cancel_buy = False
        has_buy = False
        price = None
        for execution in self.executed_instructions:
            # in some cases the price is printed in a Sell in others in a CloseAccount
            price = execution.get('extra_data', {}).get('price')

            if execution['instruction'] == "ExecuteSale":
                has_execute_sell = True
            if execution['instruction'] == "Sell":
                has_sell = True
            if execution['instruction'] == "CancelBuy":
                has_cancel_buy = True
            if execution['instruction'] == "Buy":
                has_buy = True

        self.price_lamports = price

        if has_execute_sell:
            self.type = MarketplaceInstructions.Sale
        elif has_sell:
            if 1 <= len(self.executed_instructions) <= 2:
                ins_0 = self.executed_instructions[0]
                if ins_0['instruction'] == "Sell":
                    self.type = MarketplaceInstructions.Listing
        elif has_cancel_buy:
            self.type = MarketplaceInstructions.CancelOffer
        elif has_buy:
            if len(self.executed_instructions) == 1:
                ins_0 = self.executed_instructions[0]
                if ins_0['instruction'] == "Buy":
                    self.type = MarketplaceInstructions.PlaceOffer
        else:
            self.type = MarketplaceInstructions.Unknown

    def calculate_fees(self, treasuries_accounts: List[str]) -> None:
        pre_balances = self.encoded_tx.meta.pre_balances
        post_balances = self.encoded_tx.meta.post_balances

        marketplace_index = -1
        treasury_index = -1

        for index, account in enumerate(self.encoded_tx.transaction.message.account_keys):
            if str(account) in self.fee_ids:
                marketplace_index = index
            if str(account) in treasuries_accounts:
                treasury_index = index

        if marketplace_index > 0:
            self.marketplace_fee_lamports = int(post_balances[marketplace_index] - pre_balances[marketplace_index])

        if treasury_index > 0:
            self.creators_fee_lamports = int(post_balances[treasury_index] - pre_balances[treasury_index])

    def _set_participants(self):
        pre_token_balances = self.encoded_tx.meta.pre_token_balances
        post_token_balances = self.encoded_tx.meta.post_token_balances
        if len(pre_token_balances) != 1 or len(post_token_balances) != 1:
            logger.warning("Can not determine participants in exchange")
            return
        self.nft_mint = pre_token_balances[0].mint
        self.seller_address = pre_token_balances[0].owner
        self.buyer_address = post_token_balances[0].owner

    def to_dict(self):
        return {
            'signature': str(self.sell_signature),
            'block_time': self.sell_block_time,
            "mint": str(self.nft_mint),
            'name': self.sold_nft_name,
            'source': self.marketplace_name,
            'price': self.price_lamports,
            'creator_fee_paid': self.creators_fee_lamports,
            'market_fee_paid': self.marketplace_fee_lamports,
            'seller': str(self.seller_address) if self.seller_address else None,
            'buyer': str(self.buyer_address) if self.buyer_address else None,
            'type': self.type
        }
