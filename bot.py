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
import math




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

GRID_SIZE = 5
NUM_MINES = 5

ROWS = 6
COLUMNS = 7

DIFFICULTY = {
    "easy": (5, 5, 3),     # 行, 列, 爆弾数
    "normal": (7, 7, 10),
    "hard": (9, 9, 20)
}
EMOJIS = {
    None: "⚪",
    0: "🔴",  # プレイヤー1
    1: "🔵",  # プレイヤー2
}

# 絵文字
PLAYER = "⭕"
CPU = "❌"
EMPTY = "⬜"

# 安全に評価する辞書
safe_dict = {
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log10,
    "ln": math.log,
    "sqrt": math.sqrt,
    "pi": math.pi,
    "e": math.e,
    "__builtins__": {}
}


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
ojisan_lines = [
    "🧔「やあ、君も桜を見に来たのかい？」",
    "🧔「彗星よりも君のほうが輝いてるね…ﾌﾋﾋ」",
    "🧔「今日も一人なの？ ぼくもだよ…」",
    "🧔「こっちにおいでよ、いい桜スポット知ってるんだ」",
]

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


class Connect4View(View):
    def __init__(self, player1, player2):
        super().__init__(timeout=None)
        self.players = [player1, player2]
        self.turn = 0
        self.board = [[None for _ in range(COLUMNS)] for _ in range(ROWS)]
        self.message = None
        self.finished = False

        for col in range(COLUMNS):
            self.add_item(Connect4Button(col))

    async def update_board(self):
        display = ""
        for row in self.board:
            display += "".join(EMOJIS[cell] for cell in row) + "\n"
        return display

    def drop_piece(self, col, player_index):
        for row in reversed(range(ROWS)):
            if self.board[row][col] is None:
                self.board[row][col] = player_index
                return row, col
        return None

    def check_winner(self, last_row, last_col, player_index):
        directions = [(1, 0), (0, 1), (1, 1), (1, -1)]

        for dx, dy in directions:
            count = 1

            for dir in [1, -1]:
                x, y = last_col, last_row
                while True:
                    x += dx * dir
                    y += dy * dir
                    if 0 <= x < COLUMNS and 0 <= y < ROWS and self.board[y][x] == player_index:
                        count += 1
                    else:
                        break
            if count >= 4:
                return True
        return False

    def board_full(self):
        return all(self.board[0][col] is not None for col in range(COLUMNS))


class Connect4Button(Button):
    def __init__(self, column):
        super().__init__(label=str(column + 1), style=discord.ButtonStyle.secondary)
        self.column = column

    async def callback(self, interaction: discord.Interaction):
        view: Connect4View = self.view
        if view.finished:
            return await interaction.response.send_message("このゲームはすでに終了しています。", ephemeral=True)

        current_player = view.players[view.turn]
        if interaction.user != current_player:
            return await interaction.response.send_message("あなたの番ではありません！", ephemeral=True)

        move = view.drop_piece(self.column, view.turn)
        if move is None:
            return await interaction.response.send_message("この列はもう埋まっています！", ephemeral=True)

        last_row, last_col = move
        if view.check_winner(last_row, last_col, view.turn):
            board_display = await view.update_board()
            view.finished = True
            for child in view.children:
                child.disabled = True
            await interaction.response.edit_message(content=f"{board_display}\n🎉 {current_player.mention} の勝ち！", view=view)
        elif view.board_full():
            board_display = await view.update_board()
            view.finished = True
            for child in view.children:
                child.disabled = True
            await interaction.response.edit_message(content=f"{board_display}\n🤝 引き分けです！", view=view)
        else:
            view.turn = 1 - view.turn
            board_display = await view.update_board()
            await interaction.response.edit_message(content=f"{board_display}\n{view.players[view.turn].mention} の番です！", view=view)

