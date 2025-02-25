import discord
from discord.ext import commands
import logging

# Set up logging
logging.basicConfig(filename='logging.log', level=logging.INFO, format='%(asctime)s:%(levelname)s:%(message)s')

class LoggingCog(commands.Cog):
    """Botの動作をログ出力するCog"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        logging.info(f"Bot is ready. Logged in as {self.bot.user}")

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        logging.info(f"Joined guild: {guild.name} (ID: {guild.id})")

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        logging.info(f"Removed from guild: {guild.name} (ID: {guild.id})")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        logging.info(f"Member joined: {member.name} (ID: {member.id}) in guild: {member.guild.name}")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        logging.info(f"Member left: {member.name} (ID: {member.id}) from guild: {member.guild.name}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author == self.bot.user:
            return
        logging.info(f"Message from {message.author.name} (ID: {message.author.id}) in guild: {message.guild.name} - {message.content}")

    @commands.Cog.listener()
    async def on_command_completion(self, ctx: commands.Context) -> None:
        logging.info(f"Command executed: {ctx.command} by {ctx.author.name} (ID: {ctx.author.id}) in guild: {ctx.guild.name}")

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        logging.error(f"Command error: {ctx.command} by {ctx.author.name} (ID: {ctx.author.id}) in guild: {ctx.guild.name} - {error}")

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(LoggingCog(bot))