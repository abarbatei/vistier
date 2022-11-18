import json
from typing import List

from solders.transaction_status import EncodedTransactionWithStatusMeta
from .templates import MarketplaceInstructions, MarketplaceIds


class MagicEdenTransaction:

    @staticmethod
    def is_marketplace_tx(encoded_tx: EncodedTransactionWithStatusMeta) -> bool:
        return len(set(str(a) for a in encoded_tx.transaction.message.account_keys).intersection(
            MarketplaceIds.MagicEden.ids)) > 0

    def __init__(self, encoded_tx: EncodedTransactionWithStatusMeta) -> None:
        self.ids = MarketplaceIds.MagicEden.ids
        self.fee_ids = MarketplaceIds.MagicEden.fee_ids
        self.encoded_tx = encoded_tx

        self.marketplace_fee_lamports = 0
        self.creators_fee_lamports = 0

        self.executed_instructions = None
        self._process_logs()

        self.price_lamports = None
        self.type = None
        self._determine_transaction_type()

        self.sold_nft_mint_address = None
        self.sold_nft_name = None
        self.sell_signature = None
        self.sell_block_time = None

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

    def _process_logs(self) -> None:
        """
        Good example here: https://solana.fm/tx/5viR6rqH2CEieDQMEk11JcNN18R5vnhg8iAL8zH4SwNFvx93ik243aTyYQRQUhAs8HnfrcfBRzrt3wFKtxCaTWWW?cluster=mainnet-qn1
        Can probably get this information using https://docs.solana.fm/v3-api-reference/enriched-transfers
        """
        all_elements = list()
        element = {"logs": []}
        for log_msg in self.encoded_tx.meta.log_messages:
            try:
                if not log_msg.startswith("Program "):
                    print(f"Unknown log message case: {log_msg}, skipping")
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
                print(f"exception when processing line: {log_msg}:\n{e.args}")
        if element.get("instruction"):
            all_elements.append(element)

        self.executed_instructions = all_elements

    def _determine_transaction_type(self) -> None:
        has_execute_sell = False
        has_sell = False
        price = None
        for execution in self.executed_instructions:
            if execution['instruction'] == "ExecuteSale":
                has_execute_sell = True
            if execution['instruction'] == "Sale":
                has_sell = True
            if execution['instruction'] == "Buy":
                # when a buy was attempted with not enough funds this makes extra_data unset
                price = execution.get('extra_data', {}).get('price')

        self.price_lamports = price
        if has_execute_sell:
            self.type = MarketplaceInstructions.Sale
        elif has_sell:
            self.type = MarketplaceInstructions.List
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
