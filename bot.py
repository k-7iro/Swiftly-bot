# Swiftly DiscordBot.
# Developed by: TechFish_1
import asyncio
import os
import json
import time
from typing import Final, Optional, Set, Dict, Any
import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

import aiosqlite
import dotenv
import discord
from discord.ext import commands

# logging.pyをインポート
from module.logging import LoggingCog

# 定数定義
SHARD_COUNT: Final[int] = 10
COMMAND_PREFIX: Final[str] = "sw!"
STATUS_UPDATE_COOLDOWN: Final[int] = 5
LOG_RETENTION_DAYS: Final[int] = 7

PATHS: Final[dict] = {
    "log_dir": Path("./log"),
    "db": Path("data/prohibited_channels.db"),
    "user_count": Path("data/user_count.json"),
    "cogs_dir": Path("./cogs")
}

ERROR_MESSAGES: Final[dict] = {
    "command_error": "エラーが発生しました",
    "prohibited_channel": "このチャンネルではコマンドの実行が禁止されています。",
    "db_error": "DBエラーが発生しました: {}"
}

LOG_FORMAT: Final[str] = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

logger = logging.getLogger(__name__)

class DatabaseManager:
    """DB操作を管理するクラス"""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection: Optional[aiosqlite.Connection] = None

    async def initialize(self) -> None:
        """DBを初期化"""
        self._connection = await aiosqlite.connect(self.db_path)
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS prohibited_channels (
                guild_id TEXT,
                channel_id TEXT,
                PRIMARY KEY (guild_id, channel_id)
            )
        """)
        await self._connection.commit()

    async def cleanup(self) -> None:
        """DB接続を閉じる"""
        if self._connection:
            await self._connection.close()
            self._connection = None

    async def is_channel_prohibited(
        self,
        guild_id: int,
        channel_id: int
    ) -> bool:
        try:
            if not self._connection:
                await self.initialize()

            async with self._connection.execute(
                """
                SELECT 1 FROM prohibited_channels
                WHERE guild_id = ? AND channel_id = ?
                """,
                (str(guild_id), str(channel_id))
            ) as cursor:
                return bool(await cursor.fetchone())

        except Exception as e:
            logger.error("Database error: %s", e, exc_info=True)
            return False

class UserCountManager:
    """ユーザー数管理を行うクラス"""

    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._last_update = 0
        self._cache: Dict[str, Any] = {}

    def _read_count(self) -> int:
        """ファイルからユーザー数を読み込み"""
        try:
            if self.file_path.exists():
                data = json.loads(self.file_path.read_text(encoding="utf-8"))
                return data.get("total_users", 0)
            return 0
        except Exception as e:
            logger.error("Error reading user count: %s", e, exc_info=True)
            return 0

    def _write_count(self, count: int) -> None:
        """ユーザー数をファイルに書き込み"""
        try:
            self.file_path.write_text(
                json.dumps(
                    {"total_users": count},
                    ensure_ascii=False,
                    indent=4
                ),
                encoding="utf-8"
            )
        except Exception as e:
            logger.error("Error writing user count: %s", e, exc_info=True)

    def get_count(self) -> int:
        """現在のユーザー数を取得"""
        return self._read_count()

    def update_count(self, count: int) -> None:
        self._write_count(count)
        self._last_update = time.time()

    def should_update(self) -> bool:
        """更新が必要かどうかを判定"""
        return time.time() - self._last_update >= STATUS_UPDATE_COOLDOWN

class SwiftlyBot(commands.Bot):
    """Swiftlyボットのメインクラス"""

    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.members = True
        intents.messages = True
        intents.message_content = True

        client = discord.AutoShardedClient(
            intents=intents,
            shard_count=SHARD_COUNT
        )

        super().__init__(
            command_prefix=COMMAND_PREFIX,
            intents=intents,
            client=client
        )

        self.db = DatabaseManager(PATHS["db"])
        self.user_count = UserCountManager(PATHS["user_count"])
        self._setup_logging()

    def _setup_logging(self) -> None:
        """ロギングの設定"""
        PATHS["log_dir"].mkdir(exist_ok=True)

        # コンソール出力用のハンドラを追加
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt='%Y-%m-%d %H:%M:%S'))

        # 共通のログハンドラ設定
        handlers = []
        for name, level in [("logs", logging.DEBUG), ("commands", logging.DEBUG)]:
            handler = TimedRotatingFileHandler(
                PATHS["log_dir"] / f"{name}.log",
                when="midnight",
                interval=1,
                backupCount=LOG_RETENTION_DAYS,
                encoding="utf-8"
            )
            handler.setLevel(level)
            handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt='%Y-%m-%d %H:%M:%S'))
            handlers.append(handler)

        # ボットのロガー設定
        logger.setLevel(logging.INFO)
        for handler in handlers:
            logger.addHandler(handler)
        logger.addHandler(console_handler)

        # Discordのロガー設定
        discord_logger = logging.getLogger("discord")
        discord_logger.setLevel(logging.INFO)
        for handler in handlers:
            discord_logger.addHandler(handler)
        discord_logger.addHandler(console_handler)

    async def setup_hook(self) -> None:
        """ボットのセットアップ処理"""
        await self.db.initialize()
        await self._load_extensions()
        await self.add_cog(LoggingCog(self))  # LoggingCogを追加
        await self.tree.sync()

    async def _load_extensions(self) -> None:
        """Cogを読み込み"""
        for file in PATHS["cogs_dir"].glob("*.py"):
            if file.stem == "__init__":
                continue

            try:
                await self.load_extension(f"cogs.{file.stem}")
                logger.info("Loaded: cogs.%s", file.stem)
            except Exception as e:
                logger.error("Failed to load: cogs.%s - %s", file.stem, e, exc_info=True)

    async def update_presence(self) -> None:
        """ステータスを更新"""
        while True:
            count = self.user_count.get_count()
            await self.change_presence(
                activity=discord.Game(
                    name=f"{count}人のユーザー数 || {round(self.latency * 1000)}ms"
                )
            )
            await asyncio.sleep(10)
            await self.change_presence(
                activity=discord.Game(
                    name=f"/help || {round(self.latency * 1000)}ms"
                )
            )
            await asyncio.sleep(10)

    async def count_unique_users(self) -> None:
        """ユニークユーザー数を集計"""
        unique_users: Set[int] = set()
        for guild in self.guilds:
            unique_users.update(member.id for member in guild.members)

        count = len(unique_users)
        logger.info("Unique user count: %s", count)
        self.user_count.update_count(count)
        await self.update_presence()

    async def on_ready(self) -> None:
        """準備完了時の処理"""
        logger.info("Logged in as %s", self.user)
        await self.count_unique_users()

    async def on_member_join(self, _) -> None:
        """メンバー参加時の処理"""
        await self.count_unique_users()

    async def on_member_remove(self, _) -> None:
        """メンバー退出時の処理"""
        await self.count_unique_users()

    async def on_app_command_error(
        self,
        interaction: discord.Interaction,
        error: discord.app_commands.AppCommandError
    ) -> None:
        """アプリケーションコマンドエラー時の処理"""
        logger.error("App command error: %s", error, exc_info=True)
        await interaction.response.send_message(
            ERROR_MESSAGES["command_error"],
            ephemeral=True
        )

    async def check_command_permissions(
        self,
        ctx: commands.Context
    ) -> bool:
        if not ctx.guild:
            return True

        if ctx.command and ctx.command.name == "set_mute_channel":
            return True

        is_prohibited = await self.db.is_channel_prohibited(
            ctx.guild.id,
            ctx.channel.id
        )
        if is_prohibited:
            await ctx.send(ERROR_MESSAGES["prohibited_channel"])
            return False
        return True

    async def check_slash_command(
        self,
        interaction: discord.Interaction
    ) -> bool:
        # DEV_USER_IDが設定されている場合、そのユーザーのみコマンドを実行可能
        dev_user_id = os.getenv("DEV_USER_ID")
        if dev_user_id and str(interaction.user.id) != dev_user_id:
            await interaction.response.send_message(
                "このコマンドは開発者のみが実行できます。",
                ephemeral=True
            )
            return False

        if not interaction.guild:
            return True

        if (interaction.command and
            interaction.command.name == "set_mute_channel"):
            return True

        is_prohibited = await self.db.is_channel_prohibited(
            interaction.guild_id,
            interaction.channel_id
        )
        if is_prohibited:
            await interaction.response.send_message(
                ERROR_MESSAGES["prohibited_channel"],
                ephemeral=True
            )
            return False
        return True

def main() -> None:
    """メイン処理"""
    # 環境変数の読み込み
    dotenv.load_dotenv()
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise ValueError("DISCORD_TOKEN not found in .env file")

    # ボットの起動
    bot = SwiftlyBot()
    bot.tree.interaction_check = bot.check_slash_command
    bot.check(bot.check_command_permissions)

    try:
        asyncio.run(bot.start(token))
    except KeyboardInterrupt:
        logger.info("Bot shutdown requested")
    except Exception as e:
        logger.error("Bot crashed: %s", e, exc_info=True)
    finally:
        asyncio.run(bot.db.cleanup())

if __name__ == "__main__":
    main()
