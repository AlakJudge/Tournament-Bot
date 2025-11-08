import discord
import os
from t_management import Create_Tournament
from tournament import Tournament
from t_admin_menu import T_Admin
from t_persistant_views import restore_all_views
from t_running import Start_Match_View
from t_registration import register_player_to_tournament
from t_utils import *
import t_debug

if os.getenv("GITHUB_ACTIONS") != "true":
    from dotenv import load_dotenv
    load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = discord.Bot(intents=intents)
version = "v2.0"

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

# Slash command to CREATE a new tournament
@bot.slash_command(name="create", description="Create a new tournament")
async def create(
    ctx: discord.ApplicationContext,
    registration_channel = discord.Option(
        discord.TextChannel,  # Only allow text channels
        description="The channel where player registration for the tournament will take place",
        channel_types=[discord.ChannelType.text, discord.ChannelType.news]
        ),
    player_cap = discord.Option(
        int, # Only allows integers
        description="The maximum number of players that can register for the tournament (before reserves are added)"
        ),
    embed_image = discord.Option(
        str,
        description="The URL of the tournament embed image",
        required=False
        )
    ):
    
    # Only allow users with this permission to admin tournaments
    user: discord.Member = ctx.guild.get_member(ctx.user.id)
    organizer_role: discord.Role | None = discord.utils.get(ctx.guild.roles, name="BGTB Organizer")
    if organizer_role not in user.roles and not user.guild_permissions.administrator:
        await ctx.respond("Failed. You must have the 'BGTB Organizer' role to perform this action.", ephemeral=True)
        return   

    # Set permissions for bot to manage the registration channel
    overwrites = discord.PermissionOverwrite()
    overwrites.send_messages = True
    overwrites.read_messages = True
    overwrites.read_message_history = True
    overwrites.manage_messages = True
    overwrites.view_channel = True
    try:
        await registration_channel.set_permissions(ctx.guild.me, overwrite=overwrites)
    except discord.Forbidden as e:
        print(f"Failed to set permissions: {e}")
        await ctx.respond("Failed. The bot does not have permission to set channel permissions. Make sure the bot has the 'View Channel' and 'Manage Channels' permissions", ephemeral=True)
        return

    # Validate the image URL
    if embed_image:
        if not await validate_image_url(embed_image):
            await ctx.respond("Invalid image URL. Please provide a valid image URL starting with 'http://' or 'https://'", ephemeral=True)
            return

    # Display the Modal requesting input from the user
    modal = Create_Tournament(reg_channel=registration_channel, title="Create Tournament", player_cap=player_cap, image=embed_image)
    await ctx.send_modal(modal)

# Slash command to display a LIST OF ALL ACTIVE TOURNAMENTS
@bot.slash_command(name="tournaments_list", description="Show a list of all active tournaments and their ID numbers")
async def tournament_list(ctx: discord.ApplicationContext):
    tournaments = Tournament.load_all_tournaments(ctx.guild.id)
    list = discord.Embed(title="List of Tournaments", color=discord.Color.blue())

    # Loop to add each tournament from the tournaments list
    for t in tournaments:
        list.add_field(name=f"({t.id}) - {t.name}", value=f"Game: {t.game}", inline=False)
    
    await ctx.respond(embed=list)


# Slash command to ADMIN a tournament
@bot.slash_command(name = "admin", description = "Administrate a Tournament by entering its ID number.")
async def admin(
    ctx: discord.ApplicationContext, 
    id = discord.Option(description="Find this ID number by using the tournaments_list command")
    ):
    await ctx.defer() 
    # Find the tournament
    tournaments = Tournament.load_all_tournaments(ctx.guild.id)
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
    tournament.admin_msg_channel_id = admin_msg.channel.id
    tournament.save()

