import json

from solders.transaction_status import EncodedTransactionWithStatusMeta

from marketplace.templates import MarketplaceInstructions, MarketplaceIds


class MagicEdenTransaction:

    @staticmethod
    def is_marketplace_tx(encoded_tx: EncodedTransactionWithStatusMeta):
        return len(set(str(a) for a in encoded_tx.transaction.message.account_keys).intersection(
            MarketplaceIds.MagicEden.ids)) > 0

    def __init__(self, encoded_tx: EncodedTransactionWithStatusMeta):
        self.ids = MarketplaceIds.MagicEden.ids
        self.encoded_tx = encoded_tx

        self.executed_instructions = None
        self._process_logs()

        self.price_lamports = None
        self.type = None
        self._determine_transaction_type()

    @property
    def price(self):
        return self.price_lamports / 10 ** 9

    def is_sale(self):
        return self.type == MarketplaceInstructions.Sale

    def _process_logs(self):
        """
        Good example here: https://solana.fm/tx/5viR6rqH2CEieDQMEk11JcNN18R5vnhg8iAL8zH4SwNFvx93ik243aTyYQRQUhAs8HnfrcfBRzrt3wFKtxCaTWWW?cluster=mainnet-qn1
        """
        all_elements = list()
        element = {"logs": []}
        for log_msg in self.encoded_tx.meta.log_messages:
            try:
                if not log_msg.startswith("Program "):
                    print(f"Unknown log message case: {log_msg}, skipping")
                    continue
                log_msg = log_msg.replace("Program ", "")

                if log_msg.startswith("log: "):
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
                        # skipping, polutes with no added value
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
                        pass

            except Exception as e:
                print(f"exception when processing line: {log_msg}:\n{e.args}")
        if element.get("instruction"):
            all_elements.append(element)

        self.executed_instructions = all_elements
        # Magic EDEN tx fees rFqFJ9g7TGBD8Ed7TPDnvGKZ5pWLPDyxLcvcH2eRCtt
        # https://dune.com/queries/825072/1445379 platform fee account

        # get index of platform fee account addresses and see balance changes, before/after

    def _determine_transaction_type(self):
        has_execute_sell = False
        has_sell = False
        price = -1
        for execution in self.executed_instructions:
            if execution['instruction'] == "ExecuteSale":
                has_execute_sell = True
            if execution['instruction'] == "Sale":
                has_sell = True
            if execution['instruction'] == "Buy":
                price = execution['extra_data']['price']

        self.price_lamports = price
        if has_execute_sell:
            self.type = MarketplaceInstructions.Sale
        elif has_sell:
            self.type = MarketplaceInstructions.List
        else:
            self.type = MarketplaceInstructions.Unknown