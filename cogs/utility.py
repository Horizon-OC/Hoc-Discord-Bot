import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
from datetime import datetime
import psutil
import os

from utils.checks import is_moderator, moderator_check
from utils.embeds import EmbedFactory
from config import Config

class Utility(commands.Cog):
    """Utility commands for server management"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.hybrid_command(name="ping", description="Check bot latency")
    async def ping(self, ctx: commands.Context):
        """Check the bot's latency"""
        latency = round(self.bot.latency * 1000)
        
        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"Latency: **{latency}ms**",
            color=Config.EMBED_COLOR
        )
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="userinfo", description="Get information about a user")
    @app_commands.describe(member="The member to get information about")
    async def userinfo(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        """Get information about a user"""
        member = member or ctx.author
        embed = EmbedFactory.user_info(member)
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="serverinfo", description="Get information about the server")
    async def serverinfo(self, ctx: commands.Context):
        """Get information about the server"""
        embed = EmbedFactory.server_info(ctx.guild)
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="avatar", description="Get a user's avatar")
    @app_commands.describe(member="The member to get the avatar of")
    async def avatar(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        """Get a user's avatar"""
        member = member or ctx.author
        
        embed = discord.Embed(
            title=f"{member.display_name}'s Avatar",
            color=member.color if member.color != discord.Color.default() else Config.EMBED_COLOR
        )
        embed.set_image(url=member.display_avatar.url)
        embed.add_field(name="Link", value=f"[Click here]({member.display_avatar.url})")
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="pin", description="Pin the previous message")
    @is_moderator()
    @moderator_check()
    async def pin(self, ctx: commands.Context):
        """Pin the previous message"""
        try:
            messages = [msg async for msg in ctx.channel.history(limit=2)]
            
            if len(messages) < 2:
                await ctx.send("❌ No message to pin.", ephemeral=True)
                return
            
            message_to_pin = messages[1]
            await message_to_pin.pin()
            
            await ctx.send(f"✅ Pinned message by {message_to_pin.author.mention}", ephemeral=True)
            
            try:
                await ctx.message.delete()
            except:
                pass
                
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to pin messages.", ephemeral=True)
        except discord.HTTPException as e:
            await ctx.send(f"❌ Failed to pin message: {e}", ephemeral=True)
    
    @commands.hybrid_command(name="unpin", description="Unpin the most recent pinned message")
    @is_moderator()
    @moderator_check()
    async def unpin(self, ctx: commands.Context):
        """Unpin the most recent pinned message"""
        try:
            pinned_messages = await ctx.channel.pins()
            
            if not pinned_messages:
                await ctx.send("❌ No pinned messages to unpin.", ephemeral=True)
                return
            
            message_to_unpin = pinned_messages[0]
            await message_to_unpin.unpin()
            
            await ctx.send("✅ Unpinned the most recent message.", ephemeral=True)
            
            try:
                await ctx.message.delete()
            except:
                pass
                
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to unpin messages.", ephemeral=True)
        except discord.HTTPException as e:
            await ctx.send(f"❌ Failed to unpin message: {e}", ephemeral=True)
    
    @commands.hybrid_command(name="botstats", description="Show bot resource usage and statistics")
    @is_moderator()
    @moderator_check()
    async def botstats(self, ctx: commands.Context):
        """Show bot statistics and resource usage"""
        # Get process info
        process = psutil.Process(os.getpid())
        
        # Memory usage
        memory_info = process.memory_info()
        memory_mb = memory_info.rss / 1024 / 1024
        
        # CPU usage
        cpu_percent = process.cpu_percent(interval=1)
        
        # System info
        total_memory = psutil.virtual_memory().total / 1024 / 1024 / 1024  # GB
        available_memory = psutil.virtual_memory().available / 1024 / 1024 / 1024  # GB
        
        # Bot uptime
        import time
        uptime_seconds = int(time.time() - process.create_time())
        days, remainder = divmod(uptime_seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        embed = discord.Embed(
            title="📊 Bot Statistics",
            color=Config.EMBED_COLOR,
            timestamp=datetime.utcnow()
        )
        
        # Bot info
        embed.add_field(
            name="Bot Info",
            value=f"**Guilds:** {len(self.bot.guilds)}\n**Users:** {len(self.bot.users)}\n**Commands:** {len(self.bot.commands)}",
            inline=True
        )
        
        # Resource usage
        embed.add_field(
            name="Resource Usage",
            value=f"**Memory:** {memory_mb:.2f} MB\n**CPU:** {cpu_percent:.1f}%",
            inline=True
        )
        
        # System info
        embed.add_field(
            name="System",
            value=f"**Total RAM:** {total_memory:.1f} GB\n**Available:** {available_memory:.1f} GB",
            inline=True
        )
        
        # Uptime
        uptime_str = f"{days}d {hours}h {minutes}m {seconds}s"
        embed.add_field(
            name="Uptime",
            value=uptime_str,
            inline=False
        )
        
        # Latency
        latency = round(self.bot.latency * 1000)
        embed.add_field(
            name="Latency",
            value=f"{latency}ms",
            inline=True
        )
        
        # Discord.py version
        embed.set_footer(text=f"discord.py {discord.__version__}")
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="help", description="Show all available commands")
    async def help_command(self, ctx: commands.Context):
        """Show help information"""
        embed = discord.Embed(
            title="📚 Bot Commands",
            description="Here are all available commands. Use `/command` or `?command`",
            color=Config.EMBED_COLOR,
            timestamp=datetime.utcnow()
        )
        
        # Moderation commands
        mod_commands = [
            "**setmod** - Set the moderator role",
            "**setlog** - Set the log channel",
            "**ban** - Ban a user",
            "**kick** - Kick a user",
            "**timeout** - Timeout a user (e.g., 10m, 2h, 1d)",
            "**untimeout** - Remove timeout",
            "**warn** - Warn a user",
            "**warnings** - View user warnings",
            "**clearwarnings** - Clear all warnings",
            "**removewarning** - Remove specific warning",
            "**history** - View mod history",
            "**delete** - Delete messages",
            "**slowmode** - Set slowmode",
            "**lock/unlock** - Lock/unlock channel",
            "**pin/unpin** - Pin/unpin messages",
            "**botstats** - View bot resource usage"
        ]
        
        # Utility commands
        util_commands = [
            "**ping** - Check bot latency",
            "**userinfo** - View user info",
            "**serverinfo** - View server info",
            "**avatar** - View user avatar",
            "**help** - Show this message"
        ]
        
        # Error code commands
        err_commands = [
            "**err** - Look up any Nintendo error code (auto-detects console)",
            "**err2hex** - Convert error to hex",
            "**hex2err** - Convert hex to error"
        ]
        
        embed.add_field(name="🛡️ Moderation", value="\n".join(mod_commands), inline=False)
        embed.add_field(name="🔧 Utility", value="\n".join(util_commands), inline=False)
        embed.add_field(name="🎮 Error Codes", value="\n".join(err_commands), inline=False)
        
        embed.set_footer(text=f"Prefix: {Config.PREFIX} | Total Commands: {len(self.bot.commands)}")
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Utility(bot))