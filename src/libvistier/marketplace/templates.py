import inspect
from functools import reduce

from solana.publickey import PublicKey


class MarketplaceInstructions:
    Sale = "Sale"
    CancelSell = "CancelSell"
    PlaceOffer = "PlaceOffer"
    CancelOffer = "CancelOffer"
    Listing = "Listing"
    CancelListing = "CancelListing"
    Unknown = "Unknown"


# from https://dune.com/queries/1308092 these must be found in account keys


class MarketplaceIds:
    class MagicEden:
        ids = {
            "MEisE1HzehtrDpAAT8PnLHjpSSkRYakotTuJRPjTpo8",  # Magic Eden v1
            "M2mx93ekt1fmXSVkTrUL9xVFHkmME8HTUi5Cyc5aF7K",

        }
        fee_ids = {
            # https://dune.com/queries/825072/1445379
            "rFqFJ9g7TGBD8Ed7TPDnvGKZ5pWLPDyxLcvcH2eRCtt",  # platform fee account
            "2NZukH2TXpcuZP4htiuT8CFxcaQSWzkkR6kepSWnZ24Q"  # platform fee account
        }
        escrow_ids = {
            "1BWutmTvYPwDtmw9abTkS4Ssr8no61spGAvW1X6NDix"
        }

    class Metalplex:
        ids = {
            "cndyAnrLdpjq1Ssp1z8xxDsB8dxe7u4HL5Nxi2K5WXZ",  # Metaplex NFT Candy Machine v1
            "cndy3Z4yapfJBmL3ShUp5exZKqR3z33thTzeNMm2gRZ"
        }
        fee_ids = set()
        escrow_ids = set()

    class Solanart:
        ids = {
          "CJsLwbP1iu5DuUikHEJnLfANgKy6stB2uFgvBBHoyxwz"
        }
        fee_ids = set()
        escrow_ids = set()

    class DigitalEyes:
        ids = {
            "A7p8451ktDCHq5yYaHczeLMYsjRsAkzc3hCXcSrwYHU7",  # DigitalEyes NFT Marketplace
            "7t8zVJtPCFAqog1DcnB6Ku1AVKtWfHkCiPi1cAvcJyVF"   # DigitalEyes Direct Sell
        }
        fee_ids = set()
        escrow_ids = set()

    class Solsea:
        ids = {
            "617jbWo616ggkDxvW1Le8pV38XLbVSyWY8ae6QUmGBAU"
        }
        fee_ids = set()
        escrow_ids = set()

    class AlphaArt:
        ids = {
            "HZaWndaNWHFDd9Dhk5pqUUtsmoBCqzb1MLu3NAh1VX6B"
        }
        fee_ids = set()
        escrow_ids = set()

    class ExchangeArt:
        ids = {
            "AmK5g2XcyptVLCFESBCJqoSfwV3znGoVYQnqEnaAZKWn"
        }
        fee_ids = set()
        escrow_ids = set()

    class OpenSea:
        ids = {
            "3o9d13qUvEuuauhFrVom1vuCzgNsJifeaBYDPquaT73Y",
            "pAHAKoTJsAAe2ZcvTZUxoYzuygVAFAmbYmJYdWT886r"
        }
        fee_ids = {
            # https://dune.com/queries/825072/1445379
            "8mcjXbJ8j4VryYFNpcBCFS37Au8zVYU53WTVaruJWcKt"  # platform fee account
        }
        escrow_ids = set()


marketplaces_ids = reduce(set.union, [cls_attribute.ids for cls_attribute in MarketplaceIds.__dict__.values()
                                      if inspect.isclass(cls_attribute)])


def is_marketplace(account_keys):
    return len(set(str(a) for a in account_keys).intersection(marketplaces_ids)) > 0


METADATA_PROGRAM_ID = PublicKey('metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s')
SYSTEM_PROGRAM_ID = PublicKey('11111111111111111111111111111111')
SYSVAR_RENT_PUBKEY = PublicKey('SysvarRent111111111111111111111111111111111')
ASSOCIATED_TOKEN_ACCOUNT_PROGRAM_ID = PublicKey('ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL')
TOKEN_PROGRAM_ID = PublicKey('TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA')


def empty_marketplace_data_dict():
    return {
        'signature': None,
        'block_time': None,
        "mint": None,
        'name': None,
        'source': None,
        'price': None,
        'creator_fee_paid': None,
        'market_fee_paid': None,
        'seller': None,
        'buyer': None,
        'type': None,
    }
