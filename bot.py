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
from discord.ui import View, Button
from discord import Embed
import asyncio

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
SOURCE_CHANNEL_ID = int(os.getenv("SOURCE_CHANNEL_ID"))
DEST_CHANNEL_ID = int(os.getenv("DEST_CHANNEL_ID"))

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

class PaginatorView(View):
    def __init__(self, pages, author_id):
        super().__init__(timeout=60)
        self.pages = pages
        self.current_page = 0
        self.author_id = author_id

    async def update_message(self, interaction):
        embed = self.pages[self.current_page]
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="⬅ 前へ", style=discord.ButtonStyle.primary)
    async def previous(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("あなたのボタンではありません。", ephemeral=True)
            return
        if self.current_page > 0:
            self.current_page -= 1
            await self.update_message(interaction)

    @discord.ui.button(label="次へ ➡", style=discord.ButtonStyle.primary)
    async def next(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("あなたのボタンではありません。", ephemeral=True)
            return
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            await self.update_message(interaction)

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
def ensure_player_defaults(user_id):
    defaults = {
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

    if user_id not in player_data:
        player_data[user_id] = defaults.copy()
    else:
        for key, value in defaults.items():
            if key not in player_data[user_id]:
                player_data[user_id][key] = value



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

DATA_FILE = "game_data.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        return
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        for user_id, pdata in data.get("player_data", {}).items():
            player_data[user_id] = pdata

def save_data():
    data = {
        "player_data": dict(player_data)
    }
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


@bot.command()
async def mine(ctx):
    user_id = str(ctx.author.id)
    ensure_player_defaults(user_id)
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
    while player_data[user_id]["exp"] >= 100:
    player_data[user_id]["exp"] -= 100
    player_data[user_id]["level"] += 1
    await ctx.send(f"🎉 {ctx.author.display_name} さん、レベルアップ！ 現在レベル {player_data[user_id]['level']} です！")


    if current_level != player_data[user_id]["level"]:
        player_data[user_id]["level"] = current_level
        await ctx.send(f"🎉 {ctx.author.display_name} さん、レベルアップ！ 現在レベル {current_level} です！")

    await ctx.send(f"{ctx.author.display_name} は {found_item} を採掘しました！（経験値 +{gained_xp}）")


@bot.command()
async def spin(ctx):
    user_id = str(ctx.author.id)
    ensure_player_defaults(user_id)

    # 抽選テーブル
    wheel = [
        ("🎉 レアアイテム獲得！", "ダイヤモンド"),
        ("😎 ゴールド x5！", "ゴールド", 5),
        ("💤 ハズレ…", None),
        ("🍰 ケーキをゲット！", "ケーキ"),
        ("🧪 回復薬 x1", "回復薬", 1),
        ("🔥 エピック武器！", random.choice(["TNT", "トライデント", "呪いの魔法"])),
    ]

    result = random.choice(wheel)

    # 報酬処理
    message = result[0]
    if result[1]:
        item = result[1]
        count = result[2] if len(result) > 2 else 1
        for _ in range(count):
            player_data[user_id]["inventory"].append(item)
        message += f" `{item} x{count}` を入手しました！"
    else:
        message += " 何も得られませんでした…"

    await ctx.send(f"{ctx.author.display_name} のルーレット結果：{message}")

@bot.command()
async def trade(ctx, target: discord.Member, *, item_name: str):
    sender_id = str(ctx.author.id)
    receiver_id = str(target.id)

    if sender_id not in player_data or item_name not in player_data[sender_id]["inventory"]:
        await ctx.send("そのアイテムは持っていません。")
        return

    def check(m):
        return m.author == target and m.content.lower() == "yes"

    await ctx.send(f"{target.mention} さん、{ctx.author.display_name} から `{item_name}` を受け取りますか？（`yes` と送信）")

    try:
    msg = await bot.wait_for("message", timeout=15.0, check=check)
    player_data[sender_id]["inventory"].remove(item_name)
    player_data[receiver_id]["inventory"].append(item_name)
    await ctx.send(f"✅ トレード成功！{ctx.author.display_name} → {target.display_name} に `{item_name}` を渡しました。")
    except asyncio.TimeoutError:
    await ctx.send("⏳ 時間切れです。トレードはキャンセルされました。")
    except Exception as e:
    await ctx.send(f"トレード中にエラーが発生しました: {e}")

duel_sessions = {}  # {channel_id: {"players": [user1, user2], "turn": 0 or 1, "hp": {user1: int, user2: int}}}

@bot.command()
async def duel(ctx, target: discord.Member):
    challenger_id = str(ctx.author.id)
    target_id = str(target.id)

    if challenger_id == target_id:
        await ctx.send("自分自身とは決闘できません。")
        return
    if challenger_id not in player_data or target_id not in player_data:
        await ctx.send("両者ともゲーム参加者である必要があります。")
        return
    if ctx.channel.id in duel_sessions:
        await ctx.send("このチャンネルでは既に決闘が進行中です。")
        return

    duel_sessions[ctx.channel.id] = {
        "players": [challenger_id, target_id],
        "turn": 0,
        "hp": {
            challenger_id: player_data[challenger_id]["hp"],
            target_id: player_data[target_id]["hp"]
        }
    }

    await ctx.send(f"{ctx.author.display_name} が {target.display_name} に決闘を挑みました！\n"
                   f"{player_data[challenger_id]['weapon']} を装備して戦いましょう！\n"
                   f"{ctx.author.display_name} のターンです。`!attack` で攻撃！")

@bot.command()
async def battle(ctx):
    if ctx.channel.id not in duel_sessions:
        await ctx.send("決闘は進行していません。")
        return

    session = duel_sessions[ctx.channel.id]
    players = session["players"]
    turn = session["turn"]
    attacker_id = players[turn]
    defender_id = players[1 - turn]

    if str(ctx.author.id) != attacker_id:
        await ctx.send("今はあなたのターンではありません。")
        return

    attacker = player_data[attacker_id]
    defender = player_data[defender_id]

    weapon = attacker.get("weapon", "素手")
    attack_range = WEAPONS.get(weapon, WEAPONS["素手"])["attack"]
    attack_value = random.randint(*attack_range)

    armor_name = defender.get("armor")
    defense_value = 0
    if armor_name and armor_name in WEAPONS:
        defense_value = WEAPONS[armor_name]["defense"]

    damage = max(attack_value - defense_value, 0)
    session["hp"][defender_id] -= damage

    msg = (f"{ctx.author.display_name} の攻撃！ {player_data[attacker_id]['weapon']} で "
           f"{damage} ダメージを与えた！\n"
           f"{player_data[defender_id]['weapon']} の {player_data[defender_id]['weapon']} は残りHP {session['hp'][defender_id]}")

    if session["hp"][defender_id] <= 0:
        msg += f"\n💀 {player_data[defender_id]['weapon']} は倒れました！決闘終了！"
        # 決闘終了処理
        del duel_sessions[ctx.channel.id]
    else:
        session["turn"] = 1 - turn
        next_player_id = players[session["turn"]]
        msg += f"\n次は {bot.get_user(int(next_player_id)).display_name} のターンです！"

    await ctx.send(msg)

SHOP_ITEMS = {
    "回復薬": 10,
    "剣": 50,
    "盾": 40,
    "弓矢": 45,
    "トライデント": 80,
}

# プレイヤーデータに「gold」を追加し、デフォルトは100
def ensure_player_defaults(user_id):
    defaults = {
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
        "gold": 100,
        "pet": None,
    }

    if user_id not in player_data:
        player_data[user_id] = defaults.copy()
    else:
        for key, value in defaults.items():
            if key not in player_data[user_id]:
                player_data[user_id][key] = value


@bot.command()
async def shop(ctx):
    shop_text = "**ショップ商品リスト**\n"
    for item, price in SHOP_ITEMS.items():
        shop_text += f"{item}: {price} ゴールド\n"
    await ctx.send(shop_text)

@bot.command()
async def buy(ctx, *, item_name: str):
    user_id = str(ctx.author.id)
    if user_id not in player_data:
        await ctx.send("ゲームを始めてください。")
        return
    if item_name not in SHOP_ITEMS:
        await ctx.send("ショップにその商品はありません。")
        return

    price = SHOP_ITEMS[item_name]
    gold = player_data[user_id].get("gold", 0)

    if gold < price:
        await ctx.send(f"ゴールドが足りません。所持ゴールド: {gold}、必要ゴールド: {price}")
        return

    player_data[user_id]["gold"] -= price
    player_data[user_id]["inventory"].append(item_name)

    await ctx.send(f"{ctx.author.display_name} は {item_name} を {price} ゴールドで購入しました！ 所持ゴールド: {player_data[user_id]['gold']}")

QUESTS = [
    {"desc": "森の中の魔物退治", "exp": 20, "reward": "鉄"},
    {"desc": "川の向こうの採掘", "exp": 15, "reward": "金"},
    {"desc": "古代遺跡の調査", "exp": 30, "reward": "ダイヤモンド"},
]

@bot.command()
async def quest(ctx):
    user_id = str(ctx.author.id)
    ensure_player_defaults(user_id)

    quest = random.choice(QUESTS)
    success = random.random() < 0.7  # 70% 成功率

    if success:
        player_data[user_id]["exp"] += quest["exp"]
        player_data[user_id]["inventory"].append(quest["reward"])
        await ctx.send(f"クエスト成功！『{quest['desc']}』\n経験値 +{quest['exp']}, アイテム `{quest['reward']}` を獲得！")
    else:
        await ctx.send(f"クエスト失敗…『{quest['desc']}』次は頑張ろう！")

# player_data[user_id]["pet"] = {"name": str, "level": int, "exp": int}

@bot.command()
async def pet(ctx):
    user_id = str(ctx.author.id)
    if user_id not in player_data:
        await ctx.send("まずはゲームを始めてください。")
        return

    pet = player_data[user_id].get("pet")
    if not pet:
        # 新規ペット作成
        player_data[user_id]["pet"] = {"name": "ゴーレム", "level": 1, "exp": 0}
        await ctx.send(f"{ctx.author.display_name} に新しいペット『ゴーレム』が仲間になりました！")
    else:
        # レベルアップ判定（経験値がたまったら）
        pet["exp"] += 10
        if pet["exp"] >= 100:
            pet["level"] += 1
            pet["exp"] -= 100
            await ctx.send(f"ペット『{pet['name']}』がレベルアップ！現在レベル {pet['level']}！")
        else:
            await ctx.send(f"ペット『{pet['name']}』は経験値を {pet['exp']}/100 ためました。")


@bot.command()
async def inventory(ctx):
    user_id = str(ctx.author.id)

    if user_id not in player_data or not player_data[user_id]["inventory"]:
        await ctx.send("あなたのインベントリは空です。まずは `!mine` でアイテムを集めましょう！")
        return

    inv = player_data[user_id]["inventory"]

    # アイテム数を集計して [(item, count), ...] のリストに
    counted = {}
    for item in inv:
        counted[item] = counted.get(item, 0) + 1
    counted_items = [f"{item} x{count}" for item, count in counted.items()]

    # ページに分割（8件ずつ）
    items_per_page = 8
    pages = []
    for i in range(0, len(counted_items), items_per_page):
        chunk = counted_items[i:i + items_per_page]
        embed = discord.Embed(
            title=f"{ctx.author.display_name} のインベントリ 🧳",
            description="\n".join(chunk),
            color=discord.Color.green()
        )
        embed.set_footer(text=f"ページ {i // items_per_page + 1}/{(len(counted_items) + items_per_page - 1) // items_per_page}")
        pages.append(embed)

    view = PaginatorView(pages, ctx.author.id)
    await ctx.send(embed=pages[0], view=view)



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
        "🧱 **Golem ゲームへようこそ！** 🧱\n\n"
        "🎮 **基本コマンド**\n"
        "・`!mine`：採掘してアイテムと経験値をゲット！⛏️\n"
        "・`!inventory`：インベントリを確認します。🎒\n"
        "・`!level`：レベルと経験値を表示。⭐\n"
        "・`!equip <アイテム名>`：武器や盾を装備。🗡️🛡️\n"
        "・`!attack @ユーザー`：自由に他プレイヤーを攻撃できます。\n"
        "・`!duel @ユーザー` + `!battle`：ターン制の決闘モードでPvP対戦が楽しめます。\n"
        "・`!use_potion`：回復薬でHPを回復。💊\n"
        "・`!build <建物名>`：建物を建てて報酬ゲット！🏰\n"
        "・`/mode <モード名>`：発言モードを変更（猫・執事など）。😺🤵\n"
        "・`!back`：拠点に戻ってHP全回復。🏠\n\n"
        "🆕 **新機能**\n"
        "・`!duel @ユーザー`：ターン制PvP決闘で腕試し！⚔️🛡️\n"
        "・`!shop` / `!buy <アイテム名>`：ショップで装備やアイテムを購入可能！🛒\n"
        "・`!quest`：ランダムクエストに挑戦！報酬ゲット！🎯\n"
        "・`!pet`：ペットと一緒に冒険しよう！🐾\n"
        "・`!trade @ユーザー <自分のアイテム> <相手のアイテム>`：アイテム交換機能（準備中）🔄\n"
        "・`!spin`：ルーレットで運試し！（準備中）🎰\n\n"
        "ゲームの冒険を存分に楽しんでくださいね！"
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

    await bot.process_commands(message)  # 先にコマンドを処理

    user_id = str(message.author.id)
    if user_id in player_data:
        mode = player_data[user_id].get("mode", "平和")
        func = MODE_PHRASES.get(mode)
        if func:
            new_content = func(message.content)
            if new_content != message.content:
                try:
                    await message.delete()
                    await message.channel.send(f"{message.author.display_name} > {new_content}")
                except discord.Forbidden:
                    pass


@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"ログイン完了: {bot.user}")

if __name__ == "__main__":
    load_data()
    bot.run(TOKEN)

