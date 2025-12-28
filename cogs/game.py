import discord
from discord.ext import commands
import random
import asyncio
import json
import time
from typing import Dict, List, Any

# Game data storage
active_games = {}

class GameState:
    def __init__(self, user_id):
        self.user_id = user_id
        self.compassion = 50
        self.bravery = 50
        self.hunger = 50  # Energy in original code
        self.power = 50
        self.has_dog = False
        self.location = "Forest"
        self.current_step = 0
        self.max_steps = 35
        self.current_decision = None
        self.message = None
        
    def get_stats_text(self):
        dog_status = "🐕 Has companion" if self.has_dog else "🚫 No companion"
        return f"""**Location:** {self.location}
**Stats:**
❤️ Compassion: {max(0, min(100, self.compassion))}
⚔️ Bravery: {max(0, min(100, self.bravery))}
🍖 Energy: {max(0, min(100, self.hunger))}
⚡ Power: {max(0, min(100, self.power))}
{dog_status}
**Progress:** {self.current_step}/{self.max_steps}"""
    
    def check_game_over(self):
        if self.compassion >= 100 or self.compassion <= 0:
            return "compassion"
        elif self.bravery >= 100 or self.bravery <= 0:
            return "bravery"
        elif self.hunger >= 100 or self.hunger <= 0:
            return "energy"
        elif self.power >= 100 or self.power <= 0:
            return "power"
        return None

class Decision:
    def __init__(self, title, description, art, choices, effects_description=""):
        self.title = title
        self.description = description
        self.art = art
        self.choices = choices  # List of choice dictionaries
        self.effects_description = effects_description

