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

# XPに応じたレベルアップ
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
async def level(ctx):
    data = user_levels[ctx.author.id]
    await ctx.send(f"🔼 {ctx.author.display_name} の採掘レベル: Lv.{data['level']}（XP: {data['xp']}）")
