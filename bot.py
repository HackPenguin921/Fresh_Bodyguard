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
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

DATA_FILE = "game_data.json"

user_modes = {}
user_inventories = defaultdict(list)
player_states = defaultdict(lambda: {"hp": 100, "max_hp": 100, "alive": True})
built_structures = defaultdict(set)
user_equips = defaultdict(lambda: {"weapon": "素手", "armor": None})
user_levels = defaultdict(lambda: {"level": 1, "xp": 0})

BUILDING_REWARDS = {
    "小屋": {"ゴールド": 2},
    "見張り塔": {"エメラルド": 1},
    "城": {"ダイヤモンド": 2},
    "農場": {"ゴールド": 3},
    "砦": {"ダイヤモンド": 1, "エメラルド": 1},
}

WEAPONS = {
    "素手": {"attack": (5, 10), "defense": 0},
    "剣": {"attack": (20, 40), "defense": 0},
    "盾": {"attack": (0, 0), "defense": 20},
    "弓矢": {"attack": (15, 30), "defense": 0},
    "TNT": {"attack": (30, 50), "defense": 0},
    "呪いの魔法": {"attack": (25, 45), "defense": 0},
    "トライデント": {"attack": (18, 35), "defense": 0},
    "メイス": {"attack": (22, 38), "defense": 0},
    "ハンマー": {"attack": (26, 42), "defense": 0},
    "サイス": {"attack": (24, 44), "defense": 0},
    "投げナイフ": {"attack": (10, 20), "defense": 0},
    "クロスボウ": {"attack": (17, 29), "defense": 0},
}

RARITY = {
    "common": ["石", "丸石", "木材", "パン", "焼き豚"],
    "uncommon": ["鉄", "金", "レッドストーン", "スイカ", "ケーキ", "盾"],
    "rare": ["ダイヤモンド", "エメラルド", "ネザークォーツ", "ネザーレンガ", "金のリンゴ", "剣", "弓矢", "メイス"],
    "epic": ["TNT", "呪いの魔法", "トライデント", "回復薬", "クロスボウ"],
    "legendary": ["ハンマー", "サイス"]
}

ALL_ITEMS = sum(RARITY.values(), []) + [
    "ゾンビのスポーンエッグ", "スケルトンのスポーンエッグ", "クリーパーのスポーンエッグ",
    "村人のスポーンエッグ", "エンダーマンのスポーンエッグ", "何も見つからなかった"
]

LEVEL_THRESHOLDS = [0, 10, 25, 45, 70, 100, 140, 185, 235, 290]  # Level 1~10

def gain_xp(user_id, amount):
    level_data = user_levels[user_id]
    level_data["xp"] += amount
    while (level_data["level"] < len(LEVEL_THRESHOLDS) and
           level_data["xp"] >= LEVEL_THRESHOLDS[level_data["level"]]):
        level_data["level"] += 1

