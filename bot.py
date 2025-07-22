import os
from dotenv import load_dotenv
import discord
import re

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
SOURCE_CHANNEL_ID = int(os.getenv("SOURCE_CHANNEL_ID"))
DEST_CHANNEL_ID = int(os.getenv("DEST_CHANNEL_ID"))

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

# ロボット風変換関数（かな→カタカナ、句読点カット、文体変換）
def robotify(text):
    # ひらがな・カタカナ → 全角カタカナへ変換（シンプルな方法）
    import jaconv
    text = jaconv.hira2kata(text)

    # 文体変換パターン（簡易）
    replacements = {
        "です": "デス",
        "ます": "マス",
        "した": "シマシタ",
        "する": "スル",
        "ない": "アリマセン",
        "こんにちは": "コンニチハ",
        "ありがとう": "アリガトウゴザイマス",
        "わかりません": "リカイ　デキマセン",
        "疲れた": "ツカレ　ヲ　カンジマシタ",
    }

    for word, robo_word in replacements.items():
        text = text.replace(word, robo_word)

    # ロボット風に整形
    text = text.strip()
    text = re.sub(r'[。\.、,！!？?]', '', text)  # 句読点など削除
    return f"【AIメッセージ】 {text}。"

@client.event
async def on_ready():
    print(f"🤖 Bot ready! Logged in as {client.user}")

@client.event
async def on_message(message):
    if message.author.bot:
        return

    if message.channel.id == SOURCE_CHANNEL_ID:
        dest_channel = client.get_channel(DEST_CHANNEL_ID)
        if dest_channel is None:
            print("❌ 転送先チャンネルが見つかりません")
            return

        converted = robotify(message.content)
        await dest_channel.send(converted)

client.run(TOKEN)
