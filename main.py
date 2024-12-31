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
                    guild_ids=[1286841607576092763])
async def admin(ctx: discord.ApplicationContext, id:int = discord.Option(description="Find this ID number by using the tournaments_list command")):
    # Find the tournament
    tournaments = Tournament.load_all_tournaments()
    tournament: Tournament = next((t for t in tournaments if t.id == int(id)), None) # Go through all tournaments and find the id entered.

    if not tournament:
        if not ctx.response.is_done():
            await ctx.respond("Tournament not found.", ephemeral=True)
        else:
            await ctx.followup.send("Tournament not found.", ephemeral=True)
        return
    
    # Only allow users with this permission to admin tournaments
    user: discord.Member = ctx.guild.get_member(ctx.user.id)
    admin_role: discord.Role = discord.utils.get(ctx.guild.roles, name=tournament.admin_role)

    if admin_role not in user.roles and not user.guild_permissions.administrator:
        if not ctx.response.is_done():
            await ctx.respond("Failed. Only Tournament Admins have permission to perform this action.", ephemeral=True)
        else:
            await ctx.followup.send("Failed. Only Tournament Admins have permission to perform this action.", ephemeral=True)
        return   
        
    view = Admin(tournament)
    embed = view.get_embed()
    if not ctx.response.is_done():
        await ctx.respond("", view=view, embed=embed)
    else:
        await ctx.followup.send("", view=view, embed=embed)

    admin_msg = await ctx.interaction.original_response()  
    tournament.admin_msg_id = admin_msg.id
    tournament.save()

def main():
    bot.run(TOKEN)
    ''' TODO in the future
    ENVIRONMENT = os.getenv("ENVIRONMENT")  # "development" or "production"
    if ENVIRONMENT == "development":
        bot.run(DEVELOPMENT_TOKEN)
    else:
        bot.run(PRODUCTION_TOKEN)'''


if __name__ == '__main__':
        main()