# Decision definitions
decisions = [
    Decision(
        "The Injured Dog",
        "You have found a dog. It looks hurt.",
        "        ___\n    (___()'';;\n    /,    /\n    \\\"--\\\\",
        [
            {"text": "Chase him away", "emoji": "👋", "effects": {"bravery": (4, 8), "compassion": (-8, -4)}},
            {"text": "Help him", "emoji": "❤️", "effects": {"bravery": (-8, -4), "compassion": (4, 8), "has_dog": True}}
        ],
        "[Affects: Compassion & Bravery]"
    ),
    
    Decision(
        "The Mysterious Apple",
        "You have found an apple. It might be poisoned.",
        "                  ___\n                _/`.-'`.\n      _      _/` .  _.'\n..:::::.(_)   /` _.'_./\n.oooooooooo\\ \\o/.-'__.'o.\n.ooooooooo`._\\_|_.'`oooooob.",
        [
            {"text": "Eat it", "emoji": "🍎", "effects": {"bravery": (4, 8), "hunger": "poison_check"}},
            {"text": "Throw it away", "emoji": "🗑️", "effects": {"bravery": (4, 8), "hunger": (-6, -2)}},
            {"text": "Give to dog", "emoji": "🐕", "effects": {"compassion": (2, 6)}, "requires_dog": True}
        ],
        "[Affects: Compassion, Energy, and Bravery]"
    ),
    
    Decision(
        "The Deer Corpse",
        "You find a corpse of a deer. It must have recently been killed by wolves.",
        "         __.------~~~-. \n      ,'/             `\\ \n      \" \\  ,..__ | ,_   `\\_, \n        >/|/   ~~\\||`\\(`~,~'.",
        [
            {"text": "Eat it", "emoji": "🥩", "effects": {"hunger": (20, 30)}},
            {"text": "Move on", "emoji": "🚶", "effects": {"hunger": (-14, -10)}},
            {"text": "Let dog eat", "emoji": "🐕", "effects": {"compassion": (20, 30)}, "requires_dog": True},
            {"text": "Share with dog", "emoji": "🤝", "effects": {"compassion": (4, 12), "hunger": (6, 16)}, "requires_dog": True}
        ],
        "[Affects: Compassion & Energy]"
    ),
    
    Decision(
        "The Bloody Wolf",
        "A bloody wolf glares at you with his right eye.",
        "       _    \n      / \\      _-'\n    _/|  \\-''- _ /\n__-' { |          \\ \n   /              \\ \n   /       'o.  |o }",
        [
            {"text": "Attack with wand", "emoji": "⚡", "effects": {"bravery": (2, 10), "power": 20}},
            {"text": "Flee", "emoji": "🏃", "effects": {"bravery": (-10, -3), "power": -10}},
            {"text": "Do nothing", "emoji": "🧍", "effects": {"power": -10, "bravery": (-20, -4)}}
        ],
        "[Affects: Power & Bravery]"
    ),
    
    Decision(
        "Path Split",
        "The path splits ahead.",
        " ____________________________________/   ,   /_______\n _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _\n ___________________        __________________________\n                   /   ,   /",
        [
            {"text": "Move left", "emoji": "⬅️", "effects": {"hunger": (-5, -1)}},
            {"text": "Move right", "emoji": "➡️", "effects": {"hunger": (-5, -1)}}
        ],
        "[Affects: Energy]"
    ),
    
    Decision(
        "The Fat Rabbit",
        "A rabbit bounds in front of you. It looks fat.",
        "              ,\\ \n              \\\\\\,_ \n                \\` ,\\ \n          __,.-' =__ ) \n        .'        ) \n      ,_/   ,    \\/\\_",
        [
            {"text": "Kill and eat", "emoji": "🗡️", "effects": {"compassion": (-10, -5), "hunger": (10, 20)}},
            {"text": "Leave alone", "emoji": "🐰", "effects": {"compassion": (2, 6), "hunger": (-10, -5)}},
            {"text": "Let dog hunt", "emoji": "🐕", "effects": {"compassion": (-6, -2), "bravery": (-20, -15), "hunger": (10, 20), "has_dog": False}, "requires_dog": True}
        ],
        "[Affects: Compassion, Bravery, Power, & Energy]"
    ),
    
    Decision(
        "The Graveyard",
        "You find a graveyard.",
        "                    .\"\"--..__\n _                     []       ``-.._\n.'` `'.                  ||__           `-._",
        [
            {"text": "Venture in", "emoji": "⚰️", "effects": {"bravery": 5, "location": "Graveyard"}},
            {"text": "Stay away", "emoji": "🚫", "effects": {"bravery": -5}}
        ],
        "[Affects: Bravery, Location]"
    ),
    
    Decision(
        "The Dark Castle",
        "You reach a clearing in a forest. Surrounded by dark trees, a dark castle looms over you.",
        "               -|             |-\n [-_-_-_-_-]          |             |          [-_-_-_-_-]\n  | o   o |           [  0   0   0  ]           | o   o |",
        [
            {"text": "Enter castle", "emoji": "🏰", "effects": {"bravery": 5, "location": "Castle", "hunger": (-10, -5)}},
            {"text": "Run away", "emoji": "🏃", "effects": {}}
        ],
        "[Affects: Bravery, Location]"
    ),
    
    Decision(
        "The Old Lady",
        "An old lady who was beaten by thieves begs for your help.",
        "           👵\n         \"Help!\"\n    Please help me!",
        [
            {"text": "Help her", "emoji": "🤝", "effects": {"compassion": (20, 25)}},
            {"text": "Leave her", "emoji": "🚶", "effects": {"compassion": (-25, -20)}}
        ],
        "[Affects: Compassion]"
    ),
    
    Decision(
        "The Mighty Moose",
        "You hear the thump of a moose getting closer and closer.",
        "                          .      //\n                    /) \\ |\\    //\n              (\\\\|  || \\)u|   |F     /)\n                \\```.FF  \\  \\  |J   .'/",
        [
            {"text": "Attack with wand", "emoji": "⚡", "effects": {"bravery": (1, 5), "power": (1, 5)}},
            {"text": "Flee", "emoji": "🏃", "effects": {"bravery": (-5, -1), "power": -15}},
            {"text": "Do nothing", "emoji": "🧍", "effects": {"bravery": (-5, -1), "power": (-10, -5)}}
        ],
        "[Affects: Power & Bravery]"
    ),
    
    Decision(
        "The Rusty Temple",
        "You see a rusty temple. It seems to have been there for ages.",
        "         ___\n        |___|        \n        |___|        \n      __|___|__      \n     |_________|     ",
        [
            {"text": "Enter temple", "emoji": "🏛️", "effects": {"bravery": 5, "location": "Temple"}},
            {"text": "Stay away", "emoji": "🚫", "effects": {"bravery": -5}}
        ],
        "[Affects: Bravery, Location]"
    ),
    
    Decision(
        "The Poisonous Snake",
        "A hissing snake blocks your path.",
        "    ~-._    .-~\n        ~-._.-~\n    jgs     ~",
        [
            {"text": "Attack it", "emoji": "⚔️", "effects": {"bravery": (3, 7), "power": (2, 5)}},
            {"text": "Go around", "emoji": "🔄", "effects": {"hunger": (-3, -1)}},
            {"text": "Wait it out", "emoji": "⏰", "effects": {"hunger": (-5, -2)}}
        ],
        "[Affects: Bravery, Power, Energy]"
    ),
    
    Decision(
        "The Magical Fountain",
        "You discover a glowing fountain with crystal clear water.",
        "    ~~~\n   ( o )\n    ~~~\n   |||||",
        [
            {"text": "Drink from it", "emoji": "💧", "effects": {"power": (5, 15), "hunger": (3, 8)}},
            {"text": "Fill your flask", "emoji": "🍶", "effects": {"hunger": (2, 5)}},
            {"text": "Ignore it", "emoji": "➡️", "effects": {"hunger": (-2, -1)}}
        ],
        "[Affects: Power, Energy]"
    ),
    
    Decision(
        "The Wandering Merchant",
        "An old merchant offers to trade items with you.",
        "    🎒\n   👴\n   /|\\\n   / \\",
        [
            {"text": "Trade with him", "emoji": "🤝", "effects": {"compassion": (2, 5), "power": (3, 7)}},
            {"text": "Rob him", "emoji": "💰", "effects": {"compassion": (-8, -3), "bravery": (2, 6)}},
            {"text": "Walk away", "emoji": "🚶", "effects": {}}
        ],
        "[Affects: Compassion, Power, Bravery]"
    ),
    
    Decision(
        "The Ancient Tree",
        "You find an enormous ancient tree with strange markings.",
        "      🌳\n     /||\\\n    / || \\\n      ||",
        [
            {"text": "Touch the tree", "emoji": "🤚", "effects": {"power": (10, 20)}},
            {"text": "Study markings", "emoji": "🔍", "effects": {"power": (3, 8)}},
            {"text": "Leave quickly", "emoji": "🏃", "effects": {"hunger": (-3, -1)}}
        ],
        "[Affects: Power, Energy]"
    )
]