# Slash command to set registration channel
@bot.slash_command(name="set_reg_channel", description="Set the registration channel for your tournament")
async def set_reg_channel(ctx: discord.ApplicationContext, tournament_id: int, registration_channel = discord.Option(
        discord.abc.GuildChannel, # Allow any channel type
        description="The channel where player registration for the tournament will take place",
        channel_types=[discord.ChannelType.text, discord.ChannelType.news]
        )):
    # Get tournament
    tournaments = Tournament.load_all_tournaments(ctx.guild.id) # 
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

# Slash command to reload initial thread message/view
@bot.slash_command(name="reload_thread_buttons", description="Reload the initial thread message and buttons", )
async def reload_thread_buttons(ctx: discord.ApplicationContext):    
    if not isinstance(ctx.channel, discord.Thread):
        await ctx.respond("This command can only be used in a tournament thread.", ephemeral=True)
        return
    
    # Get the channel ID of the parent channel of the current thread, then get the tournament
    parent_channel_id = ctx.channel.parent_id 
    tournaments = Tournament.load_all_tournaments(ctx.guild.id)
    tournament: Tournament = next((t for t in tournaments if t.tournament_channel_id == parent_channel_id), None) 
    if not tournament:
        await ctx.respond("Tournament not found.", ephemeral=True)
        return

    # Only allow users with this permission to admin tournaments
    user: discord.Member = ctx.guild.get_member(ctx.user.id)
    admin_role: discord.Role = discord.utils.get(ctx.guild.roles, name=tournament.admin_role)
    if admin_role not in user.roles and not user.guild_permissions.administrator:
        await ctx.respond(f"Failed. You must have the '{tournament.admin_role}' role to perform this action.", ephemeral=True)
        return

    # Get the match id based on the current thread ID
    match_id = next((match["id"] for match in tournament.matches if match.get("thread_id") == ctx.channel.id), None)
    if not match_id:
        await ctx.respond("Match not found for this thread.", ephemeral=True)
        return
   
    # Reload the initial thread admin buttons
    view = Start_Match_View(match_id, tournament)
    await ctx.respond(content="## 🛠 Match Admin Buttons", view=view)

# Register a player to a tournament manually
@bot.slash_command(name="register_player", description="Register a player to a tournament manually")
async def register_player(
        ctx: discord.ApplicationContext,
        tournament_id: int,
        player: discord.Member = discord.Option(discord.Member, description="The player to register to the tournament")
        ):
    # Get tournament
    tournaments = Tournament.load_all_tournaments(ctx.guild.id)
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

    # Register the player
    await register_player_to_tournament(tournament, player, ctx.interaction)


@bot.slash_command(name="help", description="Get help with the bot")
async def help(ctx: discord.ApplicationContext):
    help_embed = discord.Embed(title="Tournament Bot Help", color=discord.Color.blue())
    help_embed.add_field( 
        name="Description",
        value="This bot is designed to help you create and manage tournaments in your Discord server without relying on slash commands for almost anything. "
        "You can run and manage tournaments smoothly with just menus and buttons.\n\n"
        "*Use the buttons below to navigate the help menu and learn about each section of the bot.*\n**-----**\n", 
        inline=False
        )
    help_embed.add_field(
        name="🔹 Commands",
        value="Learn about the few slash commands available.", 
        inline=False
    )
    help_embed.add_field(
        name="🔹 Tournament Setup",
        value="Learn about how you can set up a tournament.", 
        inline=False
    )
    help_embed.add_field(
        name="🔹 Admin Menu",
        value="Learn all about the admin menu and how to use it.", 
        inline=False
    )
    help_embed.add_field(
        name="🔹 Running the Tournament",
        value="Learn how to run the tournament and manage players.", 
        inline=False
    )
    help_embed.add_field(
        name="🔸 Support Server",
        value="Join our support server for help and updates: [Support Server](https://discord.gg/4vSG9VYCyj)\n"
        "**---**",
        inline=False
    )
    help_embed.set_footer(text=f"Tournament Bot - {version}")

    # Create a view to hold the buttons
    view = HelpView(help_embed)

    # Show embed and buttons
    await ctx.respond(embed=help_embed, view=view, ephemeral=True)

