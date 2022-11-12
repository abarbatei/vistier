import inspect
import json
from typing import List, Union
from functools import reduce
from solana.publickey import PublicKey
from solders.transaction_status import EncodedTransactionWithStatusMeta


METADATA_PROGRAM_ID = PublicKey('metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s')
SYSTEM_PROGRAM_ID = PublicKey('11111111111111111111111111111111')
SYSVAR_RENT_PUBKEY = PublicKey('SysvarRent111111111111111111111111111111111')
ASSOCIATED_TOKEN_ACCOUNT_PROGRAM_ID = PublicKey('ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL')
TOKEN_PROGRAM_ID = PublicKey('TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA')


# from https://dune.com/queries/1308092 these must be found in account keys
class MarketplaceIds:
    class MagicEden:
        ids = {
            "MEisE1HzehtrDpAAT8PnLHjpSSkRYakotTuJRPjTpo8",  # Magic Eden v1
            "M2mx93ekt1fmXSVkTrUL9xVFHkmME8HTUi5Cyc5aF7K",
            # https://dune.com/queries/825072/1445379
            "rFqFJ9g7TGBD8Ed7TPDnvGKZ5pWLPDyxLcvcH2eRCtt",  # platform fee account
            "2NZukH2TXpcuZP4htiuT8CFxcaQSWzkkR6kepSWnZ24Q"  # platform fee account
        }

    class Metalplex:
        ids = {
            "cndyAnrLdpjq1Ssp1z8xxDsB8dxe7u4HL5Nxi2K5WXZ",  # Metaplex NFT Candy Machine v1
            "cndy3Z4yapfJBmL3ShUp5exZKqR3z33thTzeNMm2gRZ"
        }

    class Solanart:
        ids = {
          "CJsLwbP1iu5DuUikHEJnLfANgKy6stB2uFgvBBHoyxwz"
        }

    class DigitalEyes:
        ids = {
            "A7p8451ktDCHq5yYaHczeLMYsjRsAkzc3hCXcSrwYHU7",  # DigitalEyes NFT Marketplace
            "7t8zVJtPCFAqog1DcnB6Ku1AVKtWfHkCiPi1cAvcJyVF"   # DigitalEyes Direct Sell
        }

    class Solsea:
        ids = {
            "617jbWo616ggkDxvW1Le8pV38XLbVSyWY8ae6QUmGBAU"
        }

    class AlphaArt:
        ids = {
            "HZaWndaNWHFDd9Dhk5pqUUtsmoBCqzb1MLu3NAh1VX6B"
        }

    class ExchangeArt:
        ids = {
            "AmK5g2XcyptVLCFESBCJqoSfwV3znGoVYQnqEnaAZKWn"
        }

    class OpenSea:
        ids = {
            "3o9d13qUvEuuauhFrVom1vuCzgNsJifeaBYDPquaT73Y",
            "pAHAKoTJsAAe2ZcvTZUxoYzuygVAFAmbYmJYdWT886r",
            # https://dune.com/queries/825072/1445379
            "8mcjXbJ8j4VryYFNpcBCFS37Au8zVYU53WTVaruJWcKt"  # platform fee account
        }


marketplaces_ids = reduce(set.union, [cls_attribute.ids for cls_attribute in MarketplaceIds.__dict__.values()
                                      if inspect.isclass(cls_attribute)])


def is_marketplace(account_keys: List[Union[PublicKey, PublicKey]]):
    return len(set(str(a) for a in account_keys).intersection(marketplaces_ids)) > 0


class MarketplaceInstructions:
    Sell = "Sell"  # actually list
    ExecuteSale = "ExecuteSale"
    Buy = "Buy"
    Deposit = "Deposit"
    CancelBuy = "CancelBuy"
    CancelSell = "CancelSell"
    Revoke = "Revoke"
    Withdraw = "Withdraw"


class MagicEdenTransaction:

    @staticmethod
    def is_marketplace_tx(encoded_tx: EncodedTransactionWithStatusMeta):
        return len(set(str(a) for a in encoded_tx.transaction.message.account_keys).intersection(
            MarketplaceIds.MagicEden.ids)) > 0

    def __init__(self, encoded_tx: EncodedTransactionWithStatusMeta):
        self.ids = MarketplaceIds.MagicEden.ids
        self.encoded_tx = encoded_tx

        self.instruction = None
        self.extra_data = dict()

        self._process_logs()

    @property
    def price_lamports(self):
        return self.extra_data['price']

    @property
    def price(self):
        return self.price_lamports / 10e9

    def _process_logs(self):
        """
        DigitalEyes

        https://dune.com/queries/1308092
        Example magic Eden Sell (list)
        "logMessages": [
            "Program M2mx93ekt1fmXSVkTrUL9xVFHkmME8HTUi5Cyc5aF7K invoke [1]",
            "Program log: Instruction: Sell",
            "Program log: {\"price\":65000000000,\"seller_expiry\":-1}",
            "Program M2mx93ekt1fmXSVkTrUL9xVFHkmME8HTUi5Cyc5aF7K consumed 35459 of 200000 compute units",
            "Program M2mx93ekt1fmXSVkTrUL9xVFHkmME8HTUi5Cyc5aF7K success"
        ],

        :return:
        """

        action = {
            "program": "",
            "invokes": "",
            "instruction": "",
            "status": "",
        }

        for log_msg in self.encoded_tx.meta.log_messages:
            if log_msg.startswith("Program log: "):
                log_msg = log_msg.replace("Program log: ", "")
                if log_msg.startswith("Instruction:"):
                    self.instruction = log_msg[len("Instruction:")+1:]
                if log_msg.startswith("{") and log_msg.endswith("}"):
                    self.extra_data = json.loads(log_msg)

        # Magic EDEN tx fees rFqFJ9g7TGBD8Ed7TPDnvGKZ5pWLPDyxLcvcH2eRCtt
        # https://dune.com/queries/825072/1445379 platform fee account

        # get index of platform fee account addresses and see balance changes, before/after




