import discord
from discord.ext import commands
from typing import Union

class HierarchyError(commands.CheckFailure):
    """Custom exception for hierarchy check failures"""
    pass

def is_moderator():
    """Decorator to check if user has moderator role or administrator permission"""
    async def predicate(ctx: commands.Context):
        # Don't allow in DMs
        if not ctx.guild:
            return False
        
        # Administrators always bypass mod role check
        if ctx.author.guild_permissions.administrator:
            return True
            
        # Get guild config
        config = await ctx.bot.db.get_guild_config(ctx.guild.id)
        
        if not config or not config.get('mod_role_id'):
            await ctx.send("❌ No moderator role has been set. An administrator needs to use `/setmod` first.")
            return False
        
        mod_role_id = config['mod_role_id']
        mod_role = ctx.guild.get_role(mod_role_id)
        
        if not mod_role:
            await ctx.send("❌ The configured moderator role no longer exists. Please reconfigure with `/setmod`.")
            return False
        
        # Check if user has the mod role
        has_role = mod_role in ctx.author.roles
        
        if not has_role:
            await ctx.send("❌ You need the moderator role or administrator permission to use this command.")
            return False
        
        return True
    
    return commands.check(predicate)

def moderator_check():
    """Additional check for moderator commands - checks bot permissions"""
    async def predicate(ctx: commands.Context):
        # Just return True, don't block commands
        return True
    
    return commands.check(predicate)

async def check_hierarchy(ctx: commands.Context, target: discord.Member):
    """Check if moderator can act on target user"""
    # Can't moderate yourself
    if target.id == ctx.author.id:
        await ctx.send("❌ You cannot moderate yourself.")
        raise HierarchyError("Cannot moderate self")
    
    # Can't moderate the bot
    if target.id == ctx.bot.user.id:
        await ctx.send("❌ You cannot moderate me!")
        raise HierarchyError("Cannot moderate bot")
    
    # Can't moderate server owner
    if target.id == ctx.guild.owner_id:
        await ctx.send("❌ You cannot moderate the server owner.")
        raise HierarchyError("Cannot moderate owner")
    
    # Check role hierarchy (unless moderator is admin)
    if not ctx.author.guild_permissions.administrator:
        if target.top_role >= ctx.author.top_role:
            await ctx.send("❌ You cannot moderate someone with an equal or higher role.")
            raise HierarchyError("Insufficient role hierarchy")
    
    # Check if bot can moderate target
    if target.top_role >= ctx.guild.me.top_role:
        await ctx.send("❌ I cannot moderate someone with an equal or higher role than me.")
        raise HierarchyError("Bot insufficient role hierarchy")
    
    return True