class HelpView(discord.ui.View):
    def __init__(self, help_embed: discord.Embed):
        super().__init__(timeout=None)
        self.help_embed = help_embed
        self.home_embed = self.help_embed.copy()
    
    @discord.ui.button(label="🏠", style=discord.ButtonStyle.green, custom_id="home", disabled=True)
    async def home_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        # Update the existing embed with new content
        self.help_embed.clear_fields()

        # Change the color of the current button
        self.manage_help_buttons(button)
        
        # Update the message
        await interaction.response.edit_message(embed=self.home_embed, view=self)

    @discord.ui.button(label="Commands", style=discord.ButtonStyle.blurple, custom_id="commands")
    async def commands_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        # Update the existing embed with new content
        self.help_embed.clear_fields()
        self.help_embed.title = "Commands Help"
        self.help_embed.description = (
            "**Available commands:**\n"
            "`/create` - Create a new tournament.\n"
            "You must set the registration channel and the player capacity.\n"
            "It also sets the player as the owner and creates both the **Admin** and **Participant** roles.\n\n"
            "`/tournaments_list` - Show a list of all active tournaments and their IDs.\n\n"
            "`/admin` - Open the ADMIN MENU. Needs the tournament ID.\n\n"
            "`/register_player` - Register a player to a tournament manually.\n\n"
            "`/set_reg_channel` - Change the registration channel after a tournament has been created.\n\n"
            "`/reload_thread_buttons` - Reload the admin buttons for that specific Match Thread.\n\n"
            "`/help` - Get help with the bot.\n"
            "**-----**"
        )
        # Change button colour, disable it and reenable the other buttons
        self.manage_help_buttons(button)

        await interaction.response.edit_message(embed=self.help_embed, view=self)

    @discord.ui.button(label="Tournament Setup", style=discord.ButtonStyle.blurple, custom_id="setup")
    async def setup_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.help_embed.clear_fields()
        self.help_embed.title = "Tournament Setup Help"
        self.help_embed.description = ("**-----**")
        self.help_embed.add_field(
            name="🟩 Setting up the Tournament\n\n",
            value=(
                "1. Use `/create` to create a new tournament."
                "Enter the channel where you'd like the registration message to be sent and the maximum number of players in the tournament.\n"
                "2. Note the ID of the tournament from the confirmation message. But you can always find it again using `/tournaments_list`.\n"
                "3. Admin and Participant roles will be created automatically.\n"
                "4. Use `/admin` + the `id` of the tournament to open the admin menu.\n\n"

                "-- If necessary, change the registration channel at any time by using `/set_reg_channel`.\n\n"
                "**-----**"
            ),
            inline=False
        )
        self.help_embed.add_field(
            name="🟨 Restarting the tournament:\n\n",
            value=(
                "If you run into issues or simply want to restart the tournament:\n"
                "1. Use `/admin` + the `id` of the tournament to open the admin menu.\n"
                "2. Click on the `🔄Restart Tournament` button.\n"
                "3. Wait a few seconds.\n"
                "3. The tournament will be reset, only keeping the registered players, and you can start over.\n\n"
                "**-----**"
            ),
            inline=False
        )
        self.help_embed.add_field(
            name="🟥 Deleting the tournament:\n\n",
            value=(
                "If you want to delete the tournament:\n"
                "1. Use `/admin` + the `id` of the tournament to open the admin menu.\n"
                "2. Click on the `❌Delete Tournament` button.\n"
                "3. The tournament will be deleted and all data will be lost. Including the roles, channels and messages.\n\n"
                "**-----**"
            ),
            inline=False
        )
        # Change button colour, disable it and reenable the other buttons
        self.manage_help_buttons(button)
        
        await interaction.response.edit_message(embed=self.help_embed, view=self)

    @discord.ui.button(label="Admin Menu", style=discord.ButtonStyle.blurple, custom_id="admin_menu")
    async def admin_menu_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.help_embed.clear_fields()
        self.help_embed.title = "Admin Menu Help"
        self.help_embed.description = ("**-----**")
        self.help_embed.add_field(
            name="📖 Open Reg",
            value=(
                "Create an embed with tournament information in the registration channel and allow players to register.\n"
                "You will also be able to attach a message to go with the registration embed and buttons.\n\n"
                "**-----**"
            ),
            inline=False
        )
        self.help_embed.add_field(
            name="🛑 Close Reg",
            value=(
                "Close the registration by disabling the registration buttons.\n"
                "**-----**"
            ),
            inline=False
        )
        self.help_embed.add_field(
            name="🟢 START",
            value=(
                "Close Registration and Start the tournament. This will allow you to set 2 parameters:\n"
                "- Maximum number of players per game in the first round.\n"
                "- Minimum number of games in the first round.\n"
                "These parameters will give you control over how many players will be in each game and how many games will be played in the first round.\n\n"
                "*E.g., if you have 10 players and set the maximum number of players per game to 3, the bot will create 4 games with 3, 3, 2 and 2 players.*\n"
                "*However, if you set the minimum number of games to 5, the bot will create 5 games with 2 players in each one.*\n\n"
                "The bot will then create private match threads in the tournament channel, add the respective players, and send a message with the match information.\n"
                "**-----**"
            ),
            inline=False
        )
        self.help_embed.add_field(
            name="✅ Activate Check-in",
            value=(
                "Activate the check-in system for the tournament. This will allow players to check-in before the tournament starts.\n"
                "Only Checked-in players will be taken into account when setting the brackets when you start the tournament.\n\n"
                "You will be able to set the following parameters:\n"
                "- Check-in start time.\n"
                "   - Set the amount of minutes/hours prior the 'tournament start time' which you'd like the check-in to start.\n"
                "- Check-in duration.\n"
                "  - How long players have to check-in.\n"
                "- Check-in end.\n"
                "  - Set the amount of minutes/hours prior the 'tournament start time' which you'd like the check-in to end.\n\n"
                "*Players who fail to check-in will be moved to the reserves list once the check-in ends.*\n\n"
                "If a player checks in after the Check-in end time, they will be added to a 'late check-in' list, which will have priority when you add a reserve to a match.\n"
                "**-----**"
            ),
            inline=False
        )
        self.help_embed.add_field(
            name="📄 Edit Info",
            value=(
                "Edit tournament information. This will allow you to modify the following:\n"
                "- Tournament name\n"
                "- Game name\n"
                "- Date\n"
                "- Time\n"
                "- Prize\n"
                "- Player Capacity\n"
                "- Tournament embed image\n"
                "**-----**"
            ),
            inline=False
        )
        self.help_embed.add_field(
            name="📝 Edit Match Intro",
            value=(
                "Edit the message that will be sent to the players in the match thread.\n"
                "This message will be sent when the tournament starts and when a new round starts.\n"
                "**-----**"
            ),
            inline=False
        )
        self.help_embed.add_field(
            name="👥 Player List",
            value=(
                "Show a list of all players registered for the tournament.\n"
                "**-----**"
            ),
            inline=False
        )
        self.help_embed.add_field(
            name="⏰ Notifications",
            value=(
                "Activate notifications that will be sent 24 hours and 2 hours before the tournament begins.\n"
                "*This will be editable in the future.*\n"
                "**-----**"
            ),
            inline=False
        )
        self.help_embed.add_field(
            name="➕ Add New Admin",
            value=(
                "Add a new admin to the tournament. This will give the user the Tournament Admin role.\n"
                "*A new admin has the same permissions as the owner, but cannot add or remove other Admins.*\n"
                "**-----**"
            ),
            inline=False
        )
        self.help_embed.add_field(
            name="➖ Remove Admin",
            value=(
                "Remove existing Admins from the tournament. This will remove the Admin role from the user.\n"
                "*Only the owner can do this.*\n"
                "**-----**"
            ),
            inline=False
        )
        self.help_embed.add_field(
            name="🔄 Restart",
            value=(
                "Resets the tournament and allows you to start over.\n"
                "*This will keep the registered players and roles, but all other data will be lost, including the tournament channels.*\n"
                "**-----**"
            ),
            inline=False
        )
        self.help_embed.add_field(
            name="🗃 Archive",
            value=(
                "Archive the tournament. This will keep all data related to the tournament, but mark it as inactive.\n"
                "*The specific channels will not be deleted automatically, but everything else will no longer be accessible.*\n"
                "**-----**"
            ),
            inline=False
        )
        self.help_embed.add_field(
            name="❌ Delete",
            value=(
                "Delete the tournament. This will delete all data related to the tournament.\n"
                "*This includes the player registry, roles, channels and messages.*\n"
                "**-----**"
            ),
            inline=False
        )
        # Change button colour, disable it and reenable the other buttons
        self.manage_help_buttons(button)

        await interaction.response.edit_message(embed= self.help_embed, view=self)

    @discord.ui.button(label="Running the Tournament", style=discord.ButtonStyle.blurple, custom_id="running")
    async def running_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.help_embed.clear_fields()
        self.help_embed.title = "Running the Tournament Help"
        self.help_embed.description = ("**----**")
        self.help_embed.add_field(
            name="🔹 IN THE TOURNAMENT CHANNEL 🔹",
            value=(
                "**-----**"
            ),
            inline=False
        )
        self.help_embed.add_field(
            name="🏁 Go to Next Round",
            value=(
                " Proceed to next round with all the current match winners.\n"
                "**-----**"
            ),
            inline=False
        )
        self.help_embed.add_field(
            name="➕ Add Player to Match",
            value=(
                "Manually add a player to the match. This uses the player's **Username** and not Display Name.\n"
                "You'll need the Match ID. It's formatted like this: `R(round number)-G(game number)`.\n"
                "E.g., `R1-G2` for Game 2 of Round 1.\n"
                "**-----**"
            ),
            inline=False
        )
        self.help_embed.add_field(
            name="🏅 Set Match Winner",
            value=(
                "Manually set a winner of a specific match. This will use the player's **Username** and not Display Name.\n"
                "You'll need the Match ID. It's formatted like this: `R(round number)-G(game number)`.\n"
                "E.g., `R1-G2` for Game 2 of Round 1.\n"
                "**-----**"
            ),
            inline=False
        )
        self.help_embed.add_field(
            name="📣 Announcement",
            value=(
                "Send a message to all active game threads.\n"
                "**-----**"
            ),
            inline=False
        )
        self.help_embed.add_field(
            name="✅ Ready Check All Games",
            value=(
                "Send a ready check message to all active game threads.\n"
                "Players will have 5 minutes to confirm they're ready to start before getting tagged.\n"
                "**-----**"
            ),
            inline=False
        )
        self.help_embed.add_field(
            name="⏳ Show Pending Matches",
            value=(
                "Show a list of all matches without a winner and the players in each one of them.\n"
                "**-----**"
            ),
            inline=False
        )
        self.help_embed.add_field(
            name="🔸 IN THE GAME THREADS 🔸",
            value=(
                "**-----**"
            ),
            inline=False
        )
        self.help_embed.add_field(
            name="🎖 Set Winner",
            value=(
                "This will allow Admins to select the winner(s) of the match from a drop-down menu.\n"
                "**-----**"
            ),
            inline=False
        )
        self.help_embed.add_field(
            name="➕ Add Reserve",
            value=(
                "Add the first player from the reserve pool to this match.\n\n"
                "If Check-in mode is enabled, players in the 'late check-in' list will have priority above other reserves."
                "**-----**"
            ),
            inline=False
        )
        self.help_embed.add_field(
            name="⏩ Transfer Player",
            value=(
                "Transfer a player from one match to another.\n"
                "This will open a drop-down menu with all the players in this match.\n"
                "You'll need the destination Match ID. It's formatted like this: `R(round number)-G(game number)`.\n"
                "E.g., `R1-G2` for Game 2 of Round 1.\n"
                "**-----**"
            ),
            inline=False
        )
        self.help_embed.add_field(
            name="❌ Remove Player",
            value=(
                "Remove a player from this match.\n"
                "This will open a drop-down menu with all the players in this match.\n"
                "**-----**"
            ),
            inline=False
        )
        self.help_embed.add_field(
            name="✅ Ready Check",
            value=(
                "Send a ready check message to all players in this match.\n"
                "Players will have 5 minutes to confirm they're ready to start before getting tagged.\n"
                "**-----**"
            ),
            inline=False
        )
        # Change button colour, disable it and reenable the other buttons
        self.manage_help_buttons(button)

        await interaction.response.edit_message(embed=self.help_embed, view=self)

    # Function to reenable all buttons
    def manage_help_buttons(self, current_button: discord.ui.Button):
        for button in self.children:
            button.style = discord.ButtonStyle.blurple
            button.disabled = False
        current_button.style = discord.ButtonStyle.green
        current_button.disabled = True

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