@bot.command(name="桜よ舞い降りろ！")
async def sakura(ctx):
    count = random.randint(1, 100)
    sakura_string = "🌸" * count

    if random.random() < 0.05:  # 5%の確率
        ojisan = random.choice(ojisan_lines)
        sakura_string += f"\n{ojisan}"

    await ctx.send(sakura_string)

@bot.command(name="彗星に願いを")
async def comet(ctx):
    count = random.randint(1, 100)
    comet_string = "☄️" * count

    if random.random() < 0.05:
        ojisan = random.choice(ojisan_lines)
        comet_string += f"\n{ojisan}"

    await ctx.send(comet_string)
    
@bot.command()
async def connect4(ctx, opponent: discord.Member):
    """2人用のConnect4（四目並べ）ゲームを開始します。"""
    if opponent.bot:
        return await ctx.send("Botとは対戦できません。")

    view = Connect4View(ctx.author, opponent)
    board_display = await view.update_board()
    await ctx.send(f"{board_display}\n{ctx.author.mention} vs {opponent.mention}\n{ctx.author.mention} の番です！", view=view)

def safe_eval(expr):
    try:
        expr = expr.replace("^", "**")  # "^" を pythonの "**" に変換
        result = eval(expr, {"__builtins__": None}, allowed_names)
        return str(result)
    except Exception as e:
        return f"⚠️ Error: {e}"


class CalculatorView(View):
    def __init__(self):
        super().__init__(timeout=180)
        self.expression = ""
        layout = [
            ["7", "8", "9", "/"],
            ["4", "5", "6", "*"],
            ["1", "2", "3", "-"],
            ["0", ".", "=", "+"],
            ["(", ")", "C", "√"],
            ["sin", "cos", "log", "DEL"]
        ]

        for row in layout:
            for item in row:
                self.add_item(CalcButton(label=item))

    async def update_message(self, interaction):
        await interaction.response.edit_message(content=f"`{self.expression or '0'}`", view=self)

class CalcButton(Button):
    def __init__(self, label):
        super().__init__(label=label, style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction):
        view: CalculatorView = self.view
        label = self.label

        if label == "=":
            try:
                expr = view.expression.replace("√", "sqrt")
                result = eval(expr, safe_dict)
                view.expression = str(result)
            except Exception:
                view.expression = "Error"
        elif label == "C":
            view.expression = ""
        elif label == "DEL":
            view.expression = view.expression[:-1]
        else:
            view.expression += label

        await view.update_message(interaction)

@bot.command()
async def calc(ctx):
    view = CalculatorView()
    await ctx.send("`0`", view=view)

class CellButton(Button):
    def __init__(self, x, y, is_bomb, view):
        super().__init__(label="⬛", style=discord.ButtonStyle.secondary, row=y)
        self.x = x
        self.y = y
        self.is_bomb = is_bomb
        self.revealed = False
        self.flagged = False

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.view.author:
            await interaction.response.send_message("これはあなたのゲームではありません。", ephemeral=True)
            return

        if self.revealed:
            return

        if self.flagged:
            self.flagged = False
            self.label = "⬛"
            await interaction.response.edit_message(view=self.view)
            return

        if interaction.data.get("custom_id", "").endswith("_flag"):
            self.flagged = True
            self.label = "🚩"
            await interaction.response.edit_message(view=self.view)
            return

        self.revealed = True
        if self.is_bomb:
            self.label = "💣"
            self.style = discord.ButtonStyle.danger
            await interaction.response.edit_message(content="💥 爆発しました！ゲームオーバー。", view=self.view)
            self.view.disable_all()
        else:
            count = self.view.count_adjacent_bombs(self.x, self.y)
            self.label = str(count) if count > 0 else " "
            self.style = discord.ButtonStyle.success
            await interaction.response.edit_message(view=self.view)
            self.view.check_win()


