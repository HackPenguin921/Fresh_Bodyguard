# ------------------------------
# Golem ゲーム用 DiscordBot 完全統一コード - Part 1: 初期化 & 定義
# ------------------------------

import os
import json
import random
import re
from collections import defaultdict
from dotenv import load_dotenv
import discord
from discord.ext import commands

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
SOURCE_CHANNEL_ID = int(os.getenv("SOURCE_CHANNEL_ID"))
DEST_CHANNEL_ID = int(os.getenv("DEST_CHANNEL_ID"))

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

DATA_FILE = "player_data.json"
player_data = defaultdict(lambda: {
    "inventory": [],
    "hp": 100,
    "max_hp": 100,
    "level": 1,
    "xp": 0,
    "weapon": "素手",
    "armor": None,
    "alive": True,
    "potions": 1,
    "structures": [],
    "mode": None
})

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
    "クロスボウ": {"attack": (17, 29), "defense": 0}
}

RARITY = {
    "common": ["石", "丸石", "木材", "パン", "焼き豚"],
    "uncommon": ["鉄", "金", "レッドストーン", "スイカ", "ケーキ", "盾"],
    "rare": ["ダイヤモンド", "エメラルド", "ネザークォーツ", "金のリンゴ", "剣", "弓矢", "メイス"],
    "epic": ["TNT", "呪いの魔法", "トライデント", "回復薬", "クロスボウ"],
    "legendary": ["ハンマー", "サイス"]
}

BUILDING_REWARDS = {
    "小屋": {"ゴールド": 2},
    "見張り塔": {"エメラルド": 1},
    "城": {"ダイヤモンド": 2},
    "農場": {"ゴールド": 3},
    "砦": {"ダイヤモンド": 1, "エメラルド": 1}
}

MODE_PHRASES = {
    "猫": lambda s: s + "にゃん♪",
    "お嬢様": lambda s: "わたくし、" + s + "でございますわ。",
    "中二病": lambda s: s.replace("です", "なのだ").replace("ます", "なのだ"),
    "執事": lambda s: "かしこまりました。" + s,
    "幼女": lambda s: s.replace("です", "だよ").replace("ます", "だよ"),
    "ロボ": lambda s: s.replace("です", "デス").replace("ます", "デス"),
    "さくらみこ": lambda s: s + "みこ～"
}

LEVEL_THRESHOLDS = [0, 10, 25, 45, 70, 100, 140, 185, 235, 290]

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(player_data, f, ensure_ascii=False, indent=2)

def load_data():
    if not os.path.exists(DATA_FILE):
        return
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        loaded = json.load(f)
        for k, v in loaded.items():
            player_data[str(k)] = v


@bot.command()
async def mine(ctx):
    user_id = str(ctx.author.id)
    if user_id not in player_data:
        player_data[user_id] = {
            "inventory": [],
            "level": 1,
            "exp": 0,
            "hp": 100,
            "max_hp": 100,
            "weapon": "素手",
            "armor": None,
            "potions": 1,
            "mode": "平和",
            "alive": True,
            "structures": [],
        }
    # 以降は player_data[user_id]["exp"] を使う


    # 採掘アイテムリストをレアリティ混合で作成（重み付け）
    weighted_items = (
        RARITY["common"] * 50 +
        RARITY["uncommon"] * 30 +
        RARITY["rare"] * 15 +
        RARITY["epic"] * 4 +
        RARITY["legendary"] * 1
    )
    found_item = random.choice(weighted_items)
    player_data[user_id]["inventory"].append(found_item)

    # 経験値獲得
    gained_xp = random.randint(1, 5)
    player_data[user_id]["exp"] += gained_xp

    # レベルアップ判定
    current_level = player_data[user_id]["level"]
    while current_level < len(LEVEL_THRESHOLDS) and player_data[user_id]["exp"] >= LEVEL_THRESHOLDS[current_level]:
        current_level += 1
    if current_level != player_data[user_id]["level"]:
        player_data[user_id]["level"] = current_level
        await ctx.send(f"🎉 {ctx.author.display_name} さん、レベルアップ！ 現在レベル {current_level} です！")

    await ctx.send(f"{ctx.author.display_name} は {found_item} を採掘しました！（経験値 +{gained_xp}）")


