import os
from dotenv import load_dotenv
import discord
from discord.ext import commands
import re
import random
from collections import defaultdict

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
SOURCE_CHANNEL_ID = int(os.getenv("SOURCE_CHANNEL_ID"))
DEST_CHANNEL_ID = int(os.getenv("DEST_CHANNEL_ID"))

intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # attack対象指定に必要

bot = commands.Bot(command_prefix='!', intents=intents)

user_modes = {}
user_inventories = defaultdict(list)
player_states = defaultdict(lambda: {"hp": 100, "max_hp": 100, "alive": True})
built_structures = defaultdict(set)  # user_id: set of structure names

BUILDING_REWARDS = {
    "小屋": {"ゴールド": 2},
    "見張り塔": {"エメラルド": 1},
    "城": {"ダイヤモンド": 2},
    "農場": {"ゴールド": 3},
    "砦": {"ダイヤモンド": 1, "エメラルド": 1},
}

# ---------- 文字変換 ----------
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
        return text

# ---------- 通常メッセージ処理 ----------
@bot.event
async def on_ready():
    print(f"✅ Bot ready as {bot.user}")

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

    # / から始まるコマンドは無視
    if message.content.startswith("/"):
        return

    await bot.process_commands(message)

    # チャンネルIDによる発言転送などはここでOK
    if message.channel.id == SOURCE_CHANNEL_ID:
        dest_channel = bot.get_channel(DEST_CHANNEL_ID)
        if dest_channel is None:
            print("❌ 転送先チャンネルが見つかりません")
            return

        mode = user_modes.get(message.author.id)
        converted = convert_to_style(message.content, mode) if mode else message.content
        await dest_channel.send(converted)


# ---------- 採掘コマンド ----------
@bot.command()
async def mine(ctx):
    drops = ['石', '石炭', '鉄', '金', 'ダイヤモンド', 'エメラルド', '何も見つからなかった']
    item = random.choice(drops)

    if item != '何も見つからなかった':
        user_inventories[ctx.author.id].append(item)
        await ctx.send(f"⛏️ {ctx.author.display_name} は {item} を採掘した！")
    else:
        await ctx.send(f"😢 {ctx.author.display_name} は何も見つからなかった…")

@bot.command()
async def inventory(ctx):
    inv = user_inventories.get(ctx.author.id, [])
    if not inv:
        await ctx.send(f"🎒 {ctx.author.display_name} のインベントリは空っぽだよ！")
    else:
        count = {}
        for item in inv:
            count[item] = count.get(item, 0) + 1
        inventory_list = '\n'.join([f"{item} x{qty}" for item, qty in count.items()])
        await ctx.send(f"🎒 {ctx.author.display_name} のインベントリ：\n{inventory_list}")

# ---------- 攻撃コマンド ----------
@bot.command()
async def attack(ctx, target: discord.Member):
    attacker_id = ctx.author.id
    target_id = target.id

    attacker_state = player_states[attacker_id]
    target_state = player_states[target_id]

    if not attacker_state["alive"]:
        await ctx.send(f"{ctx.author.display_name} は死んでいるため攻撃できません！ `!back` で復活しましょう。")
        return

    if not target_state["alive"]:
        await ctx.send(f"{target.display_name} はすでに倒れています！")
        return

    damage = random.randint(10, 30)
    target_state["hp"] -= damage
    if target_state["hp"] <= 0:
        target_state["hp"] = 0
        target_state["alive"] = False
        await ctx.send(f"{ctx.author.display_name} は {target.display_name} に致命的な一撃！💥 {target.display_name} は倒れた…")
    else:
        await ctx.send(f"{ctx.author.display_name} が {target.display_name} に {damage} ダメージを与えた！ 残りHP: {target_state['hp']}")

# ---------- 蘇生コマンド ----------
@bot.command()
async def back(ctx):
    user_id = ctx.author.id
    state = player_states[user_id]

    if state["alive"]:
        await ctx.send(f"{ctx.author.display_name} はすでに生きています！")
    else:
        state["hp"] = state["max_hp"] // 2
        state["alive"] = True
        await ctx.send(f"🧬 {ctx.author.display_name} が `!back` で復活！ HP: {state['hp']}")

# ---------- 建築報酬コマンド ----------
@bot.command()
async def build(ctx, *, structure_name):
    user_id = ctx.author.id

    if structure_name not in BUILDING_REWARDS:
        await ctx.send(f"🏗️ 未知の建築物「{structure_name}」です。登録された建築物を指定してください。")
        return

    if structure_name in built_structures[user_id]:
        await ctx.send(f"🔁 {ctx.author.display_name} はすでに「{structure_name}」を建築済みです！")
        return

    rewards = BUILDING_REWARDS[structure_name]
    inventory = user_inventories[user_id]

    # 報酬を追加
    for item, amount in rewards.items():
        inventory.extend([item] * amount)

    built_structures[user_id].add(structure_name)

    reward_text = " / ".join([f"{item}×{qty}" for item, qty in rewards.items()])
    await ctx.send(f"🏗️ {ctx.author.display_name} は「{structure_name}」を完成！\n💰 報酬：{reward_text}")

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)
# ---------- ヘルプコマンド ----------
@bot.command(name="helpMine")
async def help_command(ctx):
    help_text = (
        "🎮 **遊べるコマンド一覧** 🎮\n"
        "・`!mine` - 採掘をしてアイテムをゲットしよう！\n"
        "・`!inventory` - 自分の持っているアイテムを確認しよう！\n"
        "・`!attack @ユーザー` - 他のプレイヤーを攻撃するよ！(生きている時のみ)\n"
        "・`!back` - 死んだらこのコマンドで復活しよう！\n"
        "・`!build 建築物名` - 建築物を建てて報酬をゲット！\n"
        "    登録済み建築物: 小屋, 見張り塔, 城, 農場, 砦\n"
        "・`/mode モード名` - 発言の口調を変えられるよ！（猫、お嬢様、中二病、執事、幼女、ロボ、さくらみこなど）\n"
        "\n"
        "※通常の発言は `SOURCE_CHANNEL_ID` チャンネルで行い、変換された発言が別チャンネルに送られます。\n"
    )
    await ctx.send(help_text)

bot.run(TOKEN)