def get_game_help():
    """Return help embed for game commands"""
    embed = discord.Embed(
        title="🎮 Dark Forest Game Help",
        description="A survival adventure game where you navigate through a dark forest!",
        color=0x2F3136
    )
    
    embed.add_field(
        name="🎯 Objective", 
        value="Survive 35 decisions to escape the forest!\nManage your four stats carefully - don't let any reach 0 or 100!",
        inline=False
    )
    
    embed.add_field(
        name="📊 Stats",
        value="❤️ **Compassion** - Your kindness and empathy\n"
              "⚔️ **Bravery** - Your courage in danger\n"
              "🍖 **Energy** - Your physical strength\n"
              "⚡ **Power** - Your magical abilities",
        inline=False
    )
    
    embed.add_field(
        name="🎮 Commands",
        value="`!game` - Start a new game\n"
              "`!endgame` - End your current game\n"
              "`!gamestats` - View your current game stats",
        inline=False
    )
    
    embed.add_field(
        name="⚠️ Warning",
        value="If any stat reaches 0 or 100, you die!\nEach decision affects your stats differently.",
        inline=False
    )
    
    return embed

async def present_decision(game_state):
    """Present a decision to the player"""
    try:
        # Choose a random decision
        decision = random.choice(decisions)
        game_state.current_decision = decision
        game_state.current_step += 1
        
        # Create embed for decision
        embed = discord.Embed(
            title=f"Decision {game_state.current_step}: {decision.title}",
            description=f"**{decision.description}**\n\n```\n{decision.art}\n```",
            color=0x3498db
        )
        
        embed.add_field(name="📊 Current Stats", value=game_state.get_stats_text(), inline=False)
        
        # Add choices
        choices_text = ""
        available_choices = []
        for choice in decision.choices:
            if choice.get("requires_dog", False) and not game_state.has_dog:
                continue
            choices_text += f"{choice['emoji']} {choice['text']}\n"
            available_choices.append(choice)
        
        embed.add_field(name="Choose your action:", value=choices_text, inline=False)
        embed.add_field(name="Effects", value=decision.effects_description, inline=False)
        embed.set_footer(text=f"Step {game_state.current_step}/{game_state.max_steps}")
        
        await game_state.message.edit(embed=embed)
        
        # Clear old reactions and add new ones
        await game_state.message.clear_reactions()
        for choice in available_choices:
            await game_state.message.add_reaction(choice["emoji"])
    except Exception as e:
        print(f"Error in present_decision: {e}")
        # Clean up the game if there's an error
        if game_state.user_id in active_games:
            del active_games[game_state.user_id]