@bot.slash_command(name="debug_mode", description="Toggle debug mode for testing", guild_ids=[1286841607576092763]) 
async def debug_mode(ctx: discord.ApplicationContext, enabled: bool):
    # Only allow users with this permission to admin tournaments
    user: discord.Member = ctx.guild.get_member(ctx.user.id)
    admin_role: discord.Role = discord.utils.get(ctx.guild.roles, name="BGTB Organizer")
    if admin_role not in user.roles and not user.guild_permissions.administrator:
        await ctx.respond("Failed. Only Tournament Admins have permission to perform this action.", ephemeral=True)
        return   
    
    t_debug.set_debug_mode(enabled)
    status = "enabled" if enabled else "disabled"
    await ctx.respond(f"Debug mode {status}.", ephemeral=True)

@bot.slash_command(name="add_dummies", description="Add dummy players to tournament (Debug mode only)", guild_ids=[1286841607576092763])
async def add_dummies(ctx: discord.ApplicationContext, tournament_id: int, count: int = 50):
    if not t_debug.TOURNAMENT_DEBUG_MODE:
        await ctx.respond("Debug mode not enabled.", ephemeral=True)
        return
    
    tournament = Tournament.load_tournament_by_id(ctx.guild.id, tournament_id)
    if not tournament:
        await ctx.respond("Tournament not found.", ephemeral=True)
        return
    
    success, message = await t_debug.add_dummy_players(tournament, count)
    await ctx.respond(message, ephemeral=True)

@bot.slash_command(name="clean_dummies", description="Remove all dummy players (Debug mode only)", guild_ids=[1286841607576092763])
async def clean_dummies(ctx: discord.ApplicationContext, tournament_id: int):
    tournament = Tournament.load_tournament_by_id(ctx.guild.id, tournament_id)
    if not tournament:
        await ctx.respond("Tournament not found.", ephemeral=True)
        return
    
    removed = await t_debug.clean_dummy_players(tournament)
    await ctx.respond(f"Removed {removed} dummy players.", ephemeral=True)


def main():
    # Fetch the environment status from the env file. Either "dev" or "live"
    ENVIRONMENT = os.getenv("ENVIRONMENT")  
    TOKEN = os.getenv("DEV_TOKEN") if ENVIRONMENT == "dev" else os.getenv("LIVE_TOKEN")
    bot.run(TOKEN)

if __name__ == '__main__':
    main()
