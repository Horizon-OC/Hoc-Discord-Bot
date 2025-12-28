import discord
from discord.ext import commands
import asyncio
import sys
import webserver
from pathlib import Path
import random

from config import Config
from utils.database import Database
from utils.cache import Cache
from utils.logger import bot_logger
from utils.checks import HierarchyError

class ModBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.reactions = True
        intents.members = True
        intents.guilds = True
        
        super().__init__(
            command_prefix=self.get_prefix,
            intents=intents,
            help_command=None,
            case_insensitive=True
        )
        
        self.db = Database()
        self.cache = Cache()
        self.initial_extensions = [
            'cogs.moderation',
            'cogs.errors',
            'cogs.utility',
            'cogs.game',
            'cogs.events'
        ]
    
    async def get_prefix(self, message: discord.Message):
        """Dynamic prefix based on guild config"""
        if not message.guild:
            return commands.when_mentioned_or(Config.PREFIX)(self, message)
        
        # Try to get from cache first
        config = await self.cache.get_guild_config(message.guild.id)
        if not config:
            config = await self.db.get_guild_config(message.guild.id)
            if config:
                await self.cache.set_guild_config(message.guild.id, config)
        
        prefix = config.get('prefix', Config.PREFIX) if config else Config.PREFIX
        return commands.when_mentioned_or(prefix)(self, message)
    
    async def setup_hook(self):
        """Initial setup when bot starts"""
        # Initialize database
        await self.db.connect()
        
        # Initialize cache
        await self.cache.connect()
        
        # Load extensions
        for extension in self.initial_extensions:
            try:
                await self.load_extension(extension)
                bot_logger.info(f"Loaded extension: {extension}")
            except Exception as e:
                bot_logger.error(f"Failed to load extension {extension}: {e}")
            
    async def on_ready(self):
        """Called when bot is ready"""
        bot_logger.info(f'{self.user.name} (ID: {self.user.id}) has connected to Discord!')
        bot_logger.info(f'Connected to {len(self.guilds)} guilds')
        
        # Sync slash commands after bot is ready
        try:
            bot_logger.info("Syncing slash commands...")
            synced = await self.tree.sync()
            bot_logger.info(f"Synced {len(synced)} slash commands")
        except Exception as e:
            bot_logger.error(f"Failed to sync commands: {e}")
        
        # Set status
        await self.change_presence(
            activity=discord.CustomActivity(
                 name="Overclocking switches | ?help"
            )
        )
    
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        """Global error handler"""
        # Ignore command not found
        if isinstance(error, commands.CommandNotFound):
            return
        
        # Hierarchy errors are already handled in the command
        if isinstance(error, commands.CheckFailure):
            if isinstance(error.__cause__, HierarchyError) or "hierarchy" in str(error).lower():
                return
        
        # Handle specific errors
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You don't have permission to use this command.")
        elif isinstance(error, commands.BotMissingPermissions):
            await ctx.send("❌ I don't have the necessary permissions to execute this command.")
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send("❌ Member not found.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ Missing required argument: `{error.param.name}`")
        elif isinstance(error, commands.BadArgument):
            await ctx.send(f"❌ Invalid argument provided.")
        elif hasattr(error, 'original'):
            # Don't show "unexpected error" for hierarchy errors
            if isinstance(error.original, HierarchyError):
                return
            bot_logger.error(f"Command error in {ctx.command}: {error.original}", exc_info=error.original)
            await ctx.send("❌ An error occurred while executing the command.")
        else:
            bot_logger.error(f"Command error: {error}", exc_info=error)
    
    async def close(self):
        """Cleanup when bot shuts down"""
        await self.cache.disconnect()
        bot_logger.info("Bot shutting down")
        await super().close()

async def start_bot_with_retry(bot, max_retries=5):
    """Start bot with exponential backoff retry logic for rate limits"""
    for attempt in range(max_retries):
        try:
            await bot.start(Config.TOKEN)
            break
        except discord.HTTPException as e:
            if e.status == 429:  # Rate limited
                if attempt < max_retries - 1:
                    # Exponential backoff with jitter
                    wait_time = (2 ** attempt) + random.uniform(0, 1)
                    bot_logger.warning(
                        f"Rate limited by Discord/Cloudflare (attempt {attempt + 1}/{max_retries}). "
                        f"Retrying in {wait_time:.1f} seconds..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    bot_logger.error(
                        "Failed to connect after multiple attempts due to rate limiting. "
                        "This is likely due to Render's shared IP being blocked by Cloudflare."
                    )
                    raise
            else:
                raise
        except Exception as e:
            bot_logger.error(f"Unexpected error during bot start: {e}", exc_info=e)
            raise

async def main():
    """Main entry point"""
    # Validate configuration
    try:
        Config.validate()
    except ValueError as e:
        bot_logger.error(f"Configuration error: {e}")
        sys.exit(1)

    # Start Flask keep-alive
    webserver.keep_alive()    

    # Create and run bot
    bot = ModBot()
    
    # Make bot accessible globally for checks
    globals()['bot'] = bot
    
    try:
        await start_bot_with_retry(bot)
    except KeyboardInterrupt:
        bot_logger.info("Received keyboard interrupt")
    except Exception as e:
        bot_logger.error(f"Fatal error: {e}", exc_info=e)
    finally:
        await bot.close()

if __name__ == "__main__":
    asyncio.run(main())
