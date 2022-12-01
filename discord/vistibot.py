import os
import discord

from datetime import datetime
from urllib.parse import urljoin
from utils import get_logger
from dotenv import load_dotenv
import aiohttp

load_dotenv()

logger = get_logger("Vistier")
intents = discord.Intents.default()
intents.message_content = True


client = discord.Bot(intents=intents)


discord_token = os.environ['DISCORD_TOKEN']

VISTIER_API_URL = "http://127.0.0.1"
VISTIER_API_PORT = 5000
DEGOD_CMIDS = ["9MynErYQ5Qi6obp4YwwdoDmXkZ1hYVtPUqYmJJ3rZ9Kn", "8RMqBV79p8sb51nMaKMWR94XKjUvD2kuUSAkpEJTmxyx"]
SMB_CMIDS = ["9uBX3ASjxWvNBAD1xjbVaKA74mWGZys3RGSF7DdeDD3F"]
SSC_CMIDS = ["71ghWqucipW661X4ht61qvmc3xKQGMBGZxwSDmZrYQmf"]

vistier_url = f"{VISTIER_API_URL}:{VISTIER_API_PORT}"


def _p(part: float, total: float):
    if not total:
        return f"0%"
    return f"{part/total*100:.2f}%"


def _pr(price):
    return round(price/10 ** 9, 4)


@client.event
async def on_ready():
    logger.info("Logged in as a bot {0.user}".format(client))


async def search_for_nfts(ctx: discord.ApplicationContext, address: str, cmids: list, nft_name: str):
    await ctx.respond(f'Checking {address} for any {nft_name} NFTs', ephemeral=True)
    async with aiohttp.ClientSession() as session:
        async with session.get(url=urljoin(vistier_url, "wallet-status"),
                               params={"address": address, "cmid": cmids}) as resp:
            response = await resp.json()
            if response['status'] != "ok":
                message = "some unexpected error happened while processing your request. Please try again later"
            else:
                content = response["content"]
                owned_nfts = content['owned_nfts']
                fees_on_owned_nfts = content['fees_on_owned_nfts']
                creator_fee_percent_on_sale = content['creator_fee_percent_on_sale']

                message = f"Address has **{len(owned_nfts)}** {nft_name} NFTs:\n"
                if owned_nfts:
                    for mint, name in owned_nfts.items():
                        message += f" - _{name}_: <https://solana.fm/address/{mint}>\n"
                    message += f"\nRoyalties paid on all of them is **{_pr(fees_on_owned_nfts['total'])} SOL**\n"
                    message += f"- `{_pr(fees_on_owned_nfts['creator'])} SOL` to the creator\n"
                    message += f"- `{_pr(fees_on_owned_nfts['marketplace'])} SOL` as marketplace fees\n"

                    message += f"\nCollection has **{creator_fee_percent_on_sale}%** creator royalty fee\n"

                    message += "\nDetails:\n"
                    for transaction in content['transactions']:
                        name = transaction['name']
                        signature = transaction['signature']
                        block_time = transaction['block_time']
                        price = transaction['price']
                        creator_fee_paid = transaction['creator_fee_paid']
                        market_fee_paid = transaction['market_fee_paid']
                        if creator_fee_paid/price*100 >= creator_fee_percent_on_sale:
                            respected_seller_message = "`respected creator fees!`"
                        else:
                            respected_seller_message = "`didn't respected creator`"
                        message += f"- __***{name}***__\n"
                        message += f"\t- bought at: _{datetime.fromtimestamp(block_time)}_\n"
                        message += f"\t- signature: <https://solana.fm/tx/{signature}>\n"
                        message += f"\t- paid: _{_pr(price)} SOL_\n"
                        message += f"\t\t- {_pr(creator_fee_paid)} SOL (**{_p(creator_fee_paid, price)}**) " \
                                   f"fee to the creator - {respected_seller_message}\n"
                        message += f"\t\t- {_pr(market_fee_paid)} SOL ({_p(market_fee_paid, price)}) " \
                                   f"as marketplace fees\n"

            await ctx.respond(message, ephemeral=True)


@client.command(name="degods", description="Check if the provided address has DeGod NFTs")
async def degods(ctx: discord.ApplicationContext, address: str):
    await search_for_nfts(ctx, address, DEGOD_CMIDS, "DeGod")


@client.command(name="smb", description="Check if the provided address has SMB NFTs")
async def smb(ctx: discord.ApplicationContext, address: str):
    await search_for_nfts(ctx, address, SMB_CMIDS, "SMB")


@client.command(name="ssc", description="Check if the provided address has Shadowy Super Coder NFTs")
async def ssc(ctx: discord.ApplicationContext, address: str):
    await search_for_nfts(ctx, address, SSC_CMIDS, "Shadowy Super Coder")


client.run(discord_token)
