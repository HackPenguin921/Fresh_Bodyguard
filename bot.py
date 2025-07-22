import os
from dotenv import load_dotenv
import discord

load_dotenv()  # .envファイルを読み込み

TOKEN = os.getenv("BOT_TOKEN")
SOURCE_CHANNEL_ID = int(os.getenv("SOURCE_CHANNEL_ID"))
DEST_CHANNEL_ID = int(os.getenv("DEST_CHANNEL_ID"))

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"Logged in as {client.user}")

@client.event
async def on_message(message):
    if message.author.bot:
        return

    if message.channel.id == SOURCE_CHANNEL_ID:
        dest_channel = client.get_channel(DEST_CHANNEL_ID)
        if dest_channel is None:
            print("Destination channel not found!")
            return
        await dest_channel.send(f"{message.author.display_name}: {message.content}")

client.run(TOKEN)
