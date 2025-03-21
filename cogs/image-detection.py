import discord
from discord.ext import commands
import torch
from PIL import Image
from transformers import AutoModelForImageClassification, ViTImageProcessor
import io
import sqlite3

class NSFWdetectionImageCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.model = AutoModelForImageClassification.from_pretrained("Falconsai/nsfw_image_detection")
        self.processor = ViTImageProcessor.from_pretrained('Falconsai/nsfw_image_detection')
        self.conn = sqlite3.connect('data/settings.db')

    def is_nsfw(self, image_bytes):
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        with torch.no_grad():
            inputs = self.processor(images=img, return_tensors="pt")
            outputs = self.model(**inputs)
            logits = outputs.logits
        predicted_label = logits.argmax(-1).item()
        return self.model.config.id2label[predicted_label] == 'nsfw'

    def get_nsfw_detection_status(self, guild_id):
        cursor = self.conn.execute('SELECT nsfw_detection_enabled FROM settings WHERE guild_id = ?', (guild_id,))
        row = cursor.fetchone()
        return row[0] if row else False

    def set_nsfw_detection_status(self, guild_id, status):
        cursor = self.conn.execute('SELECT nsfw_detection_enabled FROM settings WHERE guild_id = ?', (guild_id,))
        if cursor.fetchone():
            self.conn.execute('UPDATE settings SET nsfw_detection_enabled = ? WHERE guild_id = ?', (status, guild_id))
        else:
            self.conn.execute('INSERT INTO settings (guild_id, nsfw_detection_enabled) VALUES (?, ?)', (guild_id, status))
        self.conn.commit()

    @commands.Cog.listener()
    async def on_message(self, message):
        if not self.get_nsfw_detection_status(message.guild.id):
            return

        if message.attachments:
            for attachment in message.attachments:
                if attachment.filename.lower().endswith(('png', 'jpg', 'jpeg', 'gif', 'bmp')):
                    image_bytes = await attachment.read()
                    if self.is_nsfw(image_bytes):
                        await message.add_reaction('🚫')
                        alert = await message.channel.send(f"{message.author.mention} NSFW画像が検出されました。\nこのメッセージは5秒後に削除されます。")
                        await discord.utils.sleep_until(discord.utils.utcnow() + discord.utils.timedelta(seconds=5))
                        await alert.delete()

    @commands.command(name='sentry')
    async def sentry(self, ctx, action: str, function: str):
        if function != 'imagedetect':
            await ctx.send("無効な機能です。")
            return

        if action == 'enable':
            self.set_nsfw_detection_status(ctx.guild.id, True)
            await ctx.send("NSFW画像検知が有効になりました。")
        elif action == 'disable':
            self.set_nsfw_detection_status(ctx.guild.id, False)
            await ctx.send("NSFW画像検知が無効になりました。")
        else:
            await ctx.send("無効なアクションです。")

async def setup(bot):
    await bot.add_cog(NSFWdetectionImageCog(bot))
