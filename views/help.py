import discord

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
            "`/reload_tournament_menu` - Reload the tournament admin menu. This needs to be run in the tournament channel.\n\n"
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
                "You can also set an image for the tournament embed, but it's not required.\n"
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
                "2. Click on the `🔄Restart All` button.\n"
                "3. Wait a few seconds.\n"
                "4. The tournament will be reset, only keeping the registered players, and you can start over.\n\n"
                "You can also reset just the current game threads by clicking the `🔄Restart Games` button. This will keep the tournament setup and players, but reset the current game threads and matches.\n\n"
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
            name="👥 Players Info",
            value=(
                "This gives you 3 options.\n"
                "1. Registered (and reserves): See the list of registered players and reserves.\n"
                "2. Check-ins: See the list of players who checked in for the tournament. Only these players will be added to the matches when you start the tournament.\n"
                "3. Late Check-ins: See the list of players who checked in late. These players will have priority when adding reserves to matches.\n"
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
            name="🔄 Restart Games",
            value=(
                "Restart all current game threads. This will delete all current threads and the existing matches.\n"
                "*This will keep the tournament channels, registered players and check-ins, but reset the tournament to round 1.*\n"
                "**-----**"
            ),
            inline=False
        )
        self.help_embed.add_field(
            name="🔄 Restart all",
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
            name="➕ Add New Match",
            value=(
                "Manually add a new match to the current round. This will create a new empty match thread.\n"
                "You'll need to manually add players to this match.\n"
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
