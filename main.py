from typing import Final
import os
import discord
from dotenv import load_dotenv
from manage import *
from tournament import Tournament

load_dotenv()
TOKEN: Final[str] = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = discord.Bot(intents=intents)

@bot.event
async def on_ready():
    print(f"{bot.user} is online")

##########################
# SLASH COMMANDS SECTION #
##########################

# Slash command to CREATE a new tournament
@bot.slash_command(name="create", description="Create a new tournament", guild_ids=[1286841607576092763])
async def create(
    ctx: discord.ApplicationContext,
    registration_channel: discord.TextChannel = discord.Option(
        discord.TextChannel, # Making sure the command recognizes the input as a channel
        description="The channel where player registration for the tournament will take place")
):   
    # Display the Modal requesting input from the user
    modal = Create_Tournament(reg_channel=registration_channel, title="Create Tournament")
    await ctx.send_modal(modal)

# Slash command to display a LIST OF ALL ACTIVE TOURNAMENTS
@bot.slash_command(name="tournaments_list", description="Show a list of all active tournaments and their ID numbers")
async def tournament_list(ctx):
    tournaments = Tournament.load_all_tournaments()
    list = discord.Embed(title="List of Tournaments", color=discord.Color.blue())

    # Loop to add each tournament from the tournaments list
    for t in tournaments:
        list.add_field(name=f"({t.id}) - {t.name}", value=f"Game: {t.game}", inline=False)
    await ctx.respond(embed=list)

# Slash command to ADMIN a tournament
@bot.slash_command(name = "admin", 
                    description = "Administrate a Tournament by entering its ID number.",
                    guild_ids=[1286841607576092763],
                    default_member_permissions=discord.Permissions(manage_channels=True))
async def admin(ctx, id:int = discord.Option(description="Find this ID number by using the tournaments_list command")):
   
    tournaments = Tournament.load_all_tournaments()
    tournament = next((t for t in tournaments if t.id == int(id)), None) # Go through all tournaments and find the id entered.

    # Only allow users with this permission to admin tournaments (TODO: Change this to a tournament organizer role)
    if not ctx.author.guild_permissions.manage_channels:
        await ctx.respond("You don't have the required permissions to use this command.", ephemeral=True)
        return
    
    if not tournament:
        await ctx.respond("Tournament not found.", ephemeral=True)
        return
    
    view = Admin(tournament)
    embed = view.get_embed()
    await ctx.respond("", view=view, embed=embed)

    admin_msg = await ctx.interaction.original_response()  
    tournament.admin_msg_id = admin_msg.id
    tournament.save()

def main():
    bot.run(TOKEN)

if __name__ == '__main__':
        main()