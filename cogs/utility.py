import asyncio
import re
import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
from datetime import datetime, timedelta, timezone
import psutil
import os
import socket
import struct
import time

from utils.checks import is_moderator, moderator_check
from utils.embeds import EmbedFactory
from config import Config

NTP_CACHE_TTL = 30  # seconds

class Utility(commands.Cog):
    """Utility commands for server management"""
    
    def __init__(self, bot):
        self.bot = bot
        self._ntp_cache: Optional[datetime] = None
        self._ntp_cache_time: float = 0.0

    def _fetch_ntp_blocking(self) -> Optional[datetime]:
        """Blocking NTP fetch — run this in a thread, not the event loop."""
        ntp_packet = b'\x1b' + 47 * b'\x00'
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.settimeout(3)
                sock.sendto(ntp_packet, ("pool.ntp.org", 123))
                data, _ = sock.recvfrom(1024)
        except OSError:
            return None

        if len(data) < 48:
            return None

        ntp_seconds, _ = struct.unpack('!II', data[40:48])
        unix_seconds = ntp_seconds - 2208988800
        return datetime.fromtimestamp(unix_seconds, tz=timezone.utc)

    async def _get_ntp_time(self) -> Optional[datetime]:
        """Return the current UTC time from NTP, using a 30-second cache."""
        now = time.monotonic()
        if self._ntp_cache is not None and now - self._ntp_cache_time < NTP_CACHE_TTL:
            return self._ntp_cache

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self._fetch_ntp_blocking)
        if result is not None:
            self._ntp_cache = result
            self._ntp_cache_time = now
        return result

    @staticmethod
    def _parse_tz_offset(arg: str):
        """
        Parse a loose timezone/offset string and return a timezone object.

        Accepted formats (case-insensitive):
          utc±H, utc±H:MM, gmt±H, gmt±H:MM
          ±H, ±H:MM, ±HH, ±HH:MM
          Plain digits are treated as a positive offset (e.g. "4" → UTC+4).

        Returns a datetime.timezone on success, or None if unparseable.
        """
        s = arg.strip().upper()

        # Strip optional UTC/GMT prefix
        s = re.sub(r'^(UTC|GMT)', '', s)

        # "0" and "-0" → UTC
        if s in ('', '0', '-0', '+0', '00', '-00', '+00'):
            return timezone.utc

        # Match optional sign, hours, optional :minutes
        m = re.fullmatch(r'([+-]?)(\d{1,2})(?::(\d{2}))?', s)
        if not m:
            return None

        sign_str, hours_str, minutes_str = m.groups()
        hours = int(hours_str)
        minutes = int(minutes_str) if minutes_str else 0

        if hours > 14 or minutes >= 60:
            return None

        sign = -1 if sign_str == '-' else 1
        offset = timedelta(hours=sign * hours, minutes=sign * minutes)
        return timezone(offset)

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
    
    @commands.hybrid_command(name="time", description="Get the current time from the NTP pool")
    @app_commands.describe(timezone_arg="Optional timezone offset, e.g. UTC-4, GMT+5:30, -4, 4")
    async def current_time(self, ctx: commands.Context, *, timezone_arg: Optional[str] = None):
        """Fetch the current UTC time from the NTP pool (cached for 30 s).

        Optionally accepts a timezone offset to convert the result:
          ?time          → displays UTC
          ?time utc-4   → displays UTC-4
          ?time gmt+5:30 → displays UTC+5:30
          ?time -4       → displays UTC-4
          ?time 4        → displays UTC+4
        """
        ntp_time = await self._get_ntp_time()

        if ntp_time is None:
            embed = EmbedFactory.error(
                title="Time Lookup Failed",
                description="Could not reach the NTP pool right now. Please try again in a moment."
            )
            await ctx.send(embed=embed)
            return

        # Adjust the cached timestamp to account for time elapsed since it was fetched
        elapsed = time.monotonic() - self._ntp_cache_time
        utc_now = ntp_time.fromtimestamp(ntp_time.timestamp() + elapsed, tz=timezone.utc)

        # --- Timezone conversion ---
        tz = timezone.utc
        tz_label = "UTC"
        if timezone_arg is not None:
            parsed = self._parse_tz_offset(timezone_arg)
            if parsed is None:
                embed = EmbedFactory.error(
                    title="Invalid Timezone",
                    description=(
                        f"Could not parse `{timezone_arg}` as a timezone offset.\n"
                        "Try formats like: `UTC-4`, `GMT+5:30`, `-4`, `4`."
                    )
                )
                await ctx.send(embed=embed)
                return
            tz = parsed
            offset = tz.utcoffset(None)
            total_minutes = int(offset.total_seconds() // 60)
            hours, mins = divmod(abs(total_minutes), 60)
            sign = '+' if total_minutes >= 0 else '-'
            tz_label = f"UTC{sign}{hours}" + (f":{mins:02d}" if mins else "")

        now = utc_now.astimezone(tz)
        unix_timestamp = int(now.timestamp())
        discord_timestamp = f"<t:{unix_timestamp}:f>"
        display_time = now.strftime("%H:%M:%S")
        display_date = now.strftime("%m-%d-%Y")

        cached = elapsed > 0.5
        footer = f"Source: pool.ntp.org{' · Cached result' if cached else ''}"

        embed = discord.Embed(
            title="🕒 Current Time",
            description="Time fetched from the NTP pool.",
            color=Config.EMBED_COLOR,
            timestamp=utc_now
        )
        embed.add_field(name="Unix Timestamp", value=str(unix_timestamp), inline=True)
        embed.add_field(name="Discord Time", value=discord_timestamp, inline=True)
        embed.add_field(name=f"Time ({tz_label})", value=f"{display_time}\n{display_date}", inline=False)
        embed.set_footer(text=footer)

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
        process = psutil.Process(os.getpid())
        
        memory_info = process.memory_info()
        memory_mb = memory_info.rss / 1024 / 1024
        cpu_percent = process.cpu_percent(interval=1)
        total_memory = psutil.virtual_memory().total / 1024 / 1024 / 1024
        available_memory = psutil.virtual_memory().available / 1024 / 1024 / 1024
        
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
        
        embed.add_field(
            name="Bot Info",
            value=f"**Guilds:** {len(self.bot.guilds)}\n**Users:** {len(self.bot.users)}\n**Commands:** {len(self.bot.commands)}",
            inline=True
        )
        embed.add_field(
            name="Resource Usage",
            value=f"**Memory:** {memory_mb:.2f} MB\n**CPU:** {cpu_percent:.1f}%",
            inline=True
        )
        embed.add_field(
            name="System",
            value=f"**Total RAM:** {total_memory:.1f} GB\n**Available:** {available_memory:.1f} GB",
            inline=True
        )
        embed.add_field(name="Uptime", value=f"{days}d {hours}h {minutes}m {seconds}s", inline=False)
        embed.add_field(name="Latency", value=f"{round(self.bot.latency * 1000)}ms", inline=True)
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
            "**botstats** - View bot resource usage",
        ]
        
        # Utility commands
        util_commands = [
            "**ping** - Check bot latency",
            "**userinfo** - View user info",
            "**serverinfo** - View server info",
            "**avatar** - View user avatar",
            "**help** - Show this message",
        ]
        
        # Error code commands
        err_commands = [
            "**err** - Look up any Nintendo error code (auto-detects console)",
            "**err2hex** - Convert error to hex",
            "**hex2err** - Convert hex to error",
        ]

        # Starboard / Clownboard commands
        board_commands = [
            "**starboard setchannel** `#channel [threshold]` - Set ⭐ board channel",
            "**starboard disable** - Disable starboard",
            "**starboard info** - Show starboard config",
            "**clownboard setchannel** `#channel [threshold]` - Set 🤡 board channel",
            "**clownboard disable** - Disable clownboard",
            "**clownboard info** - Show clownboard config",
        ]
        
        embed.add_field(name="🛡️ Moderation", value="\n".join(mod_commands), inline=False)
        embed.add_field(name="⭐ Starboard & Clownboard", value="\n".join(board_commands), inline=False)
        embed.add_field(name="🔧 Utility", value="\n".join(util_commands), inline=False)
        embed.add_field(name="🎮 Error Codes", value="\n".join(err_commands), inline=False)
        
        embed.set_footer(text=f"Prefix: {Config.PREFIX} | Total Commands: {len(self.bot.commands)}")
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Utility(bot))