@bot.command()
async def inventory(ctx):
    user_id = str(ctx.author.id)
    if user_id not in player_data or not player_data[user_id]["inventory"]:
        await ctx.send("あなたのインベントリは空です。まずは `!mine` でアイテムを集めましょう！")
        return
    inv = player_data[user_id]["inventory"]
    # アイテム数集計
    counted = {}
    for item in inv:
        counted[item] = counted.get(item, 0) + 1
    inv_text = ", ".join(f"{item} x{count}" for item, count in counted.items())
    await ctx.send(f"{ctx.author.display_name} のインベントリ: {inv_text}")


@bot.command()
async def level(ctx):
    user_id = str(ctx.author.id)
    if user_id not in player_data:
        await ctx.send("まだ冒険を始めていません。`!mine` で始めましょう！")
        return
    level = player_data[user_id]["level"]
    exp = player_data[user_id]["exp"]
    await ctx.send(f"{ctx.author.display_name} のレベル: {level}（経験値: {exp}）")


@bot.command()
async def equip(ctx, *, item_name: str):
    user_id = str(ctx.author.id)
    if user_id not in player_data:
        await ctx.send("まずは `!mine` でゲームを開始してください。")
        return
    inv = player_data[user_id]["inventory"]
    if item_name not in inv:
        await ctx.send(f"{item_name} はインベントリに存在しません。")
        return
    # 装備可能か判定（武器or盾だけ装備可能）
    if item_name in WEAPONS:
        player_data[user_id]["weapon"] = item_name
        await ctx.send(f"{ctx.author.display_name} は {item_name} を装備しました。")
    elif item_name == "盾":
        player_data[user_id]["armor"] = item_name
        await ctx.send(f"{ctx.author.display_name} は 盾 を装備しました。")
    else:
        await ctx.send(f"{item_name} は装備できません。武器または盾のみ装備可能です。")


@bot.command()
async def attack(ctx, target: discord.Member = None):
    user_id = str(ctx.author.id)
    if target is None:
        await ctx.send("攻撃する対象をメンションしてください。例: `!attack @ユーザー`")
        return
    if user_id not in player_data:
        await ctx.send("まずは `!mine` で準備しましょう！")
        return
    target_id = str(target.id)
    if target_id not in player_data:
        await ctx.send(f"{target.display_name} さんはまだゲームに参加していません。")
        return
    if user_id == target_id:
        await ctx.send("自分自身を攻撃することはできません！")
        return

    attacker = player_data[user_id]
    defender = player_data[target_id]

    if not defender.get("alive", True):
        await ctx.send(f"{target.display_name} さんは既に倒れています。")
        return

    # 攻撃力計算
    weapon = attacker.get("weapon", "素手")
    attack_range = WEAPONS.get(weapon, WEAPONS["素手"])["attack"]
    attack_value = random.randint(*attack_range)

    # 防御力計算
    armor_name = defender.get("armor")
    defense_value = 0
    if armor_name and armor_name in WEAPONS:
        defense_value = WEAPONS[armor_name]["defense"]

    damage = max(attack_value - defense_value, 0)
    defender["hp"] = max(defender.get("hp", 100) - damage, 0)

    msg = f"{ctx.author.display_name} は {target.display_name} に {damage} のダメージを与えました！ (残りHP: {defender['hp']})"

    if defender["hp"] <= 0:
        defender["alive"] = False
        msg += f"\n💀 {target.display_name} は倒れました！"
    await ctx.send(msg)


