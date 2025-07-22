import os
import json
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

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

DATA_FILE = "game_data.json"

user_modes = {}
user_inventories = defaultdict(list)
player_states = defaultdict(lambda: {"hp": 100, "max_hp": 100, "alive": True})
built_structures = defaultdict(set)

BUILDING_REWARDS = {
    "小屋": {"ゴールド": 2},
    "見張り塔": {"エメラルド": 1},
    "城": {"ダイヤモンド": 2},
    "農場": {"ゴールド": 3},
    "砦": {"ダイヤモンド": 1, "エメラルド": 1},
}

def save_data():
    data = {
        "user_modes": user_modes,
        "user_inventories": dict(user_inventories),
        "player_states": dict(player_states),
        "built_structures": {k: list(v) for k, v in built_structures.items()},
    }
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_data():
    if not os.path.exists(DATA_FILE):
        return
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    user_modes.clear()
    for k, v in data.get("user_modes", {}).items():
        user_modes[int(k)] = v
    user_inventories.clear()
    for k, v in data.get("user_inventories", {}).items():
        user_inventories[int(k)] = v
    player_states.clear()
    for k, v in data.get("player_states", {}).items():
        player_states[int(k)] = v
    built_structures.clear()
    for k, v in data.get("built_structures", {}).items():
        built_structures[int(k)] = set(v)

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

@bot.event
async def on_ready():
    load_data()
    print(f"✅ Bot ready as {bot.user}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # / から始まるコマンドは無視（modeコマンドも除外）
    if message.content.startswith("/"):
        return

    await bot.process_commands(message)

    # チャンネルIDによる発言転送
    if message.channel.id == SOURCE_CHANNEL_ID:
        dest_channel = bot.get_channel(DEST_CHANNEL_ID)
        if dest_channel is None:
            print("❌ 転送先チャンネルが見つかりません")
            return

        mode = user_modes.get(message.author.id)
        converted = convert_to_style(message.content, mode) if mode else message.content
        await dest_channel.send(converted)

@bot.command()
async def mode(ctx, *, mode_name=None):
    if not mode_name:
        await ctx.send("モード名を指定してにゃん。例： `/mode 猫`")
        return
    if mode_name in ["off", "reset", "なし"]:
        user_modes.pop(ctx.author.id, None)
        save_data()
        await ctx.send("モードをリセットしたにゃん。")
    else:
        user_modes[ctx.author.id] = mode_name
        save_data()
        await ctx.send(f"{ctx.author.display_name} のモードを `{mode_name}` に設定したにゃん！")

@bot.command()
async def mine(ctx):
    drops = ['石', '石炭', '鉄', '金', 'ダイヤモンド', 'エメラルド', '回復薬', '何も見つからなかった']
    item = random.choice(drops)

    if item != '何も見つからなかった':
        user_inventories[ctx.author.id].append(item)
        save_data()
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
        save_data()
        await ctx.send(f"{ctx.author.display_name} は {target.display_name} に致命的な一撃！💥 {target.display_name} は倒れた…")
    else:
        save_data()
        await ctx.send(f"{ctx.author.display_name} が {target.display_name} に {damage} ダメージを与えた！ 残りHP: {target_state['hp']}")

@bot.command()
async def back(ctx):
    user_id = ctx.author.id
    state = player_states[user_id]

    if state["alive"]:
        await ctx.send(f"{ctx.author.display_name} はすでに生きています！")
    else:
        state["hp"] = state["max_hp"] // 2
        state["alive"] = True
        save_data()
        await ctx.send(f"🧬 {ctx.author.display_name} が `!back` で復活！ HP: {state['hp']}")

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

    for item, amount in rewards.items():
        inventory.extend([item] * amount)

    built_structures[user_id].add(structure_name)
    save_data()

    reward_text = " / ".join([f"{item}×{qty}" for item, qty in rewards.items()])
    await ctx.send(f"🏗️ {ctx.author.display_name} は「{structure_name}」を完成！\n💰 報酬：{reward_text}")

@bot.command()
async def use_potion(ctx):
    inventory = user_inventories[ctx.author.id]
    if "回復薬" not in inventory:
        await ctx.send(f"💊 {ctx.author.display_name} のインベントリに回復薬がありません！")
        return

    state = player_states[ctx.author.id]
    if not state["alive"]:
        await ctx.send(f"⚠️ {ctx.author.display_name} は倒れているので回復薬を使えません。`!back` で復活してください。")
        return

    heal_amount = 50
    old_hp = state["hp"]
    state["hp"] = min(state["hp"] + heal_amount, state["max_hp"])

    inventory.remove("回復薬")
    save_data()

    await ctx.send(f"💊 {ctx.author.display_name} は回復薬を使ってHPが {old_hp} → {state['hp']} に回復した！")

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
        "・`!use_potion` - 回復薬を使ってHPを回復しよう！\n"
        "・`/mode モード名` - 発言の口調を変えられるよ！（猫、お嬢様、中二病、執事、幼女、ロボ、さくらみこなど）\n"
        "\n"
        "※通常の発言は `SOURCE_CHANNEL_ID` チャンネルで行い、変換された発言が別チャンネルに送られます。\n"
    )
    await ctx.send(help_text)

bot.run(TOKEN)
