import discord
from discord.ext import commands
from datetime import datetime
from utils.embeds import EmbedFactory
from utils.logger import bot_logger, mod_logger
from config import Config

class Events(commands.Cog):
    """Event handlers for the bot"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        """Called when bot joins a guild"""
        bot_logger.info(f"Joined guild: {guild.name} (ID: {guild.id})")
        
        # Try to send welcome message
        if guild.system_channel:
            try:
                embed = discord.Embed(
                    title="👋 Thanks for adding me!",
                    description=(
                        f"Hello! I'm a moderation bot with error code lookup features.\n\n"
                        f"**Getting Started:**\n"
                        f"• Set a moderator role: `{Config.PREFIX}setmod @role`\n"
                        f"• Set a log channel: `{Config.PREFIX}setlog #channel`\n"
                        f"• View all commands: `{Config.PREFIX}help`\n\n"
                        f"Use either `{Config.PREFIX}` prefix or `/` slash commands!"
                    ),
                    color=Config.EMBED_COLOR
                )
                await guild.system_channel.send(embed=embed)
            except:
                pass
    
    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        """Called when bot leaves a guild"""
        bot_logger.info(f"Left guild: {guild.name} (ID: {guild.id})")
    
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Called when a member joins the server"""
        config = await self.bot.db.get_guild_config(member.guild.id)
        
        if not config or not config.get('log_joins') or not config.get('log_channel_id'):
            return
        
        channel = member.guild.get_channel(config['log_channel_id'])
        if not channel:
            return
        
        embed = discord.Embed(
            title="📥 Member Joined",
            description=f"{member.mention} has joined the server.",
            color=Config.SUCCESS_COLOR,
            timestamp=datetime.utcnow()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Account Created", value=f"<t:{int(member.created_at.timestamp())}:R>", inline=True)
        embed.set_footer(text=f"User ID: {member.id}")
        
        try:
            await channel.send(embed=embed)
        except:
            pass
    
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Called when a member leaves the server"""
        config = await self.bot.db.get_guild_config(member.guild.id)
        
        if not config or not config.get('log_leaves') or not config.get('log_channel_id'):
            return
        
        channel = member.guild.get_channel(config['log_channel_id'])
        if not channel:
            return
        
        embed = discord.Embed(
            title="📤 Member Left",
            description=f"{member.mention} has left the server.",
            color=Config.WARNING_COLOR,
            timestamp=datetime.utcnow()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        
        if member.joined_at:
            embed.add_field(name="Joined", value=f"<t:{int(member.joined_at.timestamp())}:R>", inline=True)
        
        embed.set_footer(text=f"User ID: {member.id}")
        
        try:
            await channel.send(embed=embed)
        except:
            pass
    
    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        """Called when a member is banned"""
        config = await self.bot.db.get_guild_config(guild.id)
        
        if not config or not config.get('log_bans') or not config.get('log_channel_id'):
            return
        
        channel = guild.get_channel(config['log_channel_id'])
        if not channel:
            return
        
        # Try to get ban reason from audit log
        reason = "No reason found"
        moderator = None
        
        try:
            async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.ban):
                if entry.target.id == user.id:
                    reason = entry.reason or "No reason provided"
                    moderator = entry.user
                    break
        except:
            pass
        
        embed = discord.Embed(
            title="🔨 Member Banned",
            description=f"{user.mention} was banned from the server.",
            color=Config.ERROR_COLOR,
            timestamp=datetime.utcnow()
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        
        if moderator:
            embed.add_field(name="Moderator", value=moderator.mention, inline=True)
        
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_footer(text=f"User ID: {user.id}")
        
        try:
            await channel.send(embed=embed)
        except:
            pass
    
    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        """Called when a member is unbanned"""
        config = await self.bot.db.get_guild_config(guild.id)
        
        if not config or not config.get('log_bans') or not config.get('log_channel_id'):
            return
        
        channel = guild.get_channel(config['log_channel_id'])
        if not channel:
            return
        
        embed = discord.Embed(
            title="🔓 Member Unbanned",
            description=f"{user.mention} was unbanned from the server.",
            color=Config.SUCCESS_COLOR,
            timestamp=datetime.utcnow()
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_footer(text=f"User ID: {user.id}")
        
        try:
            await channel.send(embed=embed)
        except:
            pass
    
    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        """Called when a message is deleted"""
        if message.author.bot or not message.guild:
            return
        
        config = await self.bot.db.get_guild_config(message.guild.id)
        
        if not config or not config.get('log_message_deletes') or not config.get('log_channel_id'):
            return
        
        channel = message.guild.get_channel(config['log_channel_id'])
        if not channel or channel.id == message.channel.id:
            return
        
        embed = discord.Embed(
            title="🗑️ Message Deleted",
            description=f"Message by {message.author.mention} deleted in {message.channel.mention}",
            color=Config.WARNING_COLOR,
            timestamp=datetime.utcnow()
        )
        
        if message.content:
            content = message.content[:1024]
            embed.add_field(name="Content", value=content, inline=False)
        
        if message.attachments:
            embed.add_field(
                name="Attachments",
                value="\n".join([att.filename for att in message.attachments]),
                inline=False
            )
        
        embed.set_footer(text=f"Message ID: {message.id} | User ID: {message.author.id}")
        
        try:
            await channel.send(embed=embed)
        except:
            pass
    
    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """Called when a message is edited"""
        if before.author.bot or not before.guild or before.content == after.content:
            return
        
        config = await self.bot.db.get_guild_config(before.guild.id)
        
        if not config or not config.get('log_message_edits') or not config.get('log_channel_id'):
            return
        
        channel = before.guild.get_channel(config['log_channel_id'])
        if not channel or channel.id == before.channel.id:
            return
        
        embed = discord.Embed(
            title="✏️ Message Edited",
            description=f"Message by {before.author.mention} edited in {before.channel.mention}\n[Jump to Message]({after.jump_url})",
            color=Config.EMBED_COLOR,
            timestamp=datetime.utcnow()
        )
        
        if before.content:
            embed.add_field(name="Before", value=before.content[:1024], inline=False)
        
        if after.content:
            embed.add_field(name="After", value=after.content[:1024], inline=False)
        
        embed.set_footer(text=f"Message ID: {before.id} | User ID: {before.author.id}")
        
        try:
            await channel.send(embed=embed)
        except:
            pass
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Called when a message is sent"""
        if message.author.bot:
            return
        
        # QP reaction feature from original bot
        if message.content.lower().startswith(',qp'):
            try:
                await message.add_reaction('⬆️')
                await message.add_reaction('⬇️')
            except:
                pass

async def setup(bot):
    await bot.add_cog(Events(bot))