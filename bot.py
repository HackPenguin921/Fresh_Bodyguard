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
from datetime import datetime
import pytz
import aiohttp
import datetime
from collections import defaultdict

DAILY_FILE = "daily.json"

# 初期読み込み
def load_daily_data():
    if os.path.exists(DAILY_FILE):
        with open(DAILY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        return {}

# 保存
def save_daily_data(data):
    with open(DAILY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# 起動時に読み込み
user_responses = defaultdict(dict, load_daily_data())

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
SOURCE_CHANNEL_ID = int(os.getenv("SOURCE_CHANNEL_ID"))
DEST_CHANNEL_ID = int(os.getenv("DEST_CHANNEL_ID"))

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)
duel_sessions = {}  # ← ファイル先頭または duel/battle コマンドの前に追加


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


# 絵文字
PLAYER = "⭕"
CPU = "❌"
EMPTY = "⬜"


# --- ファイル読み込み ---
if os.path.exists("user_data.json"):
    with open("user_data.json", "r", encoding="utf-8") as f:
        user_data = json.load(f)
else:
    user_data = {}

if os.path.exists("gacha_items.json"):
    with open("gacha_items.json", "r", encoding="utf-8") as f:
        gacha_items = json.load(f)
else:
    gacha_items = {}

# --- レアリティ出現確率 ---
RARITY_RATES = {
    "伝説レア": 3,
    "超激レア": 7,
    "激レア": 15,
    "レア": 25,
    "ノーマル": 50
}
# 種類別の素材データ
item_types = ["剣", "弓", "槍", "鎧", "帽子", "ポーション", "果物", "動物", "召喚獣", "本", "装飾品", "機械"]
adjectives = ["炎の", "氷の", "神聖な", "呪われた", "暗黒の", "輝く", "幻の", "ミニ", "巨大な", "伝説の"]
suffixes = ["ブレード", "ハンマー", "ロッド", "アーマー", "クラウン", "エッグ", "エリクサー", "ソウル", "コア", "ボックス"]

# --- レアリティ絵文字 ---
RARITY_EMOJIS = {
    "伝説レア": "🟨",
    "超激レア": "🟥",
    "激レア": "🟪",
    "レア": "🟦",
    "ノーマル": "⚪️"
}

def choose_rarity():
    rarities = [
        ("legendary", 1),
        ("epic", 4),
        ("rare", 15),
        ("uncommon", 30),
        ("common", 50),
    ]

    total = sum(prob for _, prob in rarities)
    pick = random.uniform(0, total)
    current = 0
    for rarity, prob in rarities:
        current += prob
        if pick <= current:
            return rarity


# 100個のアイテムを生成
items = []
for i in range(100):
    name = f"{random.choice(adjectives)}{random.choice(item_types)}{random.choice(suffixes)}"
    rarity = choose_rarity()
    item = {
        "id": i + 1,
        "name": name,
        "rarity": rarity
    }
    items.append(item)

# JSONに保存
with open("gacha_items.json", "w", encoding="utf-8") as f:
    json.dump(items, f, ensure_ascii=False, indent=2)

print("✅ gacha_items.json を生成しました（100アイテム）")

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
        "coins": 0,
    }

    if user_id not in player_data:
        player_data[user_id] = defaults.copy()
    else:
        for key, value in defaults.items():
            if key not in player_data[user_id]:
                player_data[user_id][key] = value

# --- 抽選関数 ---
def draw_item():
    rarities = list(RARITY_RATES.keys())
    weights = list(RARITY_RATES.values())
    selected_rarity = random.choices(rarities, weights=weights)[0]
    item_list = [item for item, r in gacha_items.items() if r == selected_rarity]
    item = random.choice(item_list)
    return item, selected_rarity

# --- コインチェック ---
def get_user_coins(user_id):
    return user_data.get(str(user_id), {}).get("coins", 0)

def modify_user_coins(user_id, delta):
    uid = str(user_id)
    if uid not in user_data:
        user_data[uid] = {"coins": 0, "items": []}
    user_data[uid]["coins"] += delta
    with open("user_data.json", "w", encoding="utf-8") as f:
        json.dump(user_data, f, ensure_ascii=False, indent=2)

# --- 所持アイテム保存 ---
def add_user_item(user_id, item):
    uid = str(user_id)
    if uid not in user_data:
        user_data[uid] = {"coins": 0, "items": []}
    user_data[uid]["items"].append(item)
    with open("user_data.json", "w", encoding="utf-8") as f:
        json.dump(user_data, f, ensure_ascii=False, indent=2)