async def process_choice(game_state, choice):
    """Process the player's choice and update game state"""
    try:
        results = []
        
        # Apply effects
        effects = choice["effects"]
        for stat, effect in effects.items():
            if stat == "has_dog":
                game_state.has_dog = effect
                results.append("🐕 You gained a companion!" if effect else "💔 Your dog left you...")
            elif stat == "location":
                game_state.location = effect
                results.append(f"📍 Moved to: {effect}")
            elif isinstance(effect, tuple):
                # Random range effect
                min_val, max_val = effect
                if min_val > max_val:
                    min_val, max_val = max_val, min_val  # Swap if needed
                change = random.randint(min_val, max_val)
                
                if stat == "compassion":
                    game_state.compassion += change
                    game_state.compassion = max(0, min(100, game_state.compassion))
                    results.append(f"❤️ Compassion {'increased' if change > 0 else 'decreased'} by {abs(change)}")
                elif stat == "bravery":
                    game_state.bravery += change
                    game_state.bravery = max(0, min(100, game_state.bravery))
                    results.append(f"⚔️ Bravery {'increased' if change > 0 else 'decreased'} by {abs(change)}")
                elif stat == "hunger":
                    game_state.hunger += change
                    game_state.hunger = max(0, min(100, game_state.hunger))
                    results.append(f"🍖 Energy {'increased' if change > 0 else 'decreased'} by {abs(change)}")
                elif stat == "power":
                    game_state.power += change
                    game_state.power = max(0, min(100, game_state.power))
                    results.append(f"⚡ Power {'increased' if change > 0 else 'decreased'} by {abs(change)}")
            elif stat == "hunger" and effect == "poison_check":
                # Special poison check
                if random.randint(1, 2) == 1:
                    change = random.randint(4, 12)
                    game_state.hunger += change
                    game_state.hunger = max(0, min(100, game_state.hunger))
                    results.append(f"🍎 The apple was safe! Energy increased by {change}")
                else:
                    change = random.randint(4, 12)
                    game_state.hunger -= change
                    game_state.hunger = max(0, min(100, game_state.hunger))
                    results.append(f"☠️ The apple was poisoned! Energy decreased by {change}")
            elif isinstance(effect, int):
                # Fixed effect
                if stat == "compassion":
                    game_state.compassion += effect
                    game_state.compassion = max(0, min(100, game_state.compassion))
                    results.append(f"❤️ Compassion {'increased' if effect > 0 else 'decreased'} by {abs(effect)}")
                elif stat == "bravery":
                    game_state.bravery += effect
                    game_state.bravery = max(0, min(100, game_state.bravery))
                    results.append(f"⚔️ Bravery {'increased' if effect > 0 else 'decreased'} by {abs(effect)}")
                elif stat == "hunger":
                    game_state.hunger += effect
                    game_state.hunger = max(0, min(100, game_state.hunger))
                    results.append(f"🍖 Energy {'increased' if effect > 0 else 'decreased'} by {abs(effect)}")
                elif stat == "power":
                    game_state.power += effect
                    game_state.power = max(0, min(100, game_state.power))
                    results.append(f"⚡ Power {'increased' if effect > 0 else 'decreased'} by {abs(effect)}")
        
        # Always decrease hunger slightly (moving costs energy)
        hunger_loss = random.randint(1, 3)
        game_state.hunger -= hunger_loss
        game_state.hunger = max(0, game_state.hunger)
        
        # Show results
        result_text = "\n".join(results) if results else "Nothing happened..."
        embed = discord.Embed(
            title="Choice Results",
            description=f"**You chose:** {choice['text']}\n\n**Results:**\n{result_text}",
            color=0x2ecc71
        )
        
        embed.add_field(name="📊 Updated Stats", value=game_state.get_stats_text(), inline=False)
        
        # Check for game over conditions
        game_over_reason = game_state.check_game_over()
        if game_over_reason:
            await handle_game_over(game_state, game_over_reason)
            return
        
        # Check for win condition
        if game_state.current_step >= game_state.max_steps:
            await handle_victory(game_state)
            return
        
        embed.set_footer(text="React with ➡️ to continue to the next decision")
        await game_state.message.edit(embed=embed)
        await game_state.message.clear_reactions()
        await game_state.message.add_reaction("➡️")
        
        # Set state to waiting for continue
        game_state.current_decision = "waiting_continue"
        
    except Exception as e:
        print(f"Error in process_choice: {e}")
        if game_state.user_id in active_games:
            del active_games[game_state.user_id]

