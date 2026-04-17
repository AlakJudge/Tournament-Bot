from datetime import datetime
from t_registration import Registration, close_registration
from tournament import Tournament
from t_management import *
from t_registration import Reg_Msg_Modal
from t_utils import *
from t_running import run_tournament
from t_checkin import *
import discord

class T_Admin(discord.ui.View):
    def __init__(self, tournament:Tournament):
        super().__init__(timeout=None)
        self.tournament = tournament
    
    def get_embed(self):
        return create_tournament_embed(self.tournament)
    
    # Open Registration button
    @discord.ui.button(label="📖 Open Reg", style = discord.ButtonStyle.green, custom_id="open_reg_button")
    async def open_reg(self, button: discord.ui.Button, interaction: discord.Interaction):
        # Check if the user has the admin role or is a server admin
        if not await check_tournament_admin(interaction, self.tournament):
            return
        # Update tournament data
        self.tournament: Tournament = Tournament.load_tournament_by_id(interaction.guild.id, self.tournament.id)

        registration_view = Registration(self.tournament)
        reg_channel = await interaction.guild.fetch_channel(self.tournament.reg_channel)
        
        if not self.tournament.reg_msg_id:     
            modal = Reg_Msg_Modal(self.tournament)
            await interaction.response.send_modal(modal)
            await modal.wait()

            # Create tournament chat channel
            if not self.tournament.tournament_channel_id:
                category = discord.utils.get(interaction.guild.categories, name="TOURNAMENTS")
                tournament_channel:discord.TextChannel = await interaction.guild.create_text_channel("🗨chat-"+self.tournament.name, category=category)
                self.tournament.tournament_channel_id = tournament_channel.id

            if not self.tournament.participants_channel_id:
                # Create or fetch the admin role for the tournament
                admin_role = discord.utils.get(interaction.guild.roles, name=f"({self.tournament.id}) Tournament Admin")
                if not admin_role:
                    # Create the admin role if it doesn't exist
                    admin_role = await interaction.guild.create_role(
                        name=f"({self.tournament.id}) Tournament Admin",
                        color=discord.Color.blue(),
                        mentionable=True
                    )
                    # Give the role to the tournament owner
                    owner = interaction.guild.get_member(self.tournament.owner)
                    if owner:
                        await owner.add_roles(admin_role)

                # Create channel for participants logs and management, accessible only to tournament admins
                overwrites = {
                        interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),  # Deny access to @everyone
                        admin_role: discord.PermissionOverwrite(view_channel=True)  # Grant access to the admin
                }
                overwrites[interaction.guild.me] = discord.PermissionOverwrite(view_channel=True) # Grant access to bot
                category = discord.utils.get(interaction.guild.categories, name="TOURNAMENTS") # Fetch category
                participants_channel:discord.TextChannel = await interaction.guild.create_text_channel("👥participants-"+self.tournament.name, category=category, overwrites=overwrites)
                self.tournament.participants_channel_id = participants_channel.id
            
            self.tournament.edit_reg_status("Open")
            self.tournament.save()
            await update_tournament_embeds(self.tournament, interaction)
            
        else:
            # Return if Registration is already Open
            if self.tournament.reg_status == "Open":
                await interaction.response.send_message(f"Registration is already open.", ephemeral=True)
                return
            
            # Fetch message and embed if it already exists
            try:
                reg_msg = await reg_channel.fetch_message(self.tournament.reg_msg_id)
                reg_embed = reg_msg.embeds[0]
            except discord.NotFound:
                await interaction.response.send_message("Registration message not found.", ephemeral=True)
                return

            # Re-enable buttons
            for item in registration_view.children:
                if isinstance(item, discord.ui.Button):
                    item.disabled = False

            # Edit registration status
            self.tournament.edit_reg_status("Open")
            self.tournament.save()

            # Update the original message to re-enable buttons
            await reg_msg.edit(view=registration_view, embed=reg_embed)
            await interaction.response.send_message(f"Registration opened for '{self.tournament.name}'!", ephemeral=True)

            await update_tournament_embeds(self.tournament, interaction)       

    # Close Registration button
    @discord.ui.button(label="🛑 Close Reg", style = discord.ButtonStyle.red, custom_id="close_reg_button")
    async def close_reg(self, button: discord.ui.Button, interaction: discord.Interaction): 
        # Check if the user has the admin role or is a server admin
        if not await check_tournament_admin(interaction, self.tournament):
            return
        
        # Return if Registration is already Open
        if self.tournament.reg_status == "Closed":
            await interaction.response.send_message(f"Registration is already closed.", ephemeral=True)
            return
        
        await close_registration(interaction=interaction, tournament=self.tournament)

    # Start Tournament button
    @discord.ui.button(label="🟢 Start", style = discord.ButtonStyle.green, custom_id="start_tournament_button")
    async def t_run(self, button: discord.ui.Button, interaction: discord.Interaction):  
        if not await check_tournament_admin(interaction, self.tournament):
            return 
        await run_tournament(self.tournament, interaction)    

    # Start Tournament button
    @discord.ui.button(label="✅ Activate Check-in", style = discord.ButtonStyle.green, custom_id="checkin_button")
    async def check_in(self, button: discord.ui.Button, interaction: discord.Interaction):  
        if not await check_tournament_admin(interaction, self.tournament):
            return 
        
        # Update tournament data
        self.tournament: Tournament = Tournament.load_tournament_by_id(interaction.guild.id, self.tournament.id)
        
        if not self.tournament.get_checkin_status():
            # If check-in is active, change button to deactivate
            checkin_modal = CheckinModal(self.tournament)
            await interaction.response.send_modal(checkin_modal)
            await checkin_modal.wait()
           
            self.tournament = Tournament.load_tournament_by_id(interaction.guild.id, self.tournament.id)
            if self.tournament.get_checkin_status():  # Only update button if check-in was actually activated
                button.label = "⛔ Deactivate Check-in"
                button.style = discord.ButtonStyle.red
        else:
            if await deactivate_checkin(self.tournament, interaction):
                button.label = "✅ Activate Check-in"
                button.style = discord.ButtonStyle.green

        embed = T_Admin.get_embed(self)        
        await interaction.message.edit(embed=embed, view=self)


    # Edit Tournament button
    @discord.ui.button(label="📄 Edit Info", style = discord.ButtonStyle.blurple, custom_id="edit_info_button")
    async def edit_tournament(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not await check_tournament_admin(interaction, self.tournament):
            return
        view = Edit_Options_View(self.tournament)
        await interaction.response.send_message("", view=view, ephemeral=True)

    # Add new thread message
    @discord.ui.button(label="📝 Edit Match Intro", style = discord.ButtonStyle.blurple, custom_id="edit_match_intro_button")
    async def add_thread_msg(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not await check_tournament_admin(interaction, self.tournament):
            return
        
        # Send modal to get new thread message
        modal = Thread_Msg_Modal(self.tournament)
        await interaction.response.send_modal(modal)

    
    # Button to dropdown with players, checked in players, and late check in players lists
    @discord.ui.button(label="👥 Players Info", style = discord.ButtonStyle.blurple, custom_id="players_info_button")
    async def players_info_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not await check_tournament_admin(interaction, self.tournament):
            return
        
        # Update tournament data
        self.tournament: Tournament = Tournament.load_tournament_by_id(interaction.guild.id, self.tournament.id)

        view = Players_Info_View(self.tournament)
        await interaction.response.send_message("Select the list you want to see:", view=view, ephemeral=True)

    # Schedule Notifications button
    @discord.ui.button(label="⏰ Notifications", style = discord.ButtonStyle.blurple, custom_id="schedule_notifications_button")
    async def schedule_notifications(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not await check_tournament_admin(interaction, self.tournament):
            return

        # Check if tournament chat channel exists
        if not self.tournament.tournament_channel_id:
            await interaction.response.send_message("Tournament chat channel does not exist. Please Open Registration to create it before scheduling a notification.", ephemeral=True)
            return
        
        # Reload tournament data
        self.tournament: Tournament = Tournament.load_tournament_by_id(interaction.guild.id, self.tournament.id)
        active_notifications = []
        for interval in self.tournament.notification_intervals:
            active_notifications.append(parse_seconds_to_human_readable(interval["seconds"]))

        # Send a view with a select dropdown to choose the number of notifications, then a modal to set the times
        view = NotificationView(self.tournament)
        await interaction.response.send_message(
            "The following notifications will be deleted if you decide to set new ones:\n"
            f"**{', '.join(active_notifications) if active_notifications else '*No active notifications.*'}**\n\n"
            "How many notifications would you like to set?", view=view, ephemeral=True)
    
    # Add New Admin button
    @discord.ui.button(label="➕ Add New Admin", style = discord.ButtonStyle.blurple, custom_id="add_admin_button")
    async def add_admin(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not await check_tournament_admin(interaction, self.tournament):
            return

        # Send modal to get username
        modal = Add_Admin_Modal(self.tournament)
        await interaction.response.send_modal(modal)

    # Rmove Admin button
    @discord.ui.button(label="➖ Remove Admin", style = discord.ButtonStyle.blurple, custom_id="remove_admin_button")
    async def remove_admin(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not await check_tournament_admin(interaction, self.tournament):
            return

        # Check if the user is the owner of the tournament
        if interaction.user.id != self.tournament.owner:
            await interaction.response.send_message("Only the owner of the tournament can remove admins.", ephemeral=True)
            return

        # Send modal to get username
        modal = Remove_Admin_Modal(self.tournament)
        await interaction.response.send_modal(modal)

    # Restart the tournament - Delete everything but the registered players/reserves and base info data
    @discord.ui.button(label="🔄 Restart", style = discord.ButtonStyle.blurple, custom_id="restart_tournament_button")
    async def restart_tournament(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not await check_tournament_admin(interaction, self.tournament):
            return
        view = Restart_Confirmation_View(message=interaction.message, tournament = self.tournament)
        await interaction.response.send_message(f"Are you sure you want to **RESTART** '{self.tournament.name}'?", view=view)

    # Archive Tournament button
    @discord.ui.button(label="🗃 Archive", style = discord.ButtonStyle.red, custom_id="archive_tournament_button") 
    async def archive_tournament(self,  button: discord.ui.Button, interaction: discord.Interaction):
        if not await check_tournament_admin(interaction, self.tournament):
            return
        view = Archive_Confirmation_View(message=interaction.message, tournament = self.tournament)
        await interaction.response.send_message(
            f"Are you sure you want to **ARCHIVE** '{self.tournament.name}'?\n\n"
            "All messages and roles related to the tournament will be deleted, but the created channels will stay (so you may do what you wish with them).\n"
            "This action is **IRREVERSIBLE** and the tournament will no longer be visible in the list of active tournaments.",
            view=view)

    # Delete Tournament button
    @discord.ui.button(label="❌ Delete", style = discord.ButtonStyle.red, custom_id="delete_tournament_button") 
    async def delete_tournament(self,  button: discord.ui.Button, interaction: discord.Interaction):
        if not await check_tournament_admin(interaction, self.tournament):
            return
        view = Delete_Confirmation_View(message=interaction.message, tournament = self.tournament)
        await interaction.response.send_message(
            f"Are you sure you want to **DELETE** '{self.tournament.name}'?\n\n"
            "This action is **IRREVERSIBLE** and the tournament will no longer be visible in the list of active tournaments.",
            view=view)

class Add_Admin_Modal(discord.ui.Modal):
    def __init__(self, tournament: Tournament):
        super().__init__(title="Add Tournament Administrator")
        self.tournament = tournament
        self.add_item(discord.ui.InputText(label="Discord username of the new Tournament Admin"))

    async def callback(self, interaction):
        # Get the admin role for this tournament
        admin_role = discord.utils.get(interaction.guild.roles, name=f"({self.tournament.id}) Tournament Admin")
         # Get the user from the modal input
        username = self.children[0].value
        user = discord.utils.get(interaction.guild.members, name=username)

        if not user:
            await interaction.response.send_message(f"❌ Failed! User '{username}' not found in the server.", ephemeral=True)
            return
        
        # Check if the user is already an admin
        if admin_role in user.roles:
            await interaction.response.send_message(f"❌ Failed! User '{username}' is already an admin.", ephemeral=True)
            return
        else:
            # Add the admin role to the user
            await user.add_roles(admin_role)
            await interaction.response.send_message(f"✅ Success! User '{username}' has been added as an admin, with the '{admin_role}' role.", ephemeral=True)

class Remove_Admin_Modal(discord.ui.Modal):
    def __init__(self, tournament: Tournament):
        super().__init__(title="Remove Tournament Administrator")
        self.tournament = tournament
        self.add_item(discord.ui.InputText(label="Discord username of the Tournament Admin"))

    async def callback(self, interaction):
        # Get the admin role for this tournament
        admin_role = discord.utils.get(interaction.guild.roles, name=f"({self.tournament.id}) Tournament Admin")
         # Get the user from the modal input
        username = self.children[0].value
        user = discord.utils.get(interaction.guild.members, name=username)

        if user.id == self.tournament.owner:
            await interaction.response.send_message(f"❌ Failed! You cannot remove the owner of the tournament.", ephemeral=True)
            return

        if not user:
            await interaction.response.send_message(f"❌ Failed! User '{username}' not found in the server.", ephemeral=True)
            return
        
        # Check if the user is an admin
        if not admin_role in user.roles:
            await interaction.response.send_message(f"❌ Failed! User '{username}' is not an Admin for this tournament.", ephemeral=True)
            return
        else:
            # Remove the admin role from the user
            await user.remove_roles(admin_role)
            await interaction.response.send_message(f"✅ Success! User '{username}' has been removed as an Admin for this tournament.", ephemeral=True)

# Modal to get new thread message
class Thread_Msg_Modal(discord.ui.Modal):
    def __init__(self, tournament: Tournament):
        super().__init__(title="Write a new Game-Thread-Intro Message")
        self.tournament = tournament
        self.type = type
        self.add_item(discord.ui.InputText(
            label="New introduction message for Game Threads", 
            style=discord.InputTextStyle.paragraph, 
            placeholder="### Hello participants! Rest of message...",
            required=True))

    async def callback(self, interaction: discord.Interaction):
        self.tournament: Tournament = Tournament.load_tournament_by_id(interaction.guild.id, self.tournament.id) # Update tournament data
        msg_content = self.children[0].value
        self.tournament.edit_thread_msg(msg_content)
        self.tournament.save()

        await interaction.response.send_message(f"Game-Tread Message Updated!", ephemeral=True)

# Function to show list of registered users
async def show_registered_users(t: Tournament, interaction: discord.Interaction):
    # Get updated tournament data
    tournament: Tournament = Tournament.load_tournament_by_id(interaction.guild.id, t.id)
    # Get the list of registered players
    players = tournament.players
    reserves = tournament.reserves
    
    players_list = "\n".join(players)
    reserves_list = "\n".join(reserves)

    if not players_list:
        players_list = "*No players registered yet.*"
    if not reserves_list:
        reserves_list = "*No reserves registered yet.*"
    await interaction.response.send_message(f"### Registered Players ({len(players)}):\n"
                                            f"{players_list}\n"
                                            f"\n### Registered Reserves ({len(reserves)}):\n"
                                            f"{reserves_list}", ephemeral=True)

class Players_Info_View(discord.ui.View):
    def __init__(self, tournament: Tournament):
        super().__init__(timeout=None)
        self.tournament = tournament
    
    @discord.ui.select(placeholder="Click to select an option", custom_id="players_info_select", options=[
        discord.SelectOption(label="Registered (and reserves)", value="registered"),
        discord.SelectOption(label="Check-ins", value="checked_in"),
        discord.SelectOption(label="Late Check-ins", value="late_checkin")
    ])
    async def players_info(self, select: discord.ui.Select, interaction: discord.Interaction):
        if not await check_tournament_admin(interaction, self.tournament):
            return
        
        # Update tournament data
        self.tournament: Tournament = Tournament.load_tournament_by_id(interaction.guild.id, self.tournament.id)

        if select.values[0] == "registered":
            await show_registered_users(self.tournament, interaction)
        elif select.values[0] == "checked_in":
            checked_in_list = "\n".join(self.tournament.checked_in)
            if checked_in_list:
                await interaction.response.send_message(f"### ✅Checked-in Players ({len(self.tournament.checked_in)}):\n{checked_in_list}", ephemeral=True)
            else:
                await interaction.response.send_message("### No players have checked in yet.", ephemeral=True)
        elif select.values[0] == "late_checkin":
            late_checkin_list = "\n".join(self.tournament.late_checkin)
            if late_checkin_list:
                await interaction.response.send_message(f"### ⏰Late Check-in Players ({len(self.tournament.late_checkin)}):\n{late_checkin_list}", ephemeral=True)
            else:
                await interaction.response.send_message("### No players have done a late check-in.", ephemeral=True)

class Restart_Confirmation_View(discord.ui.View):
    def __init__(self, message, tournament:Tournament):
        super().__init__()
        self.message = message
        self.tournament = tournament

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.green)
    async def confirm(self, button: discord.ui.Button,interaction: discord.Interaction):
        # Delete yes/no buttons view
        await self.message.delete()
        await restart_tournament(self.tournament, interaction)

    @discord.ui.button(label="No", style=discord.ButtonStyle.red)
    async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
        # If "No" is clicked, cancel the action
        await self.message.delete()
        await interaction.response.send_message("Action cancelled.", ephemeral=True)

async def restart_tournament(tournament:Tournament, interaction: discord.Interaction):
    # Update tournament data
    tournament: Tournament = Tournament.load_tournament_by_id(interaction.guild.id, tournament.id)
    
    await interaction.response.defer()

    # Close registration if it is open
    if tournament.reg_status == "Open":
        await close_registration(interaction, tournament)
        await update_tournament_embeds(tournament, interaction)
        
    # Deactive check-in button if it is active
    if tournament.get_checkin_status():
        # Get admin msg
        admin_msg_channel = tournament.admin_msg_channel_id
        admin_msg = tournament.admin_msg_id
        admin_channel = await interaction.guild.fetch_channel(admin_msg_channel)
        try:
            message = await admin_channel.fetch_message(admin_msg)
            embed = message.embeds[0]
            view = T_Admin(tournament)
            
            for item in view.children:
                if isinstance(item, discord.ui.Button) and item.custom_id == "checkin_button":
                    item.label = "✅ Activate Check-in"
                    item.style = discord.ButtonStyle.green
            await message.edit(view=view, embed=embed)
        except discord.NotFound:
            pass

    # Delete all messages and channels related to the tournament, if they exist.
    # Except the admin message and reg channel ID
    if tournament.reg_msg_id:
        reg_channel = await interaction.guild.fetch_channel(tournament.reg_channel)
        try:
            message = await reg_channel.fetch_message(tournament.reg_msg_id)
            await message.delete()
        except discord.NotFound:
            pass
    if tournament.tournament_channel_id:
        try:
            tournament_channel = await interaction.guild.fetch_channel(tournament.tournament_channel_id)
            await tournament_channel.delete()
        except discord.NotFound:
            pass
    if tournament.participants_channel_id:
        try:
            participants_channel = await interaction.guild.fetch_channel(tournament.participants_channel_id)
            await participants_channel.delete()
        except discord.NotFound:
            pass

    # Reset tournament data
    tournament.restart()
    tournament.save()

    if interaction.response.is_done():
        await interaction.followup.send(f"Tournament '{tournament.name}' Restarted successfully.", ephemeral=True)
    else:
        await interaction.response.send_message(f"Tournament '{tournament.name}' Restarted successfully.", ephemeral=True)

# Select dropdown for custom notifications
class NotificationCountSelect(discord.ui.Select):
    def __init__(self, tournament: Tournament):
        options = [discord.SelectOption(label=str(i), value=str(i)) for i in range(1, 6)]
        super().__init__(placeholder="", min_values=1, max_values=1, options=options)
        self.tournament = tournament

    async def callback(self, interaction: discord.Interaction):
        count = int(self.values[0])
        await interaction.response.send_modal(NotificationTimesModal(self.tournament, count))

# View for selecting the number of notifications and a button to clear all
class NotificationView(discord.ui.View):
    def __init__(self, tournament: Tournament):
        super().__init__()
        select = NotificationCountSelect(tournament)
        select.row = 0
        self.add_item(select)
        self.tournament = tournament

    @discord.ui.button(label="🧹 Clear Notifications", style = discord.ButtonStyle.red, custom_id="clear_notifications_button", row=1)
    async def clear_notifications(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not await check_tournament_admin(interaction, self.tournament):
            return
        await cancel_scheduled_notifications(interaction.guild.id, self.tournament.id)   
        await interaction.response.send_message("All scheduled notifications have been cleared.", ephemeral=True)

# Modal for setting custom notification times
class NotificationTimesModal(discord.ui.Modal):
    def __init__(self, tournament: Tournament, count):
        super().__init__(title="Set Notification Times")
        self.tournament = tournament
        for i in range(count):
            self.add_item(discord.ui.InputText(label=f"Notification {i+1} (e.g.  30m, 12h, 2d)"))

    async def callback(self, interaction: discord.Interaction):
        intervals = []
        for child in self.children:
            value = child.value.strip().lower()
            # Parse value to seconds
            seconds = parse_time_string(value)
            if seconds is None:
                await interaction.response.send_message(f"Invalid time format: {value}", ephemeral=True)
                return
            intervals.append(seconds)
        
        # Now schedule notifications using your logic
        await schedule_custom_notifications(self.tournament, interaction, intervals)
        if interaction.response.is_done():
            await interaction.followup.send("Notifications scheduled successfully!", ephemeral=True)
        else:
            await interaction.response.send_message("Notifications scheduled sucessfully!", ephemeral=True)

# Modal for setting up the check-in system
class CheckinModal(discord.ui.Modal):
    def __init__(self, tournament: Tournament):
        super().__init__(title="Set the Check-in System")
        self.tournament = tournament
        self.add_item(discord.ui.InputText(label=f"Check-in Reminder", placeholder="Time before tournament starts (e.g. 30m, 12h, 2d)"))
        self.add_item(discord.ui.InputText(label=f"Start Check-in", placeholder="Time before tournament starts (e.g. 30m, 12h, 2d)"))
        self.add_item(discord.ui.InputText(label=f"Check-in Duration", placeholder="Duration (e.g. 30m, 12h, 2d)"))

    async def callback(self, interaction: discord.Interaction):
        values_in_seconds = []
        
        for child in self.children:
            value = child.value.strip().lower()
            # Parse value to seconds
            seconds = parse_time_string(value)
            if seconds is None:
                await interaction.response.send_message(f"Invalid time format: {value}", ephemeral=True)
                return False
            values_in_seconds.append(seconds)
        
        # Check that reminder is before checkin start
        if values_in_seconds[0] <= values_in_seconds[1]:
            await interaction.response.send_message(f"'Check-in reminder' must be set to a time before 'Check-in begin'.", ephemeral=True)
            return False

        # Get the tournament start time in seconds
        import re
        t_start_time_timestamp = re.search(r'<t:(\d+):', self.tournament.date_time)
        t_start_time = int(t_start_time_timestamp.group(1))
        # Get the time now in seconds
        now = int(datetime.now().timestamp())

        # Check that reminder is before tournament start
        if (t_start_time - values_in_seconds[0] < now):
            await interaction.response.send_message(f"'Check-in reminder' must be set to a time between now and the tournament start time.", ephemeral=True)
            return False

        # Calculate when check-in would end
        checkin_end = t_start_time - values_in_seconds[1] + values_in_seconds[2]
        if checkin_end > t_start_time:
            await interaction.response.send_message(f"Check-in end time exceeds the tournament start time.", ephemeral=True)
        
        await interaction.response.defer(ephemeral=True)
        await activate_checkin(self.tournament, interaction, values_in_seconds)
        return True

async def activate_checkin(tournament: Tournament, interaction: discord.Interaction, times_in_seconds):
    tournament.set_checkin(times_in_seconds[0], times_in_seconds[1], times_in_seconds[2], status=True, ended=False)
    reserves_copy = tournament.reserves.copy()
    # Move all reserves to players
    for _ in reserves_copy:
        await move_reserve_to_player(tournament)
    tournament.reserves = []
    tournament.save()
    await update_tournament_embeds(tournament, interaction)
    await schedule_checkin(tournament, interaction, times_in_seconds)
    await interaction.followup.send(f"Check-in system has been activated!")

async def deactivate_checkin(tournament: Tournament, interaction: discord.Interaction):
    reserves_copy = tournament.reserves.copy()
    for _ in reserves_copy: # Move all reserves to players
        await move_reserve_to_player(tournament)
    await move_players_to_reserve(tournament) # Move excess players back to reserve
    tournament.set_checkin(0, 0, 0, status=False)
    await cancel_scheduled_checkin(tournament.id)
    tournament.save()
    await update_tournament_embeds(tournament, interaction)
    if interaction.response.is_done():
        await interaction.followup.send(f"Check-in system has been deactivated.")
    else:
        await interaction.response.send_message(f"Check-in system has been deactivated.")
    return True