@bot.command()
async def back(ctx):
    user_id = str(ctx.author.id)
    if user_id not in player_data:
        await ctx.send("まだゲームを始めていません。")
        return
    player_data[user_id]["hp"] = player_data[user_id].get("max_hp", 100)
    player_data[user_id]["alive"] = True
    await ctx.send(f"{ctx.author.display_name} は拠点に戻り、HPが全回復しました！")


@bot.command()
async def build(ctx, *, building_name: str):
    user_id = str(ctx.author.id)
    if user_id not in player_data:
        await ctx.send("まずは `!mine` でゲームを始めてください。")
        return

    if building_name not in BUILDING_REWARDS:
        await ctx.send(f"{building_name} は建築可能な建物ではありません。")
        return

    # 必要素材があるか簡易チェック（ここでは省略して報酬のみ付与）
    rewards = BUILDING_REWARDS[building_name]

    # インベントリに報酬を付与
    for reward_item, count in rewards.items():
        for _ in range(count):
            player_data[user_id]["inventory"].append(reward_item)

    await ctx.send(f"{ctx.author.display_name} は {building_name} を建築しました！報酬: {', '.join(f'{k} x{v}' for k,v in rewards.items())}")

@bot.command()
async def golem(ctx):
    help_text = (
        "🧱 **Golem ゲームの遊び方**\n"
        "`!mine`：採掘してアイテムと経験値をゲット\n"
        "`!inventory`：インベントリを確認\n"
        "`!level`：レベルと経験値を表示\n"
        "`!equip アイテム名`：武器や盾を装備\n"
        "`!attack @ユーザー`：他プレイヤーに攻撃\n"
        "`!use_potion`：回復薬でHP回復\n"
        "`!build 建物名`：建物を建てて報酬ゲット\n"
        "`/mode モード名`：発言モードを変更（猫・執事など）\n"
        "`!back`：拠点に戻ってHP全回復\n"
    )
    await ctx.send(help_text)


@bot.command()
async def use_potion(ctx):
    user_id = str(ctx.author.id)
    if user_id not in player_data:
        await ctx.send("まずはゲームを始めてください。")
        return
    potions = player_data[user_id].get("potions", 0)
    if potions <= 0:
        await ctx.send("回復薬がありません！")
        return
    player_data[user_id]["potions"] = potions - 1
    player_data[user_id]["hp"] = min(player_data[user_id].get("max_hp", 100), player_data[user_id].get("hp", 100) + 50)
    await ctx.send(f"{ctx.author.display_name} は回復薬を使いHPを回復しました！（現在HP: {player_data[user_id]['hp']}）")


@bot.tree.command(name="mode", description="発言モードを変更します")
async def mode(interaction: discord.Interaction, mode: str):
    user_id = str(interaction.user.id)
    if mode not in MODE_PHRASES:
        await interaction.response.send_message(f"不明なモードです。利用可能なモード: {', '.join(MODE_PHRASES.keys())}")
        return
    if user_id not in player_data:
        player_data[user_id] = {
            "inventory": [],
            "level": 1,
            "exp": 0,
            "hp": 100,
            "max_hp": 100,
            "weapon": "素手",
            "armor": None,
            "potions": 1,
            "mode": mode,
        }
    else:
        player_data[user_id]["mode"] = mode
    await interaction.response.send_message(f"{interaction.user.display_name} の発言モードを {mode} に変更しました！")


@bot.event
async def on_message(message):
    if message.author.bot:
        return
    user_id = str(message.author.id)
    if user_id in player_data:
        mode = player_data[user_id].get("mode", "平和")
        func = MODE_PHRASES.get(mode)
        if func:
            new_content = func(message.content)
            if new_content != message.content:
                # 発言を書き換えるために、一旦メッセージを削除してモード変換後に再送信
                try:
                    await message.delete()
                    await message.channel.send(f"{message.author.display_name} > {new_content}")
                    return
                except discord.Forbidden:
                    # 削除権限なければ何もしない
                    pass
    await bot.process_commands(message)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"ログイン完了: {bot.user}")
