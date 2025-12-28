import re
import discord
from discord.ext import commands
from discord import app_commands
from helpers.errcodes import *
from config import Config

class ErrorCodes(commands.Cog):
    """Nintendo error code lookup commands"""
    
    def __init__(self, bot):
        self.bot = bot
        self.dds_re = re.compile(r"0\d{2}\-\d{4}")
        self.wiiu_re = re.compile(r"1\d{2}\-\d{4}")
        self.switch_re = re.compile(r"2\d{3}\-\d{4}")
        self.no_err_desc = (
            "It seems like your error code is unknown. "
            "You can check on Switchbrew for your error code at "
            "<https://switchbrew.org/wiki/Error_codes>"
        )
        self.rickroll = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    
    @commands.hybrid_command(
        name="err",
        aliases=["nxerr", "serr", "dderr", "3dserr", "3err", "dserr", "wiiuerr", "uerr", "wuerr", "mochaerr"],
        description="Look up Nintendo error codes (Switch, 3DS, Wii U)"
    )
    @app_commands.describe(error_code="The error code to look up")
    async def err(self, ctx: commands.Context, error_code: str):
        """Look up Nintendo error codes - automatically detects console"""
        err = error_code.strip()
        
        # Detect which console based on error format
        if self.switch_re.match(err) or err.startswith("0x"):
            await self._handle_switch_error(ctx, err)
        elif self.dds_re.match(err):
            await self._handle_3ds_error(ctx, err)
        elif self.wiiu_re.match(err):
            await self._handle_wiiu_error(ctx, err)
        elif err in switch_game_err:
            await self._handle_switch_game_error(ctx, err)
        else:
            await ctx.send("❌ Unknown error code format. Supported formats:\n• Switch: `2XXX-XXXX` or `0xXXXXXX`\n• 3DS: `0XX-XXXX` or `0xXXXXXX`\n• Wii U: `1XX-XXXX`")
    
    async def _handle_switch_error(self, ctx: commands.Context, err: str):
        """Handle Switch error codes"""
        if err.startswith("0x"):
            try:
                err = err[2:]
                errcode = int(err, 16)
                module = errcode & 0x1FF
                desc = (errcode >> 9) & 0x3FFF
            except ValueError:
                await ctx.send("❌ Invalid hexadecimal error code.")
                return
        else:
            module = int(err[0:4]) - 2000
            desc = int(err[5:9])
            errcode = (desc << 9) + module
        
        str_errcode = f"{(module + 2000):04}-{desc:04}"
        
        # Get module name
        if module in switch_modules:
            err_module = switch_modules[module]
        else:
            err_module = "Unknown"
        
        # Set initial value
        err_description = self.no_err_desc
        
        # Search for error description
        if errcode in switch_known_errcodes:
            err_description = switch_known_errcodes[errcode]
        elif errcode in switch_support_page:
            err_description = switch_support_page[errcode]
        elif module in switch_known_errcode_ranges:
            for errcode_range in switch_known_errcode_ranges[module]:
                if desc >= errcode_range[0] and desc <= errcode_range[1]:
                    err_description = errcode_range[2]
                    break
        
        # Create embed
        embed = discord.Embed(
            title=f"{str_errcode} / {hex(errcode)}",
            url=self.rickroll,
            description=err_description,
            color=Config.EMBED_COLOR
        )
        embed.add_field(name="Module", value=f"{err_module} ({module})", inline=True)
        embed.add_field(name="Description", value=desc, inline=True)
        
        if "ban" in err_description.lower():
            embed.set_footer(text="F to you | Console: Nintendo Switch")
        else:
            embed.set_footer(text="Console: Nintendo Switch")
        
        await ctx.send(embed=embed)
    
    async def _handle_3ds_error(self, ctx: commands.Context, err: str):
        """Handle 3DS error codes"""
        if err.startswith("0x"):
            derr = err[2:].strip()
            try:
                rc = int(derr, 16)
                desc = rc & 0x3FF
                mod = (rc >> 10) & 0xFF
                summ = (rc >> 21) & 0x3F
                level = (rc >> 27) & 0x1F
                
                embed = discord.Embed(
                    title=f"0x{rc:X}",
                    color=Config.EMBED_COLOR
                )
                embed.add_field(name="Module", value=dds_modules.get(mod, mod), inline=True)
                embed.add_field(name="Description", value=dds_descriptions.get(desc, desc), inline=True)
                embed.add_field(name="Summary", value=dds_summaries.get(summ, summ), inline=True)
                embed.add_field(name="Level", value=dds_levels.get(level, level), inline=True)
                embed.set_footer(text="Console: Nintendo 3DS")
                
                await ctx.send(embed=embed)
            except ValueError:
                await ctx.send("❌ Invalid hexadecimal error code.")
        else:
            if err in dds_errcodes:
                err_description = dds_errcodes[err]
            else:
                err_description = self.no_err_desc
            
            embed = discord.Embed(
                title=err,
                url=self.rickroll,
                description=err_description,
                color=Config.EMBED_COLOR
            )
            embed.set_footer(text="Console: Nintendo 3DS")
            await ctx.send(embed=embed)
    
    async def _handle_wiiu_error(self, ctx: commands.Context, err: str):
        """Handle Wii U error codes"""
        module = err[2:3]
        desc = err[5:8]
        
        if err in wii_u_errors:
            err_description = wii_u_errors[err]
        else:
            err_description = self.no_err_desc
        
        embed = discord.Embed(
            title=err,
            url=self.rickroll,
            description=err_description,
            color=Config.EMBED_COLOR
        )
        embed.set_footer(text="Console: Nintendo Wii U")
        embed.add_field(name="Module", value=module, inline=True)
        embed.add_field(name="Description", value=desc, inline=True)
        
        await ctx.send(embed=embed)
    
    async def _handle_switch_game_error(self, ctx: commands.Context, err: str):
        """Handle Switch game-specific errors"""
        game, desc = switch_game_err[err].split(":", 1)
        
        embed = discord.Embed(
            title=err,
            url=self.rickroll,
            description=desc,
            color=Config.EMBED_COLOR
        )
        embed.set_footer(text="Console: Nintendo Switch")
        embed.add_field(name="Game", value=game, inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(
        name="err2hex",
        aliases=["e2h"],
        description="Convert Nintendo Switch error code to hexadecimal"
    )
    @app_commands.describe(error_code="The Switch error code to convert")
    async def err2hex(self, ctx: commands.Context, error_code: str):
        """Convert Nintendo Switch error code to hexadecimal"""
        err = error_code.strip()
        
        if self.switch_re.match(err):
            try:
                module = int(err[0:4]) - 2000
                desc = int(err[5:9])
                errcode = (desc << 9) + module
                
                embed = discord.Embed(
                    title="Error Code Conversion",
                    description=f"`{err}` → `{hex(errcode)}`",
                    color=Config.EMBED_COLOR
                )
                await ctx.send(embed=embed)
            except ValueError:
                await ctx.send("❌ Invalid error code format.")
        else:
            await ctx.send("❌ This doesn't follow the typical Nintendo Switch 2XXX-XXXX format.")
    
    @commands.hybrid_command(
        name="hex2err",
        aliases=["h2e"],
        description="Convert hexadecimal to Nintendo Switch error code"
    )
    @app_commands.describe(hex_code="The hexadecimal code to convert")
    async def hex2err(self, ctx: commands.Context, hex_code: str):
        """Convert hexadecimal to Nintendo Switch error code"""
        err = hex_code.strip()
        
        if err.startswith("0x"):
            try:
                err = err[2:]
                err_int = int(err, 16)
                module = err_int & 0x1FF
                desc = (err_int >> 9) & 0x3FFF
                errcode = f"{(module + 2000):04}-{desc:04}"
                
                embed = discord.Embed(
                    title="Hexadecimal Conversion",
                    description=f"`0x{err}` → `{errcode}`",
                    color=Config.EMBED_COLOR
                )
                await ctx.send(embed=embed)
            except ValueError:
                await ctx.send("❌ Invalid hexadecimal format.")
        else:
            await ctx.send("❌ This doesn't look like typical hexadecimal (should start with 0x).")

async def setup(bot):
    await bot.add_cog(ErrorCodes(bot))