def save_data():
    data = {
        "user_modes": user_modes,
        "user_inventories": dict(user_inventories),
        "player_states": dict(player_states),
        "built_structures": {k: list(v) for k, v in built_structures.items()},
        "user_equips": dict(user_equips),
        "user_levels": dict(user_levels),
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
    user_equips.clear()
    for k, v in data.get("user_equips", {}).items():
        user_equips[int(k)] = v
    user_levels.clear()
    for k, v in data.get("user_levels", {}).items():
        user_levels[int(k)] = v

# --------------------- コマンド群 ---------------------

@bot.command()
async def mine(ctx):
    user_id = ctx.author.id
    level = user_levels[user_id]["level"]

    chances = ["common"] * 50 + ["uncommon"] * 30 + ["rare"] * 15 + ["epic"] * 4 + ["legendary"] * 1
    chosen_rarity = random.choices(chances, k=1)[0]
    item = random.choice(RARITY[chosen_rarity]) if RARITY[chosen_rarity] else "何も見つからなかった"

    if item != "何も見つからなかった":
        user_inventories[user_id].append(item)
        gain_xp(user_id, 5)
        await ctx.send(f"⛏️ {ctx.author.display_name}（Lv.{level}）は {item} を採掘し、XP+5！")
    else:
        await ctx.send(f"😢 {ctx.author.display_name} は何も見つからなかった…")
    save_data()

@bot.command()
async def inventory(ctx):
    user_id = ctx.author.id
    items = user_inventories[user_id]
    if not items:
        await ctx.send(f"📦 {ctx.author.display_name} のインベントリは空っぽです。")
    else:
        counts = {}
        for it in items:
            counts[it] = counts.get(it, 0) + 1
        msg = "📦 あなたの持ち物一覧:\n"
        for it, cnt in counts.items():
            msg += f"・{it} x{cnt}\n"
        await ctx.send(msg)

@bot.command()
async def level(ctx):
    data = user_levels[ctx.author.id]
    await ctx.send(f"🔼 {ctx.author.display_name} の採掘レベル: Lv.{data['level']}（XP: {data['xp']}）")

@bot.command()
async def equip(ctx, *, item_name: str):
    user_id = ctx.author.id
    items = user_inventories[user_id]
    if item_name not in items:
        await ctx.send(f"❌ {item_name} はインベントリにありません。")
        return

    # 装備可能な武器か盾か判定
    if item_name in WEAPONS:
        # 武器として装備
        user_equips[user_id]["weapon"] = item_name
        await ctx.send(f"⚔️ {ctx.author.display_name} は {item_name} を武器として装備しました。")
    elif item_name == "盾":
        user_equips[user_id]["armor"] = item_name
        await ctx.send(f"🛡️ {ctx.author.display_name} は 盾 を防具として装備しました。")
    else:
        await ctx.send(f"❌ {item_name} は装備できません。")
        return

    # 装備したものはインベントリから1つ減らす
    items.remove(item_name)
    save_data()

@bot.command()
async def attack(ctx, target: discord.Member):
    attacker_id = ctx.author.id
    target_id = target.id

    # 生存チェック
    if not player_states[attacker_id]["alive"]:
        await ctx.send("❌ あなたは死んでいるため攻撃できません。")
        return
    if not player_states[target_id]["alive"]:
        await ctx.send(f"❌ {target.display_name} はすでに倒れています。")
        return

    # 攻撃力、防御力計算
    weapon = user_equips[attacker_id]["weapon"]
    armor = user_equips[target_id]["armor"]

    attack_min, attack_max = WEAPONS.get(weapon, {"attack": (5, 10)}).get("attack", (5, 10))
    defense = WEAPONS.get(armor, {"defense": 0}).get("defense", 0)

    damage = random.randint(attack_min, attack_max) - defense
    damage = max(1, damage)  # 最低1ダメージ

    player_states[target_id]["hp"] -= damage

    if player_states[target_id]["hp"] <= 0:
        player_states[target_id]["alive"] = False
        player_states[target_id]["hp"] = 0
        await ctx.send(f"💥 {ctx.author.display_name} の攻撃！ {target.display_name} に {damage} ダメージ！\n💀 {target.display_name} は倒れました！")
    else:
        await ctx.send(f"💥 {ctx.author.display_name} の攻撃！ {target.display_name} に {damage} ダメージ！ 残りHP: {player_states[target_id]['hp']}")

    save_data()

@bot.command()
async def back(ctx):
    user_id = ctx.author.id
    if player_states[user_id]["alive"]:
        await ctx.send("❗ あなたはまだ生きています。")
        return
    player_states[user_id]["hp"] = player_states[user_id]["max_hp"]
    player_states[user_id]["alive"] = True
    await ctx.send(f"🌟 {ctx.author.display_name} は復活しました！ HPが全回復しました。")
    save_data()

@bot.command()
async def build(ctx, *, building_name: str):
    user_id = ctx.author.id
    building_name = building_name.strip()

    if building_name not in BUILDING_REWARDS:
        await ctx.send(f"❌ {building_name} は登録された建築物ではありません。")
        return

    # 既に建築済みかチェック
    if building_name in built_structures[user_id]:
        await ctx.send(f"⚠️ {building_name} はすでに建てています。")
        return

    built_structures[user_id].add(building_name)

    # 報酬付与
    rewards = BUILDING_REWARDS[building_name]
    for item, qty in rewards.items():
        for _ in range(qty):
            user_inventories[user_id].append(item)

    await ctx.send(f"🏗️ {ctx.author.display_name} は {building_name} を建てました！報酬として {', '.join(f'{k} x{v}' for k,v in rewards.items())} をゲット！")
    save_data()

@bot.command()
async def use_potion(ctx):
    user_id = ctx.author.id
    items = user_inventories[user_id]

    if "回復薬" not in items:
        await ctx.send("❌ 回復薬を持っていません。")
        return

    if not player_states[user_id]["alive"]:
        await ctx.send("❌ 死んでいる間は回復薬を使えません。")
        return

    # HP回復量
    heal_amount = 30
    player_states[user_id]["hp"] = min(player_states[user_id]["max_hp"], player_states[user_id]["hp"] + heal_amount)
    items.remove("回復薬")

    await ctx.send(f"💊 {ctx.author.display_name} は回復薬を使い、HPが {heal_amount} 回復しました。現在HP: {player_states[user_id]['hp']}")
    save_data()

# --- モード設定と発言変換の例 ---

# 口調変換の簡易辞書（例）
MODE_PHRASES = {
    "猫": lambda s: s + "にゃん♪",
    "お嬢様": lambda s: "わたくし、" + s + "でございますわ。",
    "中二病": lambda s: s.replace("です", "なのだ").replace("ます", "なのだ"),
    "執事": lambda s: "かしこまりました。" + s,
    "幼女": lambda s: s.replace("です", "だよ").replace("ます", "だよ"),
    "ロボ": lambda s: s.replace("です", "デス").replace("ます", "デス"),
    "さくらみこ": lambda s: s + "みこ～",
}

@bot.command()
async def mode(ctx, *, mode_name: str):
    user_id = ctx.author.id
    mode_name = mode_name.strip()
    if mode_name not in MODE_PHRASES:
        await ctx.send(f"❌ {mode_name} は対応しているモード名ではありません。")
        return
    user_modes[user_id] = mode_name
    await ctx.send(f"🎭 {ctx.author.display_name} の口調モードを「{mode_name}」に設定しました。")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # 口調モード適用
    if message.channel.id == SOURCE_CHANNEL_ID:
        user_id = message.author.id
        mode_name = user_modes.get(user_id)
        if mode_name:
            phrase_func = MODE_PHRASES.get(mode_name)
            if phrase_func:
                transformed = phrase_func(message.content)
                dest_channel = bot.get_channel(DEST_CHANNEL_ID)
                if dest_channel:
                    await dest_channel.send(f"{message.author.display_name} さんの発言（{mode_name}モード）:\n{transformed}")
                await bot.process_commands(message)
                return

    await bot.process_commands(message)

load_data()
bot.run(TOKEN)
