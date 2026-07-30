import discord
import os
from tournament import Tournament
from views.persistent_views import restore_all_views
from utils.helpers import DummyInteraction, schedule_custom_notifications
from commands import register_commands

if os.getenv("GITHUB_ACTIONS") != "true":
    from dotenv import load_dotenv
    load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = discord.Bot(intents=intents)
version = "v2.2"

register_commands(bot, version)

@bot.event
async def on_ready():
    print(f"{bot.user} is online - {version}")
    # Restore all views when the bot is ready
    try:
        await restore_all_views(bot)
    except Exception as e:
        print(f"Failed to restore views: {e}")

    # Iterate through each guild the bot is in and reschedule existing notifications for tournaments
    for guild in bot.guilds:
        dummy_interaction = DummyInteraction(guild)
        tournaments = Tournament.load_all_tournaments(guild.id)
        for tournament in tournaments:
            if hasattr(tournament, "notification_intervals"):
                await schedule_custom_notifications(
                    tournament, dummy_interaction, 
                    [i["seconds"] for i in tournament.notification_intervals], 
                    startup=True
                    )
    
    # Force sync slash commands
    await bot.sync_commands()
    

##########################
# SLASH COMMANDS SECTION #
##########################

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
    TOKEN = os.getenv("DEV_TOKEN") if ENVIRONMENT == "dev" else os.getenv("LIVE_TOKEN")
    bot.run(TOKEN)

if __name__ == '__main__':
    main()