class MinesweeperView(View):
    def __init__(self, width, height, bombs, author):
        super().__init__(timeout=300)
        self.author = author
        self.width = width
        self.height = height
        self.bombs = bombs
        self.cells = {}

        # 爆弾配置
        bomb_positions = random.sample(range(width * height), bombs)
        for y in range(height):
            for x in range(width):
                idx = y * width + x
                is_bomb = idx in bomb_positions
                button = CellButton(x, y, is_bomb, self)
                self.cells[(x, y)] = button
                self.add_item(button)

    def get_neighbors(self, x, y):
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if 0 <= nx < self.width and 0 <= ny < self.height:
                    yield self.cells[(nx, ny)]

    def count_adjacent_bombs(self, x, y):
        return sum(1 for neighbor in self.get_neighbors(x, y) if neighbor.is_bomb)

    def check_win(self):
        unrevealed = [b for b in self.children if isinstance(b, CellButton) and not b.revealed and not b.is_bomb]
        if not unrevealed:
            for b in self.children:
                if isinstance(b, CellButton) and b.is_bomb:
                    b.label = "🚩"
                    b.style = discord.ButtonStyle.success
            self.disable_all()

    def disable_all(self):
        for b in self.children:
            if isinstance(b, CellButton):
                b.disabled = True


@bot.command()
async def tntgame(ctx, mode="easy"):
    if mode not in DIFFICULTY:
        await ctx.send("難易度は easy, normal, hard のいずれかです。")
        return

    width, height, bombs = DIFFICULTY[mode]
    view = MinesweeperView(width, height, bombs, ctx.author)
    await ctx.send(f"🧨 マインスイーパー（{mode}モード）を始めます！クリックして爆弾を避けよう。", view=view)


class FoodMakerView(View):
    def __init__(self, food_type):
        super().__init__(timeout=60)
        self.food_type = food_type
        self.steps = 0
        self.result = None

    @discord.ui.button(label="次の工程へ", style=discord.ButtonStyle.primary)
    async def next_step(self, interaction: discord.Interaction, button: Button):
        self.steps += 1

        if self.food_type == "takoyaki":
            if self.steps == 1:
                msg = "生地を混ぜています…🐙"
            elif self.steps == 2:
                msg = "タコを入れています…🐙"
            elif self.steps == 3:
                msg = "焼いています…🔥"
            else:
                msg = "たこ焼き完成！🎉"
                self.result = "たこ焼き"
                self.stop()
        elif self.food_type == "taiyaki":
            if self.steps == 1:
                msg = "生地を流し込み…🐟"
            elif self.steps == 2:
                msg = "あんこを入れています…🍡"
            elif self.steps == 3:
                msg = "焼いています…🔥"
            else:
                msg = "たい焼き完成！🎉"
                self.result = "たい焼き"
                self.stop()
        elif self.food_type == "icecream":
            if self.steps == 1:
                msg = "ミルクを用意しています…🥛"
            elif self.steps == 2:
                msg = "混ぜています…🍦"
            elif self.steps == 3:
                msg = "冷やしています…❄️"
            else:
                msg = "アイスクリーム完成！🎉"
                self.result = "アイスクリーム"
                self.stop()
        else:
            msg = "不明な料理です。"

        await interaction.response.edit_message(content=msg, view=self)

@bot.command()
async def takoyaki(ctx):
    view = FoodMakerView("takoyaki")
    await ctx.send("たこ焼き作り開始！ボタンを押して工程を進めてね。", view=view)

@bot.command()
async def taiyaki(ctx):
    view = FoodMakerView("taiyaki")
    await ctx.send("たい焼き作り開始！ボタンを押して工程を進めてね。", view=view)

@bot.command()
async def icecream(ctx):
    view = FoodMakerView("icecream")
    await ctx.send("アイスクリーム作り開始！ボタンを押して工程を進めてね。", view=view)