# --- ガチャView ---
class GachaView(View):
    def __init__(self):
        super().__init__(timeout=None)

        self.add_item(Button(label="1回ガチャ", style=discord.ButtonStyle.primary, custom_id="gacha1"))
        self.add_item(Button(label="10連ガチャ", style=discord.ButtonStyle.success, custom_id="gacha10"))


# CPU AIロジック
def get_best_move(board: list[str]) -> int:
    win_combos = [
        [0,1,2],[3,4,5],[6,7,8],
        [0,3,6],[1,4,7],[2,5,8],
        [0,4,8],[2,4,6]
    ]
    for symbol in [CPU, PLAYER]:
        for combo in win_combos:
            values = [board[i] for i in combo]
            if values.count(symbol) == 2 and values.count(EMPTY) == 1:
                return combo[values.index(EMPTY)]
    empty_cells = [i for i, v in enumerate(board) if v == EMPTY]
    return random.choice(empty_cells) if empty_cells else -1

# 勝敗チェック
def check_winner(board: list[str], symbol: str) -> bool:
    win_combos = [
        [0,1,2],[3,4,5],[6,7,8],
        [0,3,6],[1,4,7],[2,5,8],
        [0,4,8],[2,4,6]
    ]
    return any(all(board[i] == symbol for i in combo) for combo in win_combos)

