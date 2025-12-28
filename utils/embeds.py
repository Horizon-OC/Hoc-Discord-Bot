import discord
from datetime import datetime
from config import Config
from typing import Optional

class EmbedFactory:
    """Factory class for creating standardized embeds"""
    
    @staticmethod
    def create_embed(
        title: str = None,
        description: str = None,
        color: int = None,
        footer: str = None,
        timestamp: bool = True
    ) -> discord.Embed:
        """Create a basic embed"""
        embed = discord.Embed(
            title=title,
            description=description,
            color=color or Config.EMBED_COLOR
        )
        
        if timestamp:
            embed.timestamp = datetime.utcnow()
        
        if footer:
            embed.set_footer(text=footer)
        
        return embed
    
    @staticmethod
    def success(title: str = None, description: str = None) -> discord.Embed:
        """Create a success embed"""
        return EmbedFactory.create_embed(
            title=f"✅ {title}" if title else "✅ Success",
            description=description,
            color=Config.SUCCESS_COLOR
        )
    
    @staticmethod
    def error(title: str = None, description: str = None) -> discord.Embed:
        """Create an error embed"""
        return EmbedFactory.create_embed(
            title=f"❌ {title}" if title else "❌ Error",
            description=description,
            color=Config.ERROR_COLOR
        )
    
    @staticmethod
    def warning(title: str = None, description: str = None) -> discord.Embed:
        """Create a warning embed"""
        return EmbedFactory.create_embed(
            title=f"⚠️ {title}" if title else "⚠️ Warning",
            description=description,
            color=Config.WARNING_COLOR
        )
    
    @staticmethod
    def info(title: str = None, description: str = None) -> discord.Embed:
        """Create an info embed"""
        return EmbedFactory.create_embed(
            title=f"ℹ️ {title}" if title else "ℹ️ Information",
            description=description,
            color=Config.EMBED_COLOR
        )
    
    @staticmethod
    def moderation_action(
        action: str,
        target: discord.Member,
        moderator: discord.Member,
        reason: Optional[str] = None
    ) -> discord.Embed:
        """Create a moderation action embed"""
        action_emojis = {
            'ban': '🔨',
            'kick': '👢',
            'mute': '🔇',
            'unmute': '🔊',
            'warn': '⚠️',
            'timeout': '⏰'
        }
        
        emoji = action_emojis.get(action.lower(), '🛡️')
        
        embed = discord.Embed(
            title=f"{emoji} {action.capitalize()}",
            color=Config.WARNING_COLOR,
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(name="User", value=target.mention, inline=True)
        embed.add_field(name="Moderator", value=moderator.mention, inline=True)
        
        if reason:
            embed.add_field(name="Reason", value=reason, inline=False)
        else:
            embed.add_field(name="Reason", value="No reason provided", inline=False)
        
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.set_footer(text=f"User ID: {target.id}")
        
        return embed
    
    @staticmethod
    def user_info(member: discord.Member) -> discord.Embed:
        """Create a user info embed"""
        embed = discord.Embed(
            title=f"User Information - {member}",
            color=member.color if member.color != discord.Color.default() else Config.EMBED_COLOR,
            timestamp=datetime.utcnow()
        )
        
        embed.set_thumbnail(url=member.display_avatar.url)
        
        embed.add_field(name="ID", value=str(member.id), inline=True)
        embed.add_field(name="Nickname", value=member.nick or "None", inline=True)
        embed.add_field(name="Bot", value="Yes" if member.bot else "No", inline=True)
        
        embed.add_field(
            name="Account Created",
            value=f"<t:{int(member.created_at.timestamp())}:R>",
            inline=True
        )
        embed.add_field(
            name="Joined Server",
            value=f"<t:{int(member.joined_at.timestamp())}:R>" if member.joined_at else "Unknown",
            inline=True
        )
        
        roles = [role.mention for role in member.roles[1:]]  # Skip @everyone
        embed.add_field(
            name=f"Roles [{len(roles)}]",
            value=" ".join(roles) if roles else "No roles",
            inline=False
        )
        
        return embed
    
    @staticmethod
    def server_info(guild: discord.Guild) -> discord.Embed:
        """Create a server info embed"""
        embed = discord.Embed(
            title=f"Server Information - {guild.name}",
            color=Config.EMBED_COLOR,
            timestamp=datetime.utcnow()
        )
        
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        embed.add_field(name="ID", value=str(guild.id), inline=True)
        embed.add_field(name="Owner", value=guild.owner.mention if guild.owner else "Unknown", inline=True)
        embed.add_field(name="Created", value=f"<t:{int(guild.created_at.timestamp())}:R>", inline=True)
        
        embed.add_field(name="Members", value=str(guild.member_count), inline=True)
        embed.add_field(name="Channels", value=str(len(guild.channels)), inline=True)
        embed.add_field(name="Roles", value=str(len(guild.roles)), inline=True)
        
        embed.add_field(name="Boosts", value=f"Level {guild.premium_tier} ({guild.premium_subscription_count} boosts)", inline=True)
        
        return embed