@bot.command()
async def speed(ctx):
    import time
    start = time.perf_counter()
    msg = await ctx.send("速度測定中…")
    end = time.perf_counter()
    latency = (end - start) * 1000  # ms
    await msg.edit(content=f"Botの応答速度は約 {latency:.1f} ms です。")

class WatameView(View):
    def __init__(self):
        super().__init__(timeout=60)
        self.size = 0
        self.max_size = random.randint(5, 10)  # 完成サイズ
        self.failed = False

        self.button = Button(label="ぐるぐるする🍭", style=discord.ButtonStyle.primary)
        self.button.callback = self.spin
        self.add_item(self.button)

    async def spin(self, interaction: discord.Interaction):
        if self.failed:
            return

        self.size += 1

        if self.size < self.max_size:
            await interaction.response.edit_message(
                content=f"綿あめぐるぐる中... {self.size}周目！🍬\n{self.size * '🍭'}",
                view=self
            )
        elif self.size == self.max_size:
            self.button.disabled = True
            await interaction.response.edit_message(
                content=f"🎉 完成！ふわふわ巨大綿あめができたよ！ {self.size}周！\n{'🍭' * self.size}",
                view=self
            )
        else:
            self.button.disabled = True
            self.failed = True
            await interaction.response.edit_message(
                content=f"💥 やりすぎた！綿あめが爆発した！ {self.size}周...\n💣🍬💣",
                view=self
            )


@bot.command()
async def watame(ctx):
    """綿あめぐるぐるゲームを始めるよ！"""
    view = WatameView()
    await ctx.send("🍬 綿あめメーカー起動！ボタンを押してふわふわにしよう！", view=view)

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


@bot.command()
async def mine(ctx):
    user_id = str(ctx.author.id)
    ensure_player_defaults(user_id)

    weighted_items = (
        RARITY["common"] * 50 +
        RARITY["uncommon"] * 30 +
        RARITY["rare"] * 15 +
        RARITY["epic"] * 4 +
        RARITY["legendary"] * 1
    )
    found_item = random.choice(weighted_items)
    player_data[user_id]["inventory"].append(found_item)

    gained_xp = random.randint(1, 5)
    player_data[user_id]["exp"] += gained_xp

    while player_data[user_id]["exp"] >= 100:
        player_data[user_id]["exp"] -= 100
        player_data[user_id]["level"] += 1
        await ctx.send(f"🎉 {ctx.author.display_name} さん、レベルアップ！ 現在レベル {player_data[user_id]['level']} です！")

    # 変更を保存
    save_data()

    await ctx.send(f"{ctx.author.display_name} は {found_item} を採掘しました！（経験値 +{gained_xp}）")

@bot.command(name="fake")
async def fake(ctx, *, message: str):
    result = random.choice(fake_responses)
    await ctx.send(f"💬 「{message}」\n→ {result}")

    
@bot.command(name="marubatu")
async def start_marubatu(ctx):
    game = TicTacToeGame()
    await ctx.send("⭕ あなた vs ❌ CPU の ○×ゲーム！", view=game)

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

def find_user_id_by_name(name: str):
    for uid, pdata in player_data.items():
        if pdata.get("name") == name:
            return uid
    return None

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
async def aho(ctx, target: str):
    comments = [
        f"{target}よ、あほあほ〜🤣",
        f"ゆうたで？{target}があほなのはみんな知ってるってｗ",
        f"{target}の脳みそ、今日は定休日？ww",
        f"いやマジで、{target}くん…さすがにそれは草🌿",
        f"{target}よ、もうちょっと賢く生まれてきてもよかったなｗ",
        f"{target}がまたやらかしたらしいで～ｗｗｗ",
        f"{target}、今週のあほランキング1位🎉",
        f"おい{target}、せめて漢字ドリルからやり直そか？ｗ",
        f"また{target}やんｗｗｗ名物アホ出ました〜ｗ"
    ]
    response = random.choice(comments)
    await ctx.send(response)
    
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

