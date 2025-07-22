import os
from dotenv import load_dotenv
import discord
from discord.ext import commands
import re

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
SOURCE_CHANNEL_ID = int(os.getenv("SOURCE_CHANNEL_ID"))
DEST_CHANNEL_ID = int(os.getenv("DEST_CHANNEL_ID"))

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='/', intents=intents)

# ユーザーごとのモードを保存
user_modes = {}

# キャラ変換関数
def convert_to_style(text, mode):
    text = text.strip()
    base = re.sub(r'[。\.、,！!？?]', '', text)

    if mode == "猫":
        return base + " にゃん！"
    elif mode == "お嬢様":
        return "ふふっ、" + base + " ですわ〜"
    elif mode == "中二病":
        return "この世界の真理は " + base + " なのだ……"
    elif mode == "執事":
        return base + " でございます。"
    elif mode == "幼女":
        return base + " なのー！"
    elif mode == "ロボ":
        return base.upper() + "……ミッション完了。"
    elif mode == "さくらみこ":
        return f"にゃっはろ〜！{base}にぇ☆"
    else:
        return text  # モードなしなら変換しない

@bot.event
async def on_ready():
    print(f"✨ Bot ready as {bot.user}")

@bot.command()
async def mode(ctx, *, mode_name=None):
    if not mode_name:
        await ctx.send("モード名を指定してにゃん。例： `/mode 猫`")
        return
    if mode_name in ["off", "reset", "なし"]:
        user_modes.pop(ctx.author.id, None)
        await ctx.send("モードをリセットしたにゃん。")
    else:
        user_modes[ctx.author.id] = mode_name
        await ctx.send(f"{ctx.author.display_name} のモードを `{mode_name}` に設定したにゃん！")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    await bot.process_commands(message)

    if message.channel.id == SOURCE_CHANNEL_ID:
        dest_channel = bot.get_channel(DEST_CHANNEL_ID)
        if dest_channel is None:
            print("❌ 転送先チャンネルが見つかりません")
            return

        mode = user_modes.get(message.author.id, None)
        converted = convert_to_style(message.content, mode) if mode else message.content
        await dest_channel.send(converted)

bot.run(TOKEN)
