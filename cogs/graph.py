import discord
from discord.ext import commands, tasks
import datetime
import os

import matplotlib.pyplot as plt

class LatencyGraph(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.latencies = []
        self.timestamps = []
        self.update_graph.start()

    @tasks.loop(hours=1)
    async def update_graph(self):
        latency = self.bot.latency * 1000  # Convert to milliseconds
        self.latencies.append(latency)
        self.timestamps.append(datetime.datetime.now())

        # Keep only the last 7 days of data
        one_week_ago = datetime.datetime.now() - datetime.timedelta(days=7)
        self.latencies = [lat for lat, ts in zip(self.latencies, self.timestamps) if ts > one_week_ago]
        self.timestamps = [ts for ts in self.timestamps if ts > one_week_ago]

        # Plot the graph
        plt.figure(figsize=(10, 5))
        plt.plot(self.timestamps, self.latencies, marker='o')
        plt.title('Discord Latency Over the Last Week')
        plt.xlabel('Time')
        plt.ylabel('Latency (ms)')
        plt.grid(True)
        plt.xticks(rotation=45)
        plt.tight_layout()

        # Save the graph
        if not os.path.exists('public'):
            os.makedirs('public')
        plt.savefig('public/graph.png')
        plt.close()

async def setup(bot):
    await bot.add_cog(LatencyGraph(bot))