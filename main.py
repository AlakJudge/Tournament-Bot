from typing import Final
import os
import discord
from dotenv import load_dotenv
from t_management import Create_Tournament
from tournament import Tournament
from t_admin_menu import T_Admin

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = discord.Bot(intents=intents)

@bot.event
async def on_ready():
    print(f"{bot.user} is online -- v1.2")

##########################
# SLASH COMMANDS SECTION #
##########################

# Slash command to CREATE a new tournament
@bot.slash_command(name="create", description="Create a new tournament")
async def create(
    ctx: discord.ApplicationContext,
    registration_channel = discord.Option(
        discord.abc.GuildChannel, # Allow any channel type
        description="The channel where player registration for the tournament will take place",
        channel_types=[discord.ChannelType.text, discord.ChannelType.news]
        ),
    player_cap: int = discord.Option(
        int, # Only allows integers
        description="The maximum number of players that can register for the tournament (before reserves are added)"
        )):
    
    # Only allow users with this permission to admin tournaments
    user: discord.Member = ctx.guild.get_member(ctx.user.id)
    organizer_role: discord.Role = discord.utils.get(ctx.guild.roles, name="BGTB Organizer")
    if organizer_role not in user.roles and not user.guild_permissions.administrator:
        await ctx.respond("Failed. You must have the 'BGTB Organizer' role to perform this action.", ephemeral=True)
        return   

    # Set permissions for bot to manage the registration channel
    overwrites = registration_channel.overwrites_for(ctx.guild.me)
    overwrites.send_messages = True
    overwrites.read_messages = True
    overwrites.read_message_history = True
    overwrites.manage_messages = True
    overwrites.view_channel = True
    await registration_channel.set_permissions(ctx.guild.me, overwrite=overwrites)

    # Display the Modal requesting input from the user
    modal = Create_Tournament(reg_channel=registration_channel, title="Create Tournament", player_cap=player_cap)
    await ctx.send_modal(modal)

# Slash command to display a LIST OF ALL ACTIVE TOURNAMENTS
@bot.slash_command(name="tournaments_list", description="Show a list of all active tournaments and their ID numbers")
async def tournament_list(ctx: discord.ApplicationContext):
    tournaments = Tournament.load_all_tournaments()
    list = discord.Embed(title="List of Tournaments", color=discord.Color.blue())

    # Loop to add each tournament from the tournaments list
    for t in tournaments:
        list.add_field(name=f"({t.id}) - {t.name}", value=f"Game: {t.game}", inline=False)
    await ctx.respond(embed=list)

# Slash command to ADMIN a tournament
@bot.slash_command(name = "admin", description = "Administrate a Tournament by entering its ID number.")
async def admin(ctx: discord.ApplicationContext, id:int = discord.Option(description="Find this ID number by using the tournaments_list command")):
    # Find the tournament
    tournaments = Tournament.load_all_tournaments()
    tournament: Tournament = next((t for t in tournaments if t.id == int(id)), None) # Go through all tournaments and find the id entered.

    if not tournament:
        await ctx.respond("Tournament not found.", ephemeral=True)
        return
    
    # Only allow users with this permission to admin tournaments
    user: discord.Member = ctx.guild.get_member(ctx.user.id)
    admin_role: discord.Role = discord.utils.get(ctx.guild.roles, name=tournament.admin_role)
    if admin_role not in user.roles and not user.guild_permissions.administrator:
        await ctx.respond("Failed. Only Tournament Admins have permission to perform this action.", ephemeral=True)
        return   
        
    view = T_Admin(tournament)
    embed = view.get_embed()
    await ctx.respond("", view=view, embed=embed)

    admin_msg = await ctx.interaction.original_response()  
    tournament.admin_msg_id = admin_msg.id
    tournament.save()

# Slash command to set registration channel
@bot.slash_command(name="set_reg_channel", description="Set the registration channel for your tournament")
async def set_reg_channel(ctx: discord.ApplicationContext, tournament_id: int, registration_channel = discord.Option(
        discord.abc.GuildChannel, # Allow any channel type
        description="The channel where player registration for the tournament will take place",
        channel_types=[discord.ChannelType.text, discord.ChannelType.news]
        )):
    # Get tournament
    tournaments = Tournament.load_all_tournaments()
    tournament: Tournament = next((t for t in tournaments if t.id == int(tournament_id)), None)
    if not tournament:
        await ctx.respond("Tournament not found.", ephemeral=True)
        return

    # Only allow users with this permission to admin tournaments
    user: discord.Member = ctx.guild.get_member(ctx.user.id)
    admin_role: discord.Role = discord.utils.get(ctx.guild.roles, name=tournament.admin_role)
    if admin_role not in user.roles and not user.guild_permissions.administrator:
        await ctx.respond(f"Failed. You must have the '{tournament.admin_role}' role to perform this action.", ephemeral=True)
        return

    # Set permissions for bot to manage the registration channel
    overwrites = registration_channel.overwrites_for(ctx.guild.me)
    overwrites.send_messages = True
    overwrites.read_messages = True
    overwrites.read_message_history = True
    overwrites.manage_messages = True
    overwrites.view_channel = True
    await registration_channel.set_permissions(ctx.guild.me, overwrite=overwrites)

    # Set the registration channel and send confirmation
    tournament.set_reg_channel(registration_channel.id)
    tournament.save()
    await ctx.respond(f"Registration channel set to {registration_channel.mention}", ephemeral=True)

# Create tournaments-lounge channel when joining the server
@bot.event
async def on_guild_join(guild: discord.Guild):
    # Check if the bot has permissions to create channels
    if guild.me.guild_permissions.manage_channels:
        # Create tournaments category if it doesn't exist
        tournaments_category_name = "TOURNAMENTS"
        tournaments_category = discord.utils.get(guild.categories, name=tournaments_category_name)
        if not tournaments_category:
            tournaments_category = await guild.create_category(tournaments_category_name)
        # Create the main tournament admin channel
        tournaments_lounge_name = "🏆tournaments-lounge"
        tournaments_lounge = discord.utils.get(guild.text_channels, name=tournaments_lounge_name)
        if tournaments_lounge: # If channel already exists, edit it and add "use application commands" permission
            overwrites = tournaments_lounge.overwrites_for(guild.default_role)
            overwrites.use_application_commands = True
            await tournaments_lounge.set_permissions(guild.default_role, overwrite=overwrites)
        else: # If not, create it
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(use_application_commands=True)
            }
            await guild.create_text_channel(name=tournaments_lounge_name,
                                            category=tournaments_category,
                                            overwrites=overwrites)                                           
    else:
        print(f"Bot doesn't have permissions to create channels in {guild.name}.")
    
    # Create 'BGTB Organizer' role. Necessary in order to create tournaments
    await guild.create_role(name="BGTB Organizer", permissions=discord.Permissions(use_application_commands=True))
    print(f"Created role 'BGTB Organizer' in the '{guild.name}' server.")

def main():
    # Fetch the environment status from the env file. Either "dev" or "live"
    ENVIRONMENT = os.getenv("ENVIRONMENT")  
    TOKEN = os.getenv("DEV_TOKEN") if ENVIRONMENT == "dev" else os.getenv("LIVE_TOKEN") # 
    bot.run(TOKEN)

if __name__ == '__main__':
    main()