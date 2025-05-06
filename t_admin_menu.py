from t_registration import Registration, close_registration
from tournament import Tournament
from t_management import update_tournament_embeds, create_tournament_embed, Delete_Confirmation_View, Edit_Options_View
from t_registration import Reg_Msg_Modal
from t_utils import check_tournament_admin, schedule_notifications
from t_running import run_tournament
import discord


class T_Admin(discord.ui.View):
    def __init__(self, tournament:Tournament):
        super().__init__(timeout=None)
        self.tournament = tournament
    
    def get_embed(self):
        return create_tournament_embed(self.tournament)
    
    # Open Registration button
    @discord.ui.button(label="📖 Open Reg", style = discord.ButtonStyle.green)
    async def open_reg(self, button: discord.ui.Button, interaction: discord.Interaction):
        # Check if the user has the admin role or is a server admin
        if not await check_tournament_admin(interaction, self.tournament):
            return
        # Update tournament data
        self.tournament: Tournament = Tournament.load_tournament_by_name(self.tournament.name)

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
                # Create channel for participants logs and management, accessible only to tournament admins
                admin_role = discord.utils.get(interaction.guild.roles, name=f"({self.tournament.id}) Tournament Admin") # Fetch admin role
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
            reg_msg = await reg_channel.fetch_message(self.tournament.reg_msg_id)
            reg_embed = reg_msg.embeds[0]

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
    @discord.ui.button(label="🛑 Close Reg", style = discord.ButtonStyle.red)
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
    @discord.ui.button(label="🟢 Start Tournament", style = discord.ButtonStyle.green)
    async def t_run(self, button: discord.ui.Button, interaction: discord.Interaction):  
        if not await check_tournament_admin(interaction, self.tournament):
            return 
        await run_tournament(self.tournament, interaction)        

    # Edit Tournament button
    @discord.ui.button(label="📄 Edit Info", style = discord.ButtonStyle.blurple)
    async def edit_tournament(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not await check_tournament_admin(interaction, self.tournament):
            return
        view = Edit_Options_View(self.tournament)
        await interaction.response.send_message("", view=view, ephemeral=True)

    # Add new thread message
    @discord.ui.button(label="📝 Edit Match Intro", style = discord.ButtonStyle.blurple)
    async def add_thread_msg(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not await check_tournament_admin(interaction, self.tournament):
            return
        
        # Send modal to get new thread message
        modal = Thread_Msg_Modal(self.tournament)
        await interaction.response.send_modal(modal)

    # Show list of registered users
    @discord.ui.button(label="👥 Player List", style = discord.ButtonStyle.blurple)
    async def show_reg(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not await check_tournament_admin(interaction, self.tournament):
            return
        
        await show_registered_users(self.tournament, interaction)

    # Schedule Notifications button
    @discord.ui.button(label="⏰ Notifications", style = discord.ButtonStyle.blurple)
    async def schedule_notifications(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not await check_tournament_admin(interaction, self.tournament):
            return

        # Check if tournament chat channel exists
        if not self.tournament.tournament_channel_id:
            await interaction.response.send_message("Tournament chat channel does not exist. Please Open Registration to create it before scheduling a notification.", ephemeral=True)
            return

        # Schedule notifications for 24 and 2 hours before the tournament
        await schedule_notifications(self.tournament, interaction)
    
    # Add New Admin button
    @discord.ui.button(label="➕ Add New Admin", style = discord.ButtonStyle.blurple)
    async def add_admin(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not await check_tournament_admin(interaction, self.tournament):
            return

        # Send modal to get username
        modal = Add_Admin_Modal(self.tournament)
        await interaction.response.send_modal(modal)

    # Rmove Admin button
    @discord.ui.button(label="➖ Remove Admin", style = discord.ButtonStyle.blurple)
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
    @discord.ui.button(label="🔄 Restart Tournament", style = discord.ButtonStyle.blurple)
    async def restart_tournament(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not await check_tournament_admin(interaction, self.tournament):
            return
        view = Restart_Confirmation_View(message=interaction.message, tournament = self.tournament)
        await interaction.response.send_message(f"Are you sure you want to **RESTART** '{self.tournament.name}'?", view=view)

    # Delete Tournament button
    @discord.ui.button(label="❌ Delete Tournament", style = discord.ButtonStyle.red)
    async def delete_tournament(self,  button: discord.ui.Button, interaction: discord.Interaction):
        if not await check_tournament_admin(interaction, self.tournament):
            return
        view = Delete_Confirmation_View(message=interaction.message, tournament = self.tournament)
        await interaction.response.send_message(f"Are you sure you want to **DELETE** '{self.tournament.name}'?", view=view)

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
        self.tournament: Tournament = Tournament.load_tournament_by_name(self.tournament.name) # Update tournament data
        msg_content = self.children[0].value
        self.tournament.edit_thread_msg(msg_content)
        self.tournament.save()

        await interaction.response.send_message(f"Game-Tread Message Updated!", ephemeral=True)

# Function to show list of registered users
async def show_registered_users(t: Tournament, interaction: discord.Interaction):
    # Get updated tournament data
    tournament: Tournament = Tournament.load_tournament_by_name(t.name)
    # Get the list of registered players
    players = tournament.players
    reserves = tournament.reserves
    
    players_list = "\n".join(players)
    reserves_list = "\n".join(reserves)

    if not players_list:
        players_list = "*No players registered yet.*"
        return
    await interaction.response.send_message(f"**Registered Players**\n"
                                            f"{players_list}\n"
                                            f"\n**Registered Reserves**\n"
                                            f"{reserves_list}", ephemeral=True)

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
    tournament: Tournament = Tournament.load_tournament_by_name(tournament.name)
    
    await interaction.response.defer()

    # Close registration if it is open
    if tournament.reg_status == "Open":
        await close_registration(interaction, tournament)
    await update_tournament_embeds(tournament, interaction)

    # Delete all messages and channels related to the tournament, if they exist.
    # Except the admin message and reg channel ID
    if tournament.reg_msg_id:
        reg_channel = await interaction.guild.fetch_channel(tournament.reg_channel)
        message = await reg_channel.fetch_message(tournament.reg_msg_id)
        await message.delete()
    if tournament.tournament_channel_id:
        tournament_channel = await interaction.guild.fetch_channel(tournament.tournament_channel_id)
        await tournament_channel.delete()
    if tournament.participants_channel_id:
        participants_channel = await interaction.guild.fetch_channel(tournament.participants_channel_id)
        await participants_channel.delete()

    # Reset tournament data
    tournament.restart()
    tournament.save()

    if interaction.response.is_done():
        await interaction.followup.send(f"Tournament '{tournament.name}' Restarted successfully.", ephemeral=True)
    else:
        await interaction.response.send_message(f"Tournament '{tournament.name}' Restarted successfully.", ephemeral=True)