class TicTacToeButton(Button):
    def __init__(self, index: int, game):
        super().__init__(style=discord.ButtonStyle.secondary, label=EMPTY, row=index // 3, custom_id=str(index))
        self.index = index
        self.game = game

    async def callback(self, interaction: discord.Interaction):
        if self.game.board[self.index] != EMPTY:
            return await interaction.response.send_message("そのマスはすでに埋まっています！", ephemeral=True)

        # プレイヤーの手
        self.game.board[self.index] = PLAYER
        self.label = PLAYER
        self.disabled = True

        # 勝敗チェック（プレイヤー）
        if check_winner(self.game.board, PLAYER):
            await self.game.update_view(interaction, end_message="🎉 あなたの勝ち！")
            return

        # 引き分けチェック
        if EMPTY not in self.game.board:
            await self.game.update_view(interaction, end_message="🤝 引き分けです！")
            return

        # CPUの手
        cpu_move = get_best_move(self.game.board)
        if cpu_move != -1:
            self.game.board[cpu_move] = CPU
            cpu_button = self.game.buttons[cpu_move]
            cpu_button.label = CPU
            cpu_button.disabled = True

            # 勝敗チェック（CPU）
            if check_winner(self.game.board, CPU):
                await self.game.update_view(interaction, end_message="💻 CPUの勝ち！")
                return

        # 引き分け再チェック
        if EMPTY not in self.game.board:
            await self.game.update_view(interaction, end_message="🤝 引き分けです！")
            return

        # 次のターンへ
        await interaction.response.edit_message(view=self.game)

class TicTacToeGame(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.board = [EMPTY] * 9
        self.buttons = [TicTacToeButton(i, self) for i in range(9)]
        for btn in self.buttons:
            self.add_item(btn)

    async def update_view(self, interaction, end_message: str):
        for btn in self.buttons:
            btn.disabled = True
        await interaction.response.edit_message(content=end_message, view=self)


def convert_old_items(inventory):
    converted = []
    for item in inventory:
        if isinstance(item, str):
            converted.append({
                "name": item,
                "rarity": "common"
            })
        elif isinstance(item, dict):
            converted.append(item)
    return converted

def convert_inventory_for_user(user_id: str):
    raw_inventory = player_data.get(user_id, {}).get("inventory", [])
    player_data[user_id]["inventory"] = convert_old_items(raw_inventory)


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

fake_responses = [
    "🟩 本当っぽいね…",
    "🟥 嘘くさいかも。",
    "🟨 微妙…判定不能",
    "🧠 科学的にはありえる！",
    "🤯 嘘にしては説得力ありすぎ！",
    "😅 それ、夢の中で見たとかじゃない？",
    "🙄 それは盛ってるでしょ…",
    "👀 証拠がないと信じられないな。",
    "🧙‍♂️ 魔法でもないと無理でしょ！",
    "😎 本当だとしてもすごすぎる！",
    "👻 都市伝説かな…？",
    "🤖 AIの私でも判断不能。",
    "👽 宇宙人にしかわからない真実かも。",
    "🤔 その話、前にも誰かが言ってたような…",
    "💤 嘘か本当かより、眠くなる話だね。"
]

# お題リスト（例追加済み）
daily_prompts = [
    "今日のラッキーアイテムは？",
    "怒った猫の気持ちを代弁せよ",
    "もし明日が世界最後の日なら？",
    "今の気分を一言で！",
    "あなたの秘密の趣味をこっそり教えて",
    "最強の言い訳とは？",
    "子供のころの夢は？",
    "今日一番嬉しかったことは？",
    "理想の朝ごはんは？",
    "次に生まれ変わるなら何になりたい？",
    "自分を漢字一文字で表すと？",
    "最近「やっちまった」ことは？",
    "無人島に一つだけ持っていくなら？"
]

ratings = [
    "🌟素晴らしい！", "😆おもしろい！", "🤔深い…",
    "💡なるほど！", "😮予想外！", "👍いいね！", "😂笑った",
    "👏見事！", "✨キラリと光る", "🧠賢い！", "🔥熱いね！"
]

tags = [
    "#哲学", "#ネタ", "#ほっこり", "#感情", "#ちょっと変",
    "#共感", "#謎すぎる", "#知的", "#笑撃", "#妄想"
]

# user_id -> date_str -> 回答データ
user_responses = defaultdict(dict)

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


async def geocode(city_name):
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": city_name,
        "format": "json",
        "limit": 1,
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            if len(data) == 0:
                return None
            lat = data[0]["lat"]
            lon = data[0]["lon"]
            return float(lat), float(lon)


@bot.command()
async def tenki(ctx, *, city: str = None):
    if city is None:
        await ctx.send(f"{ctx.author.mention} どの都市の天気を知りたいですか？ 返信してください。")

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        try:
            msg = await bot.wait_for("message", timeout=30.0, check=check)
            city = msg.content.strip()
        except asyncio.TimeoutError:
            await ctx.send("時間切れです。コマンドをキャンセルしました。")
            return

    coords = await geocode(city)
    if not coords:
        await ctx.send(f"{city} の場所が見つかりませんでした。")
        return

    lat, lon = coords
    weather_url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current_weather": "true",
        "timezone": "Asia/Tokyo",
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(weather_url, params=params) as resp:
            if resp.status != 200:
                await ctx.send("天気情報が取得できませんでした。")
                return
            weather_data = await resp.json()
            current = weather_data.get("current_weather", {})
            if not current:
                await ctx.send("現在の天気情報がありません。")
                return

            temp = current.get("temperature")
            windspeed = current.get("windspeed")
            weather_code = current.get("weathercode")

            weather_desc = {
                0: "晴れ",
                1: "主に晴れ",
                2: "部分的に曇り",
                3: "曇り",
                45: "霧",
                48: "凍結霧",
                51: "弱い霧雨",
                53: "中程度の霧雨",
                55: "強い霧雨",
                56: "凍結弱い霧雨",
                57: "凍結強い霧雨",
                61: "弱い雨",
                63: "中程度の雨",
                65: "強い雨",
                66: "凍結弱い雨",
                67: "凍結強い雨",
                71: "弱い雪",
                73: "中程度の雪",
                75: "強い雪",
                77: "あられ",
                80: "弱いにわか雨",
                81: "中程度のにわか雨",
                82: "強いにわか雨",
                85: "弱いにわか雪",
                86: "強いにわか雪",
                95: "雷雨",
                96: "弱い雷雨とあられ",
                99: "強い雷雨とあられ"
            }

            desc = weather_desc.get(weather_code, "不明な天気")

            await ctx.send(f"**{city}** の現在の天気:\n気温: {temp}°C\n風速: {windspeed} km/h\n天気: {desc}")

def test_convert():
    player_inventory = ["石", "丸石", {"name": "炎の剣", "rarity": "legendary"}]
    converted = convert_old_items(player_inventory)
    print(converted)

if __name__ == "__main__":
    test_convert()



@bot.command()
async def mine(ctx):
    user_id = str(ctx.author.id)
    ensure_player_defaults(user_id)

    # アイテム抽選
    weighted_items = (
        RARITY["common"] * 50 +
        RARITY["uncommon"] * 30 +
        RARITY["rare"] * 15 +
        RARITY["epic"] * 4 +
        RARITY["legendary"] * 1
    )
    found_item = random.choice(weighted_items)
    player_data[user_id]["inventory"].append(found_item)

    # 経験値
    gained_xp = random.randint(1, 5)
    player_data[user_id]["exp"] += gained_xp

    # コイン獲得（5〜15枚）
    gained_coins = random.randint(5, 15)
    player_data[user_id]["coins"] += gained_coins

    # レベルアップ処理
    while player_data[user_id]["exp"] >= 100:
        player_data[user_id]["exp"] -= 100
        player_data[user_id]["level"] += 1
        await ctx.send(f"🎉 {ctx.author.display_name} さん、レベルアップ！ 現在レベル {player_data[user_id]['level']} です！")

    save_data()

    await ctx.send(
        f"⛏️ {ctx.author.display_name} は {found_item} を採掘！（経験値 +{gained_xp}, コイン +{gained_coins}）"
    )


@bot.command(name="fake")
async def fake(ctx, *, message: str):
    result = random.choice(fake_responses)
    await ctx.send(f"💬 「{message}」\n→ {result}")

    
@bot.command(name="marubatu")
async def start_marubatu(ctx):
    game = TicTacToeGame()
    await ctx.send("⭕ あなた vs ❌ CPU の ○×ゲーム！", view=game)

@bot.event
async def on_interaction(interaction):
    if interaction.type == discord.InteractionType.component:
        user = interaction.user
        uid = str(user.id)
        if uid not in user_data:
            user_data[uid] = {"coins": 1500, "items": []}  # 初期コイン

        if interaction.data["custom_id"] == "gacha1":
            if get_user_coins(uid) < 150:
                await interaction.response.send_message("💸 コインが足りません！（150枚必要）", ephemeral=True)
                return
            modify_user_coins(uid, -150)
            item, rarity = draw_item()
            add_user_item(uid, item)
            emoji = RARITY_EMOJIS[rarity]
            await interaction.response.send_message(f"{emoji}【{rarity}】『{item}』をゲット！")

        elif interaction.data["custom_id"] == "gacha10":
            if get_user_coins(uid) < 1500:
                await interaction.response.send_message("💸 コインが足りません！（1500枚必要）", ephemeral=True)
                return
            modify_user_coins(uid, -1500)
            result_dict = {r: [] for r in RARITY_RATES}
            for _ in range(10):
                item, rarity = draw_item()
                add_user_item(uid, item)
                result_dict[rarity].append(item)

            result_msg = "🎉 10連ガチャ結果 🎉\n"
            for r in RARITY_RATES:
                items = result_dict[r]
                if items:
                    emoji = RARITY_EMOJIS[r]
                    result_msg += f"{emoji}【{r}】\n- " + "\n- ".join(items) + "\n"

            await interaction.response.send_message(result_msg)


@bot.command()
async def spin(ctx):
    user_id = str(ctx.author.id)
    ensure_player_defaults(user_id)

    wheel = [
        ("🎉 レアアイテム獲得！", "ダイヤモンド"),
        ("😎 ゴールド x5！", "ゴールド", 5),
        ("💤 ハズレ…", None),
        ("🍰 ケーキをゲット！", "ケーキ"),
        ("🧪 回復薬 x1", "回復薬", 1),
        ("🔥 エピック武器！", random.choice(["TNT", "トライデント", "呪いの魔法"])),
    ]

    result = random.choice(wheel)
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
async def clock(ctx):
    import pytz
    from datetime import datetime
    tz = pytz.timezone('Asia/Tokyo')
    now = datetime.now(tz)
    hour = now.hour

    if 5 <= hour < 10:
        greetings = [
            "おはようございます！今日もがんばろう！",
            "おはよう！素敵な一日を！",
            "朝の光が気持ちいいね！",
            "早起きは三文の得だよ！"
        ]
    elif 10 <= hour < 17:
        greetings = [
            "こんにちは！調子はどう？",
            "良い午後を過ごしてね！",
            "今日も元気にいこう！",
            "午後もファイト！"
        ]
    elif 17 <= hour < 21:
        greetings = [
            "こんばんは！一日お疲れさま！",
            "夕方だね。ゆっくり休んでね。",
            "夜も元気に過ごそう！",
            "そろそろリラックスタイムだね。"
        ]
    else:
        greetings = [
            "もう遅いけどお疲れさま！",
            "夜更かしはほどほどにね。",
            "おやすみ前のひとときを大切に。",
            "ぐっすり眠って明日に備えよう！"
        ]

    greeting = random.choice(greetings)
    await ctx.send(f"{greeting}（現在の日本時間：{now.strftime('%Y-%m-%d %H:%M:%S')}）")

@bot.event
async def on_ready():
    print(f"✅ 起動しました: {bot.user}")
    channel = bot.get_channel(DEST_CHANNEL_ID)
    if channel:
        await channel.send("✅ Botが現在オンラインです！（使用可能）")

@bot.event
async def on_disconnect():
    print("⚠️ 切断されました")
    channel = bot.get_channel(DEST_CHANNEL_ID)
    if channel:
        try:
            await channel.send("⚠️ Botは現在メンテナンスモードです。復旧をお待ちください。")
        except Exception:
            pass  # 切断時は送れない場合もあるので例外回避


@commands.command(name="daily")
async def daily(ctx):
    user_id = str(ctx.author.id)
    today = datetime.date.today().isoformat()

    # すでに回答済み？
    if today in user_responses[user_id]:
        await ctx.send(f"{ctx.author.mention} 今日はもう答えてるよ！また明日🎉")
        return

    # お題選定（固定インデックス or 完全ランダムも可）
    prompt_index = hash(today) % len(daily_prompts)
    prompt = daily_prompts[prompt_index]

    await ctx.send(f"🎯 今日のお題:\n> **{prompt}**\n\n30秒以内に答えてね！")

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    try:
        msg = await ctx.bot.wait_for("message", timeout=30.0, check=check)
        response = msg.content.strip()

        rating = random.choice(ratings)
        tag = random.choice(tags)

        # 保存（上書きなし）
        user_responses[user_id][today] = {
            "prompt": prompt,
            "response": response,
            "rating": rating,
            "tag": tag
        }

        await ctx.send(
            f"📝 あなたの回答: **{response}**\n{rating} {tag}"
        )

    except asyncio.TimeoutError:
        await ctx.send(f"{ctx.author.mention} 時間切れだよ〜😢 また挑戦してね！")


@commands.command(name="daily_history")
async def daily_history(ctx):
    user_id = str(ctx.author.id)
    responses = user_responses.get(user_id, {})

    if not responses:
        await ctx.send(f"{ctx.author.mention} まだ回答履歴がないよ！ `/daily` で始めよう🎯")
        return

    lines = []
    sorted_days = sorted(responses.keys(), reverse=True)[:7]
    for date in sorted_days:
        entry = responses[date]
        lines.append(f"📅 {date}: `{entry['prompt']}`\n→ **{entry['response']}** {entry['rating']} {entry['tag']}")

    await ctx.send(f"🗂 **{ctx.author.name} の履歴**（最新7件）:\n\n" + "\n\n".join(lines))

@commands.command(name="daily_leaderboard")
async def daily_leaderboard(ctx):
    today = datetime.date.today().isoformat()
    results = []

    for user_id, records in user_responses.items():
        if today in records:
            entry = records[today]
            user = await ctx.bot.fetch_user(int(user_id))
            results.append((user.name, entry["response"], entry["rating"], entry["tag"]))

    if not results:
        await ctx.send("📊 まだ誰も今日の回答をしていないみたい！ `/daily` で一番乗りしよう🎯")
        return

    random.shuffle(results)
    lines = []
    for i, (name, response, rating, tag) in enumerate(results[:5], start=1):
        lines.append(f"**#{i}** `{name}`: {response} {rating} {tag}")

    await ctx.send("🏆 **今日の面白回答ランキング**\n\n" + "\n".join(lines))


@commands.command(name="daily_edit")
async def daily_edit(ctx):
    user_id = str(ctx.author.id)
    today = datetime.date.today().isoformat()

    if today not in user_responses[user_id]:
        await ctx.send(f"{ctx.author.mention} まだ今日の回答がないよ！ `/daily` から始めてね。")
        return

    await ctx.send("✏️ 新しい回答を30秒以内に入力してね！")

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    try:
        msg = await ctx.bot.wait_for("message", timeout=30.0, check=check)
        new_response = msg.content.strip()

        # 上書き処理
        rating = random.choice(ratings)
        tag = random.choice(tags)
        user_responses[user_id][today]["response"] = new_response
        user_responses[user_id][today]["rating"] = rating
        user_responses[user_id][today]["tag"] = tag

        await ctx.send(f"✅ 回答を更新したよ！\n→ **{new_response}** {rating} {tag}")
    except asyncio.TimeoutError:
        await ctx.send(f"{ctx.author.mention} 時間切れ！もう一度 `/daily_edit` を試してね。")


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

        save_data()

        await ctx.send(f"✅ トレード成功！{ctx.author.display_name} → {target.display_name} に `{item_name}` を渡しました。")
    except asyncio.TimeoutError:
        await ctx.send("⏳ 時間切れです。トレードはキャンセルされました。")
    except Exception as e:
        await ctx.send(f"トレード中にエラーが発生しました: {e}")



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

    # ここで保存！
    save_data()

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
        player_data[user_id]["pet"] = {"name": "ゴーレム", "level": 1, "exp": 0}

        # ここで保存！
        save_data()

        await ctx.send(f"{ctx.author.display_name} に新しいペット『ゴーレム』が仲間になりました！")
    else:
        pet["exp"] += 10
        if pet["exp"] >= 100:
            pet["level"] += 1
            pet["exp"] -= 100

            # ここで保存！
            save_data()

            await ctx.send(f"ペット『{pet['name']}』がレベルアップ！現在レベル {pet['level']}！")
        else:
            # ここで保存（expだけ増えたので）
            save_data()

            await ctx.send(f"ペット『{pet['name']}』は経験値を {pet['exp']}/100 ためました。")



@bot.command()
async def inventory(ctx):
    user_id = str(ctx.author.id)

    # player_dataの存在チェック
    if user_id not in player_data:
        player_data[user_id] = {"inventory": []}

    raw_inventory = player_data[user_id].get("inventory", [])
    # 旧形式アイテムを変換
    player_data[user_id]["inventory"] = convert_old_items(raw_inventory)

    inv = player_data[user_id]["inventory"]
    if not inv:
        await ctx.send("あなたのインベントリは空です。まずは `!mine` や `!gachaMine` でアイテムを集めましょう！")
        return

    # ここにインベントリ表示の処理などを書く
    await ctx.send(f"あなたのインベントリ: {inv}")


    # 以下はレアリティごとに表示用の埋め込みとか続く感じですね


    # レアリティの表示順
    rarity_order = ["legendary", "epic", "rare", "uncommon", "common"]
    rarity_labels = {
        "legendary": "🌈伝説レア",
        "epic": "💎超激レア",
        "rare": "🔶激レア",
        "uncommon": "🔷レア",
        "common": "⚪ノーマル"
    }

    pages = []
    items_per_page = 8
    all_lines = []

    for rarity in rarity_order:
        if rarity not in grouped:
            continue
        lines = [f"__**{rarity_labels[rarity]}**__"]
        for name, count in grouped[rarity].items():
            lines.append(f"{name} x{count}")
        all_lines.extend(lines)

    # ページ分け
    for i in range(0, len(all_lines), items_per_page):
        chunk = all_lines[i:i + items_per_page]
        embed = discord.Embed(
            title=f"{ctx.author.display_name} のインベントリ 🧳",
            description="\n".join(chunk),
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"ページ {i // items_per_page + 1}/{(len(all_lines) + items_per_page - 1) // items_per_page}")
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
        await ctx.send("まずは !mine でゲームを開始してください。")
        return

    inv = player_data[user_id]["inventory"]
    if item_name not in inv:
        await ctx.send(f"{item_name} はインベントリに存在しません。")
        return

    # 装備判定ロジック（修正版）
    if item_name in WEAPONS:
        if WEAPONS[item_name]["defense"] > 0:
            player_data[user_id]["armor"] = item_name
            await ctx.send(f"{ctx.author.display_name} は {item_name} を装備しました（防御用）。")
        else:
            player_data[user_id]["weapon"] = item_name
            await ctx.send(f"{ctx.author.display_name} は {item_name} を装備しました（攻撃用）。")
    else:
        await ctx.send(f"{item_name} は装備できません。武器または盾のみ装備可能です。")

        # 登録時の名前（ニックネーム）を保存
@bot.command()
async def register(ctx, name: str = None):
    user_id = str(ctx.author.id)

    if user_id in player_data:
        await ctx.send("すでに登録されています。")
        return

    if name is None:
        name = ctx.author.display_name

    # 同じ名前が使われていないかチェック
    if any(p["name"] == name for p in player_data.values()):
        await ctx.send("この名前はすでに使われています。別の名前を選んでください。")
        return

    player_data[user_id] = {
        "name": name,
        "hp": 100,
        "atk": 10,
        "def": 5,
        "location": "拠点",
        "mode": "normal"
    }
    save_data()
    await ctx.send(f"{name}さんを登録しました！")

# 名前からuser_idを探す
def find_user_id_by_name(name: str):
    for user_id, data in player_data.items():
        if data["name"] == name:
            return user_id
    return None

# --------------------
# 🎮 マイクラ風ストーリーゲーム


@bot.command()
async def story(ctx, who: str = None):
    players = ["れむらむ", "ゆうた", "こもねこ", "ばーど", "ふるねこ", "ぎょふ",
               "ぷろわん", "まめちー", "うに", "ノックス", "わたあめ", "みこ"]

    if not who:
        if not player_data:
            await ctx.send("プレイヤーが登録されていません。")
            return
        who = random.choice(list(player_data.values()))["name"]

    # プレイヤー絡みの対象は登録済みの中から who を除く
    others = [p for p in players if p != who]

    player_actions = [
        lambda w, t: f"{w}が{t}を殴った",
        lambda w, t: f"{w}が{t}に爆笑ジョークを言った",
        lambda w, t: f"{w}が{t}とエンダードラゴンに挑んだ",
        lambda w, t: f"{w}が{t}のチェストをこっそり開けた",
        lambda w, t: f"{w}が{t}の家をTNTで爆破した",
        lambda w, t: f"{w}が{t}にサトウキビを投げつけた",
        lambda w, t: f"{w}が{t}にマグマダイブを強要した",
        lambda w, t: f"{w}が{t}とトロッコレースで勝負した",
        lambda w, t: f"{w}が{t}にラップバトルを挑んだ",
        lambda w, t: f"{w}が{t}のベッドを隠した"
    ]

    solo_actions = [
        "クリーパーに話しかけた", "TNTを設置した", "村人を叩いた", "ゾンビピッグマンを挑発した",
        "ダイヤを拾った", "ネコを手懐けた", "ベッドを壊した", "ポーションを全部飲んだ",
        "コマンドブロックを触った", "Witherを召喚した", "ドラゴンに投げキッスした",
        "トロッコで暴走した", "彼女を作った", "エリトラで空を飛んだ", "バケツで溶岩を飲んだ",
        "旗を燃やした", "ラマを怒らせた", "エンダーパールを投げまくった", "カボチャを被ったままプロポーズした",
        "ビーコンに爆竹を挿した", "ベッドで爆睡した", "サトウキビで自宅建築した",
        "ネザーラックを全部舐めた", "エンダーマンにラップバトルを仕掛けた",
        "ゾンビに恋文を渡した", "スポナーで盆踊りした", "豚に乗って競馬を始めた",
        "空腹で建築しながら歌った", "ピストンでジャンプ台を作った", "ディスペンサーに頭を突っ込んだ"
    ]

    places = [
        "ネザー", "エンド", "村", "洞窟", "渓谷", "天空の島", "森林バイオーム", "海底神殿", "廃坑",
        "ピリジャーの前線基地", "溶岩の海", "雪山", "監獄", "図書館", "要塞", "砂漠の寺院", "キノコ島",
        "スポナー部屋", "儀式の間", "巨大スライムの巣", "古代都市", "スニッファーの巣", "村の祭壇",
        "迷子のネザーゲート", "カカシ農園", "天空バーガーショップ", "謎の和室", "レッドストーン銀行",
        "廃墟のラーメン屋", "ウーパールーパー温泉", "トロッコ高速道路", "虚無空間", "ベッドウォーズの戦場",
        "深海ファミレス", "異次元のトイレ"
    ]

    results = [
        "家が吹き飛んだ", "全ロスした", "敵が大群で襲ってきた", "サーバーが落ちた",
        "村人に通報された", "ネザーゲートが消えた", "リアルの世界にバグった",
        "MODが暴走した", "BANされた", "天空から落下した", "クリーパーにプロポーズされた",
        "コマンドが暴走した", "ベッドが爆発した", "全プレイヤーが泣いた",
        "スティーブの記憶が消えた", "マイクラが映画化された", "村人が歌いだした",
        "アイテムが全部ジャガイモになった", "エンダードラゴンがペットになった",
        "洞窟のBGMで泣いた", "チートがバレて謝罪会見した", "牛に優しくされた",
        "エリトラで月まで飛んだ", "クリーパーと結婚式を挙げた", "石炭で人生逆転した",
        "謎の司書に弟子入りした", "マグマに愛を捧げた", "全チャットが『草』になった",
        "レッドストーンに意志が芽生えた", "ベッドで爆死して配信BANされた", "ヤギにホームを奪われた",
        "スポーン地点が寿司屋になった", "ダイヤが全部スライムに変わった", "FPSが3になった",
        "世界を滅ぼした", "トラップにかかった", "あほになってしまった", "突然スニーカーを履いた",
        "ネザーで踊り出した", "光の速さで逃げ出した", "豚になった", "ブロックが喋り出した",
        "インベントリがパンケーキで満タンになった", "一生マグマダイブし続けた", "全ての看板が意味不明になった",
        "ゾンビに転職した", "スティーブが泣きながら謝った", "ワールドが回転し始めた",
        "リアルで叫んだらBANされた", "謎の声に説教された", "スケルトンに壁ドンされた",
        "村人から借金を背負わされた", "エンダーパールが爆発した", "全員が透明人間になった"
    ]

    place = random.choice(places)
    result = random.choice(results)

    # ランダムにプレイヤー絡み or 単独行動を決める
    if random.choice([True, False]) and others:
        target = random.choice(others)
        action = random.choice(player_actions)(who, target)
    else:
        action = random.choice(solo_actions)

    await ctx.send(f"🎮 **{who}** が **{place}** で **{action}** から、**{result}**！")





@bot.command()
async def attack(ctx, target_input: str = None):
    attacker_id = str(ctx.author.id)

    if attacker_id not in player_data:
        await ctx.send("まずは `!register 名前` で登録してください。")
        return

    if target_input is None:
        await ctx.send("攻撃する相手を指定してください（@メンション または プレイヤー名）")
        return

    # --- 対象がメンション（ID形式）なら変換 ---
    if target_input.startswith("<@") and target_input.endswith(">"):
        # メンション形式 → ID取得
        target_id = target_input.replace("<@", "").replace("!", "").replace(">", "")
        target_member = await ctx.guild.fetch_member(int(target_id))
        target_name = target_member.display_name
    else:
        # プレイヤー名から検索
        target_id = find_user_id_by_name(target_input)
        if not target_id:
            await ctx.send(f"「{target_input}」というプレイヤーは見つかりません。")
            return
        target_name = target_input

    if target_id == attacker_id:
        await ctx.send("自分自身を攻撃することはできません。")
        return

    if target_id not in player_data:
        await ctx.send("相手はまだ登録されていません。")
        return

    attacker = player_data[attacker_id]
    defender = player_data[target_id]

    if not defender.get("alive", True):
        await ctx.send(f"{target_name} はすでに倒れています。")
        return

    weapon = attacker.get("weapon", "素手")
    attack_range = WEAPONS.get(weapon, WEAPONS["素手"])["attack"]
    attack_value = random.randint(*attack_range)

    armor_name = defender.get("armor")
    defense_value = 0
    if armor_name and armor_name in WEAPONS:
        defense_value = WEAPONS[armor_name]["defense"]

    damage = max(attack_value - defense_value, 0)
    defender["hp"] = max(defender.get("hp", 100) - damage, 0)

    msg = f"{attacker['name']} は {target_name} に {damage} のダメージを与えた！ (残りHP: {defender['hp']})"

    if defender["hp"] <= 0:
        defender["alive"] = False
        msg += f"\n💀 {target_name} は倒れた…"

    save_data()
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
        "・`!spin`：ルーレットで運試し！🎰\n\n"
        "・`!story`：ストーリー作成できるよ！\n\n"
        "・`!register`：プレイヤー登録できるよ！\n\n"
        "・`!clock`：現在の時間が分かるよ!\n\n"
        "・`!tenki`：現在の天気が分かるよ!\n\n"
        "ゲームの冒険を存分に楽しんでくださいね！"
    )
    await ctx.send(help_text)

@bot.command()
async def hyoka(ctx, target: str):
    score = random.randint(0, 100)

    if score <= 20:
        comments = [
            "あほかお前！もう一回やり直せｗ",
            "うーん…頑張れ！まだ生きてるよな？",
            "なんでそんなミスするんやｗｗｗ",
            "0点じゃねーか！いや、0点だけどな！"
        ]
    elif score <= 40:
        comments = [
            "まあまあだなｗ",
            "ちょっとはマシになったな…まだまだだけど！",
            "惜しい！惜しいけど惜しいだけ！",
            "まあまあ、空気読んで頑張れや！"
        ]
    elif score <= 60:
        comments = [
            "そこそこやるやん、悪くないぞ！",
            "普通にできてるやん！サンキュー！",
            "ふむふむ、意外とやるなコイツ！",
            "よしよし、今日はここまでで許したる！"
        ]
    elif score <= 80:
        comments = [
            "お、なかなかイケてるやん！その調子！",
            "いいねぇ、調子乗ってええで！",
            "バッチリやん、尊敬するわ！",
            "完璧ちゃうけど、もう合格点やで！"
        ]
    else:
        comments = [
            "神か！あんたは神様か！",
            "これ以上は無理！大正解！",
            "いや、マジで天才やな、お前！",
            "100点満点！なんも言うことなし！"
        ]

    comment = random.choice(comments)
    await ctx.send(f"評価対象: {target}\n評価結果: {score}%\nコメント：{comment}")

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

    # ここで保存！
    save_data()

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

