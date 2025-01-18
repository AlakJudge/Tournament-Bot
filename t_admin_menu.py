from t_registration import Registration, close_registration
from tournament import Tournament
from t_management import *
from t_registration import Reg_Msg_Modal
from t_utils import check_tournament_admin
from t_running import run_tournament
import discord

class T_Admin(discord.ui.View):
    def __init__(self, tournament:Tournament):
        super().__init__(timeout=None)
        self.tournament = tournament
    
    def get_embed(self):
        return create_tournament_embed(self.tournament)
    
    # Open Registration button
    @discord.ui.button(label="Open Registration", style = discord.ButtonStyle.green)
    async def open_reg(self, button: discord.ui.Button, interaction: discord.Interaction):
        # Check if the user has the admin role or is a server admin
        if not await check_tournament_admin(interaction, self.tournament):
            return

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

            self.tournament.edit_reg_status("Open")
            await update_tournament_embeds(self.tournament, interaction)

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
           
            self.tournament.save()
            
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

            # Update the original message to re-enable buttons
            await reg_msg.edit(view=registration_view, embed=reg_embed)
            await interaction.response.send_message(f"Registration opened for '{self.tournament.name}'!", ephemeral=True)

            # Edit registration status
            self.tournament.edit_reg_status("Open")
            await update_tournament_embeds(self.tournament, interaction)
            
            self.tournament.save()

    # Close Registration button
    @discord.ui.button(label="Close Registration", style = discord.ButtonStyle.red)
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
    @discord.ui.button(label="Start Tournament", style = discord.ButtonStyle.green)
    async def t_run(self, button: discord.ui.Button, interaction: discord.Interaction):  
        if not await check_tournament_admin(interaction, self.tournament):
            return 
        await run_tournament(self.tournament, interaction)        

    # Edit Tournament button
    @discord.ui.button(label="Edit Tournament", style = discord.ButtonStyle.blurple)
    async def edit_tournament(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not await check_tournament_admin(interaction, self.tournament):
            return
        view = Edit_Options_View(self.tournament)
        await interaction.response.send_message("", view=view, ephemeral=True)

    # Show list of registered users
    @discord.ui.button(label="👥", style = discord.ButtonStyle.blurple)
    async def show_reg(self, button: discord.ui.Button, interaction: discord.Interaction):
        await show_registered_users(self.tournament, interaction)

    # Delete Tournament button
    @discord.ui.button(label="Delete Tournament", style = discord.ButtonStyle.red)
    async def delete_tournament(self,  button: discord.ui.Button, interaction: discord.Interaction):
        if not await check_tournament_admin(interaction, self.tournament):
            return
        view = Delete_Confirmation_View(message=interaction.message, tournament = self.tournament)
        await interaction.response.send_message(f"Are you sure you want to **DELETE** '{self.tournament.name}'?", view=view)

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
                                            f"**Registered Reserves**\n"
                                            f"{reserves_list}", ephemeral=True)