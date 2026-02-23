import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
from datetime import datetime

from utils.logger import bot_logger, mod_logger
from config import Config

STAR_EMOJI = "⭐"
CLOWN_EMOJI = "🤡"
DEFAULT_THRESHOLD = 3


class Starboard(commands.Cog):
    """Starboard and Clownboard — automatically pin great or cursed messages."""

    def __init__(self, bot):
        self.bot = bot
        # In-memory dedup cache: { guild_id: { "star": {src_msg_id: board_msg_id}, "clown": {...} } }
        self._posted: dict[int, dict[str, dict[int, int]]] = {}

    # ──────────────────────────────────────────────────────────────────
    # Helper: guild sub-cache
    # ──────────────────────────────────────────────────────────────────

    def _cache(self, guild_id: int, board: str) -> dict[int, int]:
        return self._posted.setdefault(guild_id, {}).setdefault(board, {})

    # ──────────────────────────────────────────────────────────────────
    # Helper: fetch board config from DB (via bot.db)
    # ──────────────────────────────────────────────────────────────────

    async def _get_config(self, guild_id: int, board: str):
        """Return (channel_id, threshold) or (None, None)."""
        config = await self.bot.db.get_guild_config(guild_id)
        if not config:
            return None, None
        if board == "star":
            return (
                config.get("starboard_channel_id"),
                config.get("starboard_threshold") or DEFAULT_THRESHOLD,
            )
        return (
            config.get("clownboard_channel_id"),
            config.get("clownboard_threshold") or DEFAULT_THRESHOLD,
        )

    # ──────────────────────────────────────────────────────────────────
    # Helper: count a specific reaction on a message
    # ──────────────────────────────────────────────────────────────────

    @staticmethod
    def _count(message: discord.Message, emoji: str) -> int:
        for r in message.reactions:
            if str(r.emoji) == emoji:
                return r.count
        return 0

    # ──────────────────────────────────────────────────────────────────
    # Embed builder
    # ──────────────────────────────────────────────────────────────────

    def _build_embed(
        self, message: discord.Message, count: int, board: str
    ) -> tuple[str, discord.Embed]:
        """Return (header_content, embed) for a board post."""
        is_star = board == "star"
        emoji = STAR_EMOJI if is_star else CLOWN_EMOJI
        color = discord.Color.gold() if is_star else discord.Color.orange()
        board_name = "Starboard" if is_star else "Clownboard"

        # Content line above the embed (stays visible even on mobile)
        header = f"{emoji} **{count}** | {message.channel.mention}"

        embed = discord.Embed(
            description=message.content or "*— no text —*",
            color=color,
            timestamp=message.created_at,
        )
        embed.set_author(
            name=message.author.display_name,
            icon_url=message.author.display_avatar.url,
        )

        # Attach image if present
        if message.attachments:
            att = message.attachments[0]
            if att.content_type and att.content_type.startswith("image/"):
                embed.set_image(url=att.url)
            else:
                embed.add_field(
                    name="📎 Attachment",
                    value=f"[{att.filename}]({att.url})",
                    inline=False,
                )
        elif message.embeds:
            orig = message.embeds[0]
            if orig.image:
                embed.set_image(url=orig.image.url)
            elif orig.thumbnail:
                embed.set_image(url=orig.thumbnail.url)

        embed.add_field(
            name="Original",
            value=f"[Jump to message]({message.jump_url})",
            inline=False,
        )
        embed.set_footer(text=f"{board_name} • #{message.channel.name} • ID: {message.id}")

        return header, embed

    # ──────────────────────────────────────────────────────────────────
    # Post / edit board messages
    # ──────────────────────────────────────────────────────────────────

    async def _post(
        self,
        board_channel: discord.TextChannel,
        message: discord.Message,
        count: int,
        board: str,
    ) -> Optional[discord.Message]:
        header, embed = self._build_embed(message, count, board)
        try:
            return await board_channel.send(content=header, embed=embed)
        except discord.Forbidden:
            bot_logger.warning(
                f"Missing permissions to post to {board} board in {board_channel.guild.name}"
            )
            return None

    async def _update_count(
        self,
        board_channel: discord.TextChannel,
        board_msg_id: int,
        count: int,
        board: str,
    ):
        emoji = STAR_EMOJI if board == "star" else CLOWN_EMOJI
        try:
            board_msg = await board_channel.fetch_message(board_msg_id)
            parts = board_msg.content.split(" | ", 1)
            if len(parts) == 2:
                await board_msg.edit(content=f"{emoji} **{count}** | {parts[1]}")
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass

    # ──────────────────────────────────────────────────────────────────
    # Core reaction handler
    # ──────────────────────────────────────────────────────────────────

    async def _handle(self, payload: discord.RawReactionActionEvent, board: str):
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        board_channel_id, threshold = await self._get_config(guild.id, board)
        if not board_channel_id:
            return

        src_channel = guild.get_channel(payload.channel_id)
        if not isinstance(src_channel, discord.TextChannel):
            return

        # Prevent board channels from feeding themselves
        if src_channel.id == board_channel_id:
            return

        try:
            message = await src_channel.fetch_message(payload.message_id)
        except (discord.NotFound, discord.Forbidden):
            return

        # Skip bot messages
        if message.author.bot:
            return

        emoji = STAR_EMOJI if board == "star" else CLOWN_EMOJI
        count = self._count(message, emoji)

        board_channel = guild.get_channel(board_channel_id)
        if not isinstance(board_channel, discord.TextChannel):
            return

        cache = self._cache(guild.id, board)

        if message.id in cache:
            # Already posted — just update the count
            await self._update_count(board_channel, cache[message.id], count, board)
        elif count >= threshold:
            # First time hitting threshold — post it
            posted = await self._post(board_channel, message, count, board)
            if posted:
                cache[message.id] = posted.id
                bot_logger.info(
                    f"[{board}] Posted message {message.id} from "
                    f"#{src_channel.name} in {guild.name} ({count} reactions)"
                )

    # ──────────────────────────────────────────────────────────────────
    # Listeners
    # ──────────────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if not payload.guild_id:
            return
        emoji = str(payload.emoji)
        if emoji == STAR_EMOJI:
            await self._handle(payload, "star")
        elif emoji == CLOWN_EMOJI:
            await self._handle(payload, "clown")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        """Update count when a reaction is removed."""
        if not payload.guild_id:
            return
        emoji = str(payload.emoji)
        if emoji not in (STAR_EMOJI, CLOWN_EMOJI):
            return
        board = "star" if emoji == STAR_EMOJI else "clown"

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        board_channel_id, _ = await self._get_config(guild.id, board)
        if not board_channel_id:
            return

        cache = self._cache(guild.id, board)
        if payload.message_id not in cache:
            return

        src_channel = guild.get_channel(payload.channel_id)
        if not src_channel:
            return

        try:
            message = await src_channel.fetch_message(payload.message_id)
        except (discord.NotFound, discord.Forbidden):
            return

        reaction_emoji = STAR_EMOJI if board == "star" else CLOWN_EMOJI
        count = self._count(message, reaction_emoji)

        board_channel = guild.get_channel(board_channel_id)
        if board_channel:
            await self._update_count(board_channel, cache[payload.message_id], count, board)

    # ──────────────────────────────────────────────────────────────────
    # Commands — /starboard
    # ──────────────────────────────────────────────────────────────────

    @commands.hybrid_group(
        name="starboard",
        description="Starboard configuration",
        invoke_without_command=True,
    )
    @commands.has_permissions(administrator=True)
    async def starboard_group(self, ctx: commands.Context):
        """Starboard commands"""
        await ctx.send_help(ctx.command)

    @starboard_group.command(
        name="setchannel",
        description="Set the channel where starred messages appear",
    )
    @commands.has_permissions(administrator=True)
    @app_commands.describe(
        channel="The channel to post starred messages in",
        threshold=f"Number of ⭐ reactions required (default {DEFAULT_THRESHOLD})",
    )
    async def star_set(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel,
        threshold: Optional[int] = DEFAULT_THRESHOLD,
    ):
        threshold = max(1, threshold)
        await self.bot.db.set_starboard_channel(ctx.guild.id, channel.id, threshold)
        await self.bot.cache.invalidate_guild_config(ctx.guild.id)

        embed = discord.Embed(
            title="⭐ Starboard Configured",
            description=(
                f"**Channel:** {channel.mention}\n"
                f"**Threshold:** {threshold} {STAR_EMOJI} reaction(s) required"
            ),
            color=discord.Color.gold(),
            timestamp=datetime.utcnow(),
        )
        embed.set_footer(
            text=f"Set by {ctx.author}", icon_url=ctx.author.display_avatar.url
        )
        await ctx.send(embed=embed)
        mod_logger.info(
            f"Starboard set to #{channel.name} (threshold {threshold}) "
            f"in {ctx.guild.name} by {ctx.author}"
        )

    @starboard_group.command(name="disable", description="Disable the starboard")
    @commands.has_permissions(administrator=True)
    async def star_disable(self, ctx: commands.Context):
        await self.bot.db.set_starboard_channel(ctx.guild.id, None, DEFAULT_THRESHOLD)
        await self.bot.cache.invalidate_guild_config(ctx.guild.id)

        embed = discord.Embed(
            title="⭐ Starboard Disabled",
            description="The starboard has been turned off.",
            color=discord.Color.red(),
            timestamp=datetime.utcnow(),
        )
        await ctx.send(embed=embed)
        mod_logger.info(f"Starboard disabled in {ctx.guild.name} by {ctx.author}")

    @starboard_group.command(
        name="info", description="Show current starboard configuration"
    )
    @commands.has_permissions(administrator=True)
    async def star_info(self, ctx: commands.Context):
        channel_id, threshold = await self._get_config(ctx.guild.id, "star")
        if not channel_id:
            embed = discord.Embed(
                title="⭐ Starboard",
                description="Starboard is **disabled**. Use `/starboard setchannel` to enable it.",
                color=discord.Color.greyple(),
            )
        else:
            channel = ctx.guild.get_channel(channel_id)
            embed = discord.Embed(
                title="⭐ Starboard",
                color=discord.Color.gold(),
                timestamp=datetime.utcnow(),
            )
            embed.add_field(name="Channel", value=channel.mention if channel else f"<#{channel_id}> *(deleted?)*", inline=True)
            embed.add_field(name="Threshold", value=f"{threshold} {STAR_EMOJI}", inline=True)
        await ctx.send(embed=embed)

    # ──────────────────────────────────────────────────────────────────
    # Commands — /clownboard
    # ──────────────────────────────────────────────────────────────────

    @commands.hybrid_group(
        name="clownboard",
        description="Clownboard configuration",
        invoke_without_command=True,
    )
    @commands.has_permissions(administrator=True)
    async def clownboard_group(self, ctx: commands.Context):
        """Clownboard commands"""
        await ctx.send_help(ctx.command)

    @clownboard_group.command(
        name="setchannel",
        description="Set the channel where clowned messages appear",
    )
    @commands.has_permissions(administrator=True)
    @app_commands.describe(
        channel="The channel to post clowned messages in",
        threshold=f"Number of 🤡 reactions required (default {DEFAULT_THRESHOLD})",
    )
    async def clown_set(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel,
        threshold: Optional[int] = DEFAULT_THRESHOLD,
    ):
        threshold = max(1, threshold)
        await self.bot.db.set_clownboard_channel(ctx.guild.id, channel.id, threshold)
        await self.bot.cache.invalidate_guild_config(ctx.guild.id)

        embed = discord.Embed(
            title="🤡 Clownboard Configured",
            description=(
                f"**Channel:** {channel.mention}\n"
                f"**Threshold:** {threshold} {CLOWN_EMOJI} reaction(s) required"
            ),
            color=discord.Color.orange(),
            timestamp=datetime.utcnow(),
        )
        embed.set_footer(
            text=f"Set by {ctx.author}", icon_url=ctx.author.display_avatar.url
        )
        await ctx.send(embed=embed)
        mod_logger.info(
            f"Clownboard set to #{channel.name} (threshold {threshold}) "
            f"in {ctx.guild.name} by {ctx.author}"
        )

    @clownboard_group.command(name="disable", description="Disable the clownboard")
    @commands.has_permissions(administrator=True)
    async def clown_disable(self, ctx: commands.Context):
        await self.bot.db.set_clownboard_channel(ctx.guild.id, None, DEFAULT_THRESHOLD)
        await self.bot.cache.invalidate_guild_config(ctx.guild.id)

        embed = discord.Embed(
            title="🤡 Clownboard Disabled",
            description="The clownboard has been turned off.",
            color=discord.Color.red(),
            timestamp=datetime.utcnow(),
        )
        await ctx.send(embed=embed)
        mod_logger.info(f"Clownboard disabled in {ctx.guild.name} by {ctx.author}")

    @clownboard_group.command(
        name="info", description="Show current clownboard configuration"
    )
    @commands.has_permissions(administrator=True)
    async def clown_info(self, ctx: commands.Context):
        channel_id, threshold = await self._get_config(ctx.guild.id, "clown")
        if not channel_id:
            embed = discord.Embed(
                title="🤡 Clownboard",
                description="Clownboard is **disabled**. Use `/clownboard setchannel` to enable it.",
                color=discord.Color.greyple(),
            )
        else:
            channel = ctx.guild.get_channel(channel_id)
            embed = discord.Embed(
                title="🤡 Clownboard",
                color=discord.Color.orange(),
                timestamp=datetime.utcnow(),
            )
            embed.add_field(name="Channel", value=channel.mention if channel else f"<#{channel_id}> *(deleted?)*", inline=True)
            embed.add_field(name="Threshold", value=f"{threshold} {CLOWN_EMOJI}", inline=True)
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Starboard(bot))