async def handle_game_over(game_state, reason):
    """Handle game over scenario"""
    try:
        death_messages = {
            "compassion": "💀 Your extreme compassion led you into a deadly trap..." if game_state.compassion >= 100 else "💀 Your lack of compassion made you cold and heartless...",
            "bravery": "💀 Your reckless bravery was your downfall..." if game_state.bravery >= 100 else "💀 Your cowardice left you defenseless...",
            "energy": "💀 You collapsed from overeating..." if game_state.hunger >= 100 else "💀 You starved to death...",
            "power": "💀 Your magical power consumed you..." if game_state.power >= 100 else "💀 You were too weak to defend yourself..."
        }
        
        embed = discord.Embed(
            title="💀 GAME OVER 💀",
            description=f"{death_messages[reason]}\n\nYou perished and were long forgotten...\n\n**Final Stats:**\n{game_state.get_stats_text()}",
            color=0xe74c3c
        )
        
        embed.set_footer(text="Use !game to start a new adventure")
        await game_state.message.edit(embed=embed)
        await game_state.message.clear_reactions()
        
        if game_state.user_id in active_games:
            del active_games[game_state.user_id]
    except Exception as e:
        print(f"Error in handle_game_over: {e}")
        if game_state.user_id in active_games:
            del active_games[game_state.user_id]

async def handle_victory(game_state):
    """Handle victory scenario"""
    try:
        embed = discord.Embed(
            title="🎉 VICTORY! 🎉",
            description="Congratulations! You found your way to civilization!\n\nYou have successfully navigated the Dark Dark Forest and survived all 35 decisions!\n\n**Final Stats:**\n" + game_state.get_stats_text(),
            color=0xf1c40f
        )
        
        embed.set_footer(text="Use !game to start a new adventure")
        await game_state.message.edit(embed=embed)
        await game_state.message.clear_reactions()
        
        if game_state.user_id in active_games:
            del active_games[game_state.user_id]
    except Exception as e:
        print(f"Error in handle_victory: {e}")
        if game_state.user_id in active_games:
            del active_games[game_state.user_id]

