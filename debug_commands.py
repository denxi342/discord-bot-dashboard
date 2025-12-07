
import discord
from discord.ext import commands
import main
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

async def test():
    print("Testing bot commands...")
    # Inspect the bot object from main
    # We need to initialize it the same way
    intents = discord.Intents.default()
    intents.message_content = True
    bot = main.bot
    
    print(f"Commands registered: {[c.name for c in bot.commands]}")
    
    monitor_cmd = bot.get_command('monitor')
    if monitor_cmd:
        print(f"Monitor command found. Type: {type(monitor_cmd)}")
        if isinstance(monitor_cmd, commands.Group):
            print(f"Subcommands: {[c.name for c in monitor_cmd.commands]}")
    else:
        print("Monitor command NOT found!")

if __name__ == "__main__":
    asyncio.run(test())
