import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional, Union
from datetime import datetime, timedelta
import re

from utils.checks import is_moderator, moderator_check, check_hierarchy, HierarchyError
from utils.embeds import EmbedFactory
from utils.logger import mod_logger

class Moderation(commands.Cog):
    """Moderation commands for server management"""
    
    def __init__(self, bot):
        self.bot = bot
    
    def parse_duration(self, duration_str: str) -> Optional[int]:
        """Parse duration string (e.g., '10m', '2h', '1d', '1w') to minutes"""
        match = re.match(r'^(\d+)([mhdw])$', duration_str.lower())
        if not match:
            return None
        
        amount, unit = match.groups()
        amount = int(amount)
        
        multipliers = {
            'm': 1,           # minutes
            'h': 60,          # hours
            'd': 1440,        # days
            'w': 10080        # weeks
        }
        
        return amount * multipliers[unit]
    
    @commands.hybrid_command(name="setmod", description="Set the moderator role for this server")
    @commands.has_permissions(administrator=True)
    @app_commands.describe(role="The role to set as moderator")
    async def setmod(self, ctx: commands.Context, *, role: str):
        """Set the moderator role"""
        # Try to parse the role from mention or name
        discord_role = None
        
        # Check if it's a mention
        if role.startswith('<@&') and role.endswith('>'):
            role_id = int(role[3:-1])
            discord_role = ctx.guild.get_role(role_id)
        else:
            # Try to find by name
            discord_role = discord.utils.get(ctx.guild.roles, name=role)
        
        if not discord_role:
            await ctx.send(f"❌ Could not find role: {role}")
            return
        
        await self.bot.db.set_mod_role(ctx.guild.id, discord_role.id)
        await self.bot.cache.invalidate_guild_config(ctx.guild.id)
        
        embed = EmbedFactory.success(
            "Moderator Role Set",
            f"Moderator role has been set to {discord_role.mention}"
        )
        await ctx.send(embed=embed)
        mod_logger.info(f"Mod role set to {discord_role.name} in {ctx.guild.name} by {ctx.author}")
    
    @commands.hybrid_command(name="setlog", description="Set the log channel for moderation actions")
    @commands.has_permissions(administrator=True)
    @app_commands.describe(channel="The channel to send logs to")
    async def setlog(self, ctx: commands.Context, channel: discord.TextChannel):
        """Set the log channel"""
        await self.bot.db.set_log_channel(ctx.guild.id, channel.id)
        await self.bot.cache.invalidate_guild_config(ctx.guild.id)
        
        embed = EmbedFactory.success(
            "Log Channel Set",
            f"Moderation logs will be sent to {channel.mention}"
        )
        await ctx.send(embed=embed)
        mod_logger.info(f"Log channel set to #{channel.name} in {ctx.guild.name} by {ctx.author}")
    
    @commands.hybrid_command(name="ban", description="Ban a user from the server")
    @is_moderator()
    @moderator_check()
    @app_commands.describe(
        member="The member to ban",
        reason="Reason for the ban",
        delete_days="Days of messages to delete (0-7)"
    )
    async def ban(
        self,
        ctx: commands.Context,
        member: discord.Member,
        delete_days: Optional[int] = 0,
        *,
        reason: Optional[str] = "No reason provided"
    ):
        """Ban a member from the server"""
        try:
            await check_hierarchy(ctx, member)
        except HierarchyError:
            return
        
        delete_days = max(0, min(delete_days, 7))
        
        try:
            # Try to DM user
            try:
                dm_embed = EmbedFactory.warning(
                    "You have been banned",
                    f"**Server:** {ctx.guild.name}\n**Reason:** {reason}"
                )
                await member.send(embed=dm_embed)
            except:
                pass
            
            # Ban the member
            await member.ban(reason=reason, delete_message_days=delete_days)
            
            # Log action
            await self.bot.db.log_action(
                ctx.guild.id,
                member.id,
                ctx.author.id,
                'ban',
                reason
            )
            
            # Send confirmation
            embed = EmbedFactory.moderation_action('ban', member, ctx.author, reason)
            if delete_days > 0:
                embed.add_field(name="Messages Deleted", value=f"{delete_days} day(s)", inline=False)
            await ctx.send(embed=embed)
            
            # Send to log channel
            await self._send_to_log(ctx.guild, embed)
            
            mod_logger.info(f"{ctx.author} banned {member} in {ctx.guild.name}: {reason}")
            
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to ban this user.")
        except Exception as e:
            await ctx.send(f"❌ An error occurred: {str(e)}")
    
    @commands.hybrid_command(name="kick", description="Kick a user from the server")
    @is_moderator()
    @moderator_check()
    @app_commands.describe(
        member="The member to kick",
        reason="Reason for the kick"
    )
    async def kick(
        self,
        ctx: commands.Context,
        member: discord.Member,
        *,
        reason: Optional[str] = "No reason provided"
    ):
        """Kick a member from the server"""
        try:
            await check_hierarchy(ctx, member)
        except HierarchyError:
            return
        
        try:
            # Try to DM user
            try:
                dm_embed = EmbedFactory.warning(
                    "You have been kicked",
                    f"**Server:** {ctx.guild.name}\n**Reason:** {reason}"
                )
                await member.send(embed=dm_embed)
            except:
                pass
            
            # Kick the member
            await member.kick(reason=reason)
            
            # Log action
            await self.bot.db.log_action(
                ctx.guild.id,
                member.id,
                ctx.author.id,
                'kick',
                reason
            )
            
            # Send confirmation
            embed = EmbedFactory.moderation_action('kick', member, ctx.author, reason)
            await ctx.send(embed=embed)
            
            # Send to log channel
            await self._send_to_log(ctx.guild, embed)
            
            mod_logger.info(f"{ctx.author} kicked {member} in {ctx.guild.name}: {reason}")
            
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to kick this user.")
        except Exception as e:
            await ctx.send(f"❌ An error occurred: {str(e)}")
    
    @commands.hybrid_command(name="timeout", description="Timeout a user")
    @is_moderator()
    @moderator_check()
    @app_commands.describe(
        member="The member to timeout",
        duration="Duration (e.g., 10m, 2h, 1d, 1w)",
        reason="Reason for the timeout"
    )
    async def timeout(
        self,
        ctx: commands.Context,
        member: discord.Member,
        duration: str,
        *,
        reason: Optional[str] = "No reason provided"
    ):
        """Timeout a member"""
        try:
            await check_hierarchy(ctx, member)
        except HierarchyError:
            return
        
        # Parse duration
        duration_minutes = self.parse_duration(duration)
        
        if duration_minutes is None:
            await ctx.send("❌ Invalid duration format. Use format like: `10m`, `2h`, `1d`, or `1w`")
            return
        
        if duration_minutes < 1 or duration_minutes > 40320:  # Max 28 days
            await ctx.send("❌ Duration must be between 1 minute and 28 days.")
            return
        
        try:
            until = discord.utils.utcnow() + timedelta(minutes=duration_minutes)
            await member.timeout(until, reason=reason)
            
            # Log action
            await self.bot.db.log_action(
                ctx.guild.id,
                member.id,
                ctx.author.id,
                'timeout',
                f"{reason} (Duration: {duration})"
            )
            
            # Format duration nicely for display
            duration_display = duration
            
            # Send confirmation
            embed = EmbedFactory.moderation_action('timeout', member, ctx.author, reason)
            embed.add_field(name="Duration", value=duration_display, inline=False)
            embed.add_field(name="Expires", value=f"<t:{int(until.timestamp())}:R>", inline=False)
            await ctx.send(embed=embed)
            
            # Send to log channel
            await self._send_to_log(ctx.guild, embed)
            
            mod_logger.info(f"{ctx.author} timed out {member} for {duration} in {ctx.guild.name}: {reason}")
            
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to timeout this user.")
        except Exception as e:
            await ctx.send(f"❌ An error occurred: {str(e)}")
    
    @commands.hybrid_command(name="untimeout", description="Remove timeout from a user")
    @is_moderator()
    @moderator_check()
    @app_commands.describe(member="The member to remove timeout from")
    async def untimeout(self, ctx: commands.Context, member: discord.Member):
        """Remove timeout from a member"""
        try:
            await member.timeout(None)
            
            embed = EmbedFactory.success(
                "Timeout Removed",
                f"{member.mention}'s timeout has been removed."
            )
            await ctx.send(embed=embed)
            
            mod_logger.info(f"{ctx.author} removed timeout from {member} in {ctx.guild.name}")
            
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to remove timeout from this user.")
        except Exception as e:
            await ctx.send(f"❌ An error occurred: {str(e)}")
    
    @commands.hybrid_command(name="warn", description="Warn a user")
    @is_moderator()
    @moderator_check()
    @app_commands.describe(
        member="The member to warn",
        reason="Reason for the warning"
    )
    async def warn(
        self,
        ctx: commands.Context,
        member: discord.Member,
        *,
        reason: Optional[str] = "No reason provided"
    ):
        """Warn a member"""
        try:
            await check_hierarchy(ctx, member)
        except HierarchyError:
            return
        
        try:
            # Add warning to database
            warning_id = await self.bot.db.add_warning(
                ctx.guild.id,
                member.id,
                ctx.author.id,
                reason
            )
            
            # Invalidate cache
            await self.bot.cache.invalidate_user_warnings(ctx.guild.id, member.id)
            
            # Get total warnings
            warnings = await self.bot.db.get_warnings(ctx.guild.id, member.id)
            warning_count = len(warnings)
            
            # Try to DM user
            try:
                dm_embed = EmbedFactory.warning(
                    "You have been warned",
                    f"**Server:** {ctx.guild.name}\n**Reason:** {reason}\n**Total Warnings:** {warning_count}"
                )
                await member.send(embed=dm_embed)
            except:
                pass
            
            # Send confirmation
            embed = EmbedFactory.moderation_action('warn', member, ctx.author, reason)
            embed.add_field(name="Warning ID", value=f"#{warning_id}", inline=True)
            embed.add_field(name="Total Warnings", value=str(warning_count), inline=True)
            await ctx.send(embed=embed)
            
            # Send to log channel
            await self._send_to_log(ctx.guild, embed)
            
            mod_logger.info(f"{ctx.author} warned {member} in {ctx.guild.name}: {reason}")
            
        except Exception as e:
            await ctx.send(f"❌ An error occurred: {str(e)}")
    
    @commands.hybrid_command(name="warnings", description="View a user's warnings")
    @is_moderator()
    @moderator_check()
    @app_commands.describe(member="The member to check warnings for")
    async def warnings(self, ctx: commands.Context, member: discord.Member):
        """View warnings for a member"""
        # Try cache first
        warnings = await self.bot.cache.get_user_warnings(ctx.guild.id, member.id)
        if warnings is None:
            warnings = await self.bot.db.get_warnings(ctx.guild.id, member.id)
            await self.bot.cache.set_user_warnings(ctx.guild.id, member.id, warnings)
        
        if not warnings:
            embed = EmbedFactory.info(
                f"Warnings for {member.display_name}",
                f"{member.mention} has no warnings."
            )
            await ctx.send(embed=embed)
            return
        
        embed = discord.Embed(
            title=f"⚠️ Warnings for {member.display_name}",
            description=f"Total: {len(warnings)} warning(s)",
            color=discord.Color.orange(),
            timestamp=datetime.utcnow()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        
        for i, warning in enumerate(warnings[:10], 1):  # Show max 10
            timestamp = warning['timestamp']
            embed.add_field(
                name=f"Warning #{warning['id']}",
                value=f"**Reason:** {warning['reason'] or 'No reason'}\n**Date:** <t:{int(datetime.fromisoformat(timestamp).timestamp())}:R>",
                inline=False
            )
        
        if len(warnings) > 10:
            embed.set_footer(text=f"Showing 10 of {len(warnings)} warnings")
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="clearwarnings", description="Clear all warnings for a user")
    @is_moderator()
    @moderator_check()
    @app_commands.describe(member="The member to clear warnings for")
    async def clearwarnings(self, ctx: commands.Context, member: discord.Member):
        """Clear all warnings for a member"""
        await self.bot.db.clear_warnings(ctx.guild.id, member.id)
        await self.bot.cache.invalidate_user_warnings(ctx.guild.id, member.id)
        
        embed = EmbedFactory.success(
            "Warnings Cleared",
            f"All warnings for {member.mention} have been cleared."
        )
        await ctx.send(embed=embed)
        
        mod_logger.info(f"{ctx.author} cleared warnings for {member} in {ctx.guild.name}")
    
    @commands.hybrid_command(name="removewarning", description="Remove a specific warning")
    @is_moderator()
    @moderator_check()
    @app_commands.describe(warning_id="The ID of the warning to remove")
    async def removewarning(self, ctx: commands.Context, warning_id: int):
        """Remove a specific warning by ID"""
        success = await self.bot.db.remove_warning(warning_id)
        
        if success:
            # Invalidate all warning caches for this guild
            await self.bot.cache.clear_pattern(f"warnings:{ctx.guild.id}:*")
            
            embed = EmbedFactory.success(
                "Warning Removed",
                f"Warning #{warning_id} has been removed."
            )
            mod_logger.info(f"{ctx.author} removed warning #{warning_id} in {ctx.guild.name}")
        else:
            embed = EmbedFactory.error(
                "Warning Not Found",
                f"Warning #{warning_id} was not found."
            )
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="history", description="View moderation history for a user")
    @is_moderator()
    @moderator_check()
    @app_commands.describe(member="The member to check history for")
    async def history(self, ctx: commands.Context, member: discord.Member):
        """View moderation history for a member"""
        actions = await self.bot.db.get_user_actions(ctx.guild.id, member.id)
        
        if not actions:
            embed = EmbedFactory.info(
                f"History for {member.display_name}",
                f"{member.mention} has no moderation history."
            )
            await ctx.send(embed=embed)
            return
        
        embed = discord.Embed(
            title=f"📋 Moderation History for {member.display_name}",
            description=f"Total: {len(actions)} action(s)",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        
        for action in actions[:10]:  # Show max 10
            timestamp = action['timestamp']
            moderator = ctx.guild.get_member(action['moderator_id'])
            mod_name = moderator.display_name if moderator else f"ID: {action['moderator_id']}"
            
            embed.add_field(
                name=f"{action['action'].capitalize()} - <t:{int(datetime.fromisoformat(timestamp).timestamp())}:R>",
                value=f"**Moderator:** {mod_name}\n**Reason:** {action['reason'] or 'No reason'}",
                inline=False
            )
        
        if len(actions) > 10:
            embed.set_footer(text=f"Showing 10 of {len(actions)} actions")
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="delete", description="Delete multiple messages")
    @is_moderator()
    @moderator_check()
    @app_commands.describe(amount="Number of messages to delete (1-50)")
    async def delete(self, ctx: commands.Context, amount: int):
        """Delete multiple messages"""
        if amount < 1 or amount > 50:
            await ctx.send("❌ Amount must be between 1 and 50.", ephemeral=True)
            return
        
        try:
            deleted = await ctx.channel.purge(limit=amount + 1)  # +1 for command message
            
            embed = EmbedFactory.success(
                "Messages Deleted",
                f"Deleted {len(deleted) - 1} message(s)."
            )
            msg = await ctx.send(embed=embed)
            
            # Delete confirmation after 5 seconds
            await msg.delete(delay=5)
            
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to delete messages.", ephemeral=True)
        except discord.HTTPException as e:
            await ctx.send(f"❌ Failed to delete messages: {e}", ephemeral=True)
    
    @commands.hybrid_command(name="slowmode", description="Set slowmode for a channel")
    @is_moderator()
    @moderator_check()
    @app_commands.describe(
        seconds="Slowmode duration in seconds (0 to disable)",
        channel="Channel to set slowmode in (defaults to current channel)"
    )
    async def slowmode(
        self,
        ctx: commands.Context,
        seconds: int,
        channel: Optional[discord.TextChannel] = None
    ):
        """Set slowmode for a channel"""
        channel = channel or ctx.channel
        
        if seconds < 0 or seconds > 21600:  # Max 6 hours
            await ctx.send("❌ Slowmode must be between 0 and 21600 seconds (6 hours).", ephemeral=True)
            return
        
        try:
            await channel.edit(slowmode_delay=seconds)
            
            if seconds == 0:
                embed = EmbedFactory.success(
                    "Slowmode Disabled",
                    f"Slowmode has been disabled in {channel.mention}."
                )
            else:
                embed = EmbedFactory.success(
                    "Slowmode Enabled",
                    f"Slowmode set to **{seconds}** second(s) in {channel.mention}."
                )
            
            await ctx.send(embed=embed)
            
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to edit this channel.", ephemeral=True)
        except discord.HTTPException as e:
            await ctx.send(f"❌ Failed to set slowmode: {e}", ephemeral=True)
    
    @commands.hybrid_command(name="lock", description="Lock a channel")
    @is_moderator()
    @moderator_check()
    @app_commands.describe(channel="Channel to lock (defaults to current channel)")
    async def lock(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        """Lock a channel"""
        channel = channel or ctx.channel
        
        try:
            overwrite = channel.overwrites_for(ctx.guild.default_role)
            overwrite.send_messages = False
            await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
            
            embed = EmbedFactory.success(
                "Channel Locked",
                f"🔒 {channel.mention} has been locked."
            )
            await ctx.send(embed=embed)
            
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to edit this channel.", ephemeral=True)
        except discord.HTTPException as e:
            await ctx.send(f"❌ Failed to lock channel: {e}", ephemeral=True)
    
    @commands.hybrid_command(name="unlock", description="Unlock a channel")
    @is_moderator()
    @moderator_check()
    @app_commands.describe(channel="Channel to unlock (defaults to current channel)")
    async def unlock(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        """Unlock a channel"""
        channel = channel or ctx.channel
        
        try:
            overwrite = channel.overwrites_for(ctx.guild.default_role)
            overwrite.send_messages = None
            await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
            
            embed = EmbedFactory.success(
                "Channel Unlocked",
                f"🔓 {channel.mention} has been unlocked."
            )
            await ctx.send(embed=embed)
            
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to edit this channel.", ephemeral=True)
        except discord.HTTPException as e:
            await ctx.send(f"❌ Failed to unlock channel: {e}", ephemeral=True)
    
    async def _send_to_log(self, guild: discord.Guild, embed: discord.Embed):
        """Send embed to log channel if configured"""
        config = await self.bot.db.get_guild_config(guild.id)
        if not config or not config.get('log_channel_id'):
            return
        
        channel = guild.get_channel(config['log_channel_id'])
        if channel:
            try:
                await channel.send(embed=embed)
            except:
                pass

async def setup(bot):

    await bot.add_cog(Moderation(bot))