def setup_game_commands(bot):
    """Setup game commands for the bot"""
    
    @bot.command(name='game', help='🎮 Start the Dark Forest adventure game')
    async def start_game(ctx):
        user_id = ctx.author.id
        
        if user_id in active_games:
            embed = discord.Embed(
                title="🎮 Game Already Active",
                description="You already have an active game! Finish it first or use `!endgame` to quit.",
                color=0xff9900
            )
            await ctx.send(embed=embed)
            return
        
        # Create new game state
        game_state = GameState(user_id)
        active_games[user_id] = game_state
        
        # Create initial embed
        embed = discord.Embed(
            title="🌲 THE DARK DARK FOREST 🌲",
            description="You are lost in the woods. You have four stats to help you survive:\n\n"
                       "❤️ **Compassion** - Your kindness and empathy\n"
                       "⚔️ **Bravery** - Your courage in danger\n"
                       "🍖 **Energy** - Your physical strength\n"
                       "⚡ **Power** - Your magical abilities\n\n"
                       "⚠️ **Warning:** Do not have too much or too little of any stat, or you will die!\n\n"
                       "**Goal:** Survive 35 decisions to escape the forest!",
            color=0x2F3136
        )
        
        embed.add_field(name="📊 Current Stats", value=game_state.get_stats_text(), inline=False)
        embed.set_footer(text="React with ✅ to begin your adventure!")
        
        message = await ctx.send(embed=embed)
        await message.add_reaction("✅")
        
        # Store message for later editing
        game_state.message = message

    @bot.command(name='endgame', help='🛑 End your current game')
    async def end_game(ctx):
        user_id = ctx.author.id
        if user_id in active_games:
            del active_games[user_id]
            embed = discord.Embed(
                title="🛑 Game Ended",
                description="Your game has been ended.",
                color=0xff0000
            )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="❌ No Active Game",
                description="You don't have an active game.",
                color=0xff0000
            )
            await ctx.send(embed=embed)

    @bot.command(name='gamestats', help='📊 View your current game statistics')
    async def game_stats(ctx):
        user_id = ctx.author.id
        if user_id not in active_games:
            embed = discord.Embed(
                title="❌ No Active Game",
                description="You don't have an active game. Use `!game` to start one!",
                color=0xff0000
            )
            await ctx.send(embed=embed)
            return
        
        game_state = active_games[user_id]
        embed = discord.Embed(
            title="📊 Game Statistics",
            description=game_state.get_stats_text(),
            color=0x3498db
        )
        
        # Add progress information
        progress_percent = (game_state.current_step / game_state.max_steps) * 100
        embed.add_field(
            name="📈 Progress",
            value=f"{progress_percent:.1f}% complete\n{game_state.max_steps - game_state.current_step} decisions remaining",
            inline=False
        )
        
        await ctx.send(embed=embed)

    @bot.event
    async def on_reaction_add(reaction, user):
        try:
            if user.bot:
                return
                
            user_id = user.id
            if user_id not in active_games:
                return
                
            game_state = active_games[user_id]
            
            # Check if this is the correct message
            if not hasattr(game_state, 'message') or reaction.message.id != game_state.message.id:
                return
            
            # Remove the user's reaction
            try:
                await reaction.remove(user)
            except (discord.errors.NotFound, discord.errors.Forbidden):
                pass
            
            emoji = str(reaction.emoji)
            
            # Handle start game
            if emoji == "✅" and game_state.current_step == 0:
                await present_decision(game_state)
                return
            
            # Handle continue to next decision
            if emoji == "➡️" and game_state.current_decision == "waiting_continue":
                await present_decision(game_state)
                return
            
            # Handle decision choices
            if game_state.current_decision and game_state.current_decision != "waiting_continue":
                for choice in game_state.current_decision.choices:
                    if emoji == choice["emoji"]:
                        # Check if choice requires dog
                        if choice.get("requires_dog", False) and not game_state.has_dog:
                            continue
                        await process_choice(game_state, choice)
                        break
        except Exception as e:
            print(f"Error in game on_reaction_add: {e}")
            if user_id in active_games:
                del active_games[user_id]

async def setup(bot):
    setup_game_commands(bot)
