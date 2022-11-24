import os
import discord
from discord.ext import commands

from utils import get_logger
from dotenv import load_dotenv

load_dotenv()

logger = get_logger("Vistier")
intents = discord.Intents.default()
intents.message_content = True


client = discord.Bot(intents=intents)


discord_token = os.getenv('DISCORD_TOKEN')


@client.event
async def on_ready():
    logger.info("Logged in as a bot {0.user}".format(client))


@client.command(name="lastbuy", description="lastbuy")
async def last_buy(ctx: discord.ApplicationContext, address: str):
    pass


@client.command()
async def verify(ctx: discord.ApplicationContext, address: str):
    print(ctx.author.guild, ctx.author.id, ctx.author.name)
    logger.info(address)
    # logger.info(ctx.guild)
    # logger.info(ctx.channel)
    # logger.info(ctx.interaction.response)
    await ctx.respond(f'You passed: {address}', ephemeral=True)
    response = await ctx.bot.wait_for('message')
    if response.content == "yes":
        logger.info("yes")


client.run(discord_token)

