from t_utils import check_tournament_admin, move_reserve_to_player
from t_management import   update_tournament_embeds, create_tournament_embed
from tournament import Tournament
import discord
import t_debug

class Registration(discord.ui.View):    
    def __init__(self, tournament:Tournament):
        super().__init__(timeout=None)
        self.tournament: Tournament = tournament
    
    @discord.ui.button(label="Register", style = discord.ButtonStyle.green, custom_id="register_button")
    async def register(self, button: discord.ui.Button, interaction: discord.Interaction):
        await register_player_to_tournament(self.tournament, interaction.user, interaction)

    @discord.ui.button(label="Unregister", style = discord.ButtonStyle.red, custom_id="unregister_button")
    async def unregister(self, button: discord.ui.Button, interaction: discord.Interaction):
        # Defer the interaction to prevent timeout
        await interaction.response.defer(ephemeral=True)
        
        player_name = interaction.user.name
        player = discord.utils.get(interaction.guild.members, name=player_name) 
        participants_channel = await interaction.guild.fetch_channel(self.tournament.participants_channel_id)
        tournament_channel = await interaction.guild.fetch_channel(self.tournament.tournament_channel_id)

        # Update tournament data
        self.tournament = Tournament.load_tournament_by_id(interaction.guild.id, self.tournament.id)

        # Check if player is registered
        if player_name not in self.tournament.players and player_name not in self.tournament.reserves:
            await interaction.followup.send(f"Failed. '{player_name}' is not registered to '{self.tournament.name}'.", ephemeral=True)
            return

        # Remove participant role from user
        participants_role: discord.Role = discord.utils.get(interaction.guild.roles, name=self.tournament.participants_role) 
        await interaction.user.remove_roles(participants_role)

        # Unregister player then save change to file
        if player_name in self.tournament.players:
            self.tournament.unregister_player(player_name)
            if await move_reserve_to_player(self.tournament):
                # Send message to tournament channel saying who was promoted from reserve to player
                promoted_player_name = self.tournament.players[-1]
                mention = t_debug.get_mention_safe(interaction.guild, promoted_player_name)
                await tournament_channel.send(f"**{mention} has been promoted from reserve to player!**")
        else:
            self.tournament.unregister_reserve(player_name)

        self.tournament.save()

        await update_tournament_embeds(self.tournament, interaction)
        await interaction.followup.send(f"'{player_name}' unregistered from '{self.tournament.name}'.", ephemeral=True)
        await participants_channel.send(f"----------------------------------\n"
                                        f"{player.mention} unregistered from '{self.tournament.name}'.")
       
    
    @discord.ui.button(label="✏️ Edit", style = discord.ButtonStyle.blurple, custom_id="edit_reg_button")
    async def edit_reg(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not await check_tournament_admin(interaction, self.tournament):
            return
        
        modal = Reg_Msg_Modal(self.tournament, type="edit")
        await interaction.response.send_modal(modal)

# Modal for registration message
class Reg_Msg_Modal(discord.ui.Modal):
    def __init__(self, tournament: Tournament, type: str = None):
        super().__init__(title="Write a Registration Message")
        self.tournament = tournament
        self.type = type
        self.add_item(discord.ui.InputText(
            label="Enter a Registration Message (optional)", 
            style=discord.InputTextStyle.paragraph, 
            placeholder="Message...",
            required=False))

    async def callback(self, interaction: discord.Interaction):
        msg_content = self.children[0].value
        reg_channel = await interaction.guild.fetch_channel(self.tournament.reg_channel)
        registration_view = Registration(self.tournament)
        embed = create_tournament_embed(self.tournament)        
        
        if self.type == "edit":
            # Fetch registration message and edit it 
            old_msg_id = self.tournament.reg_msg_id
            message = await reg_channel.fetch_message(old_msg_id)
            
            await message.edit(content=msg_content, view=registration_view, embed=embed)
            await reg_channel.send(f"Registration message for '{self.tournament.name}' updated successfully.", delete_after=2)
        else:
            # Send a new message
            msg = await reg_channel.send(content=msg_content, embed=embed, view=registration_view)
            self.tournament.reg_msg_id = msg.id
            self.tournament.save()

            await interaction.response.send_message(f"Registration opened for '{self.tournament.name}'!", delete_after=2)

# Logic for Kick button
class kick_view(discord.ui.View):
    def __init__(self, tournament:Tournament, player_name):
        super().__init__(timeout=None)
        self.tournament = tournament
        self.player_name = player_name

    @discord.ui.button(label="Kick", style=discord.ButtonStyle.red, custom_id="kick_button")
    async def kick_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        # Reload the latest tournament data
        tournament = Tournament.load_tournament_by_id(interaction.guild.id, self.tournament.id)
        self.tournament = tournament  # Update the view's reference
        # Get necessary user and channels
        player = discord.utils.get(interaction.guild.members, name=self.player_name)
        participants_channel = await interaction.guild.fetch_channel(self.tournament.participants_channel_id)
        tournament_channel = await interaction.guild.fetch_channel(self.tournament.tournament_channel_id)
        # Check if player is still in the server
        if not player:
            await interaction.response.send_message(f"Unable to kick. Player not found.", ephemeral=True)
            return
        
        # Unregister the player from the tournament
        if self.player_name in self.tournament.players:
            self.tournament.unregister_player(self.player_name)
            if await move_reserve_to_player(self.tournament):
                # Send message to tournament channel saying who was promoted from reserve to player
                promoted_player = discord.utils.get(interaction.guild.members, name=self.tournament.players[-1])
                await tournament_channel.send(f"**{promoted_player.mention} has been promoted from reserve to player!**")
        else:
            self.tournament.unregister_reserve(self.player_name)

        self.tournament.save()

        # Edit the embed with updated number of players
        await update_tournament_embeds(self.tournament, interaction)
    
        await participants_channel.send(f"----------------------------------\n"
                                        f"{player.mention} has been kicked from '{self.tournament.name}'.")
        await interaction.response.defer()

        await self.message.delete()

# Function to register a player to a tournament
async def register_player_to_tournament(tournament, player, interaction=None):
    # Get user and participants channel
    participants_channel = await interaction.guild.fetch_channel(tournament.participants_channel_id)
    # Reload the latest tournament data
    tournament = Tournament.load_tournament_by_id(interaction.guild.id, tournament.id)

    # Get tournament details and check if the user is already registered. Stop duplicate register if so.
    if player.name in tournament.players or player.name in tournament.reserves:
        await interaction.response.send_message(f"Registration failed. '{player.name}' is already registered to '{tournament.name}'.", ephemeral=True)
        return

    # Assign the participant role to the user
    if tournament.participants_role and not t_debug.is_dummy_player(player.name):
        participants_role: discord.Role = discord.utils.get(interaction.guild.roles, name=tournament.participants_role) 
        await interaction.user.add_roles(participants_role)

    k_view = kick_view(tournament, player.name) # Set up view for kick button

    # Get checkin status
    checkin_status = tournament.get_checkin_status()

    # Add as player if under the player cap limit or if it's checkin mode, otherwise add as reserve
    if len(tournament.players) < tournament.player_cap or checkin_status:
        tournament.register_player(player.name)
        await interaction.response.send_message(f"'{player.name}' registered to '{tournament.name}' successfully.", ephemeral=True)
    else:
        tournament.register_reserve(player.name)    
        await interaction.response.send_message(f"'{player.name}' registered to '{tournament.name}' as a **RESERVE** successfully.", ephemeral=True)    
    
    tournament.save() # Save registration to file
    await update_tournament_embeds(tournament, interaction) # Edit the embed with updated number of players

    mention = t_debug.get_mention_safe(interaction.guild, player.name)
    await participants_channel.send(f"----------------------------------\n"
                                     f"{mention} registered to '{tournament.name}' successfully.", view=k_view)

# Close registration function
async def close_registration(interaction: discord.Interaction, tournament: Tournament):
    # Fetch registration channel, message and embed, and recreate view
    if not tournament.reg_msg_id:
        if interaction.response.is_done():
            await interaction.followup.send("Registration message not found.", ephemeral=True)
        else:
            await interaction.response.send_message("Registration message not found.", ephemeral=True)
    else:
        reg_channel = await interaction.guild.fetch_channel(tournament.reg_channel)
        try:
            reg_msg = await reg_channel.fetch_message(tournament.reg_msg_id)
            reg_embed = reg_msg.embeds[0]
            registration_view = Registration(tournament)

            # Disable all buttons in the view
            for item in registration_view.children:
                if isinstance(item, discord.ui.Button):
                    item.disabled = True
            
            # Update the original message to disable buttons
            await reg_msg.edit(view=registration_view, embed=reg_embed)
        
        except discord.NotFound:
            if interaction.response.is_done():
                await interaction.followup.send("Registration message not found.", ephemeral=True)
            else:
                await interaction.response.send_message("Registration message not found.", ephemeral=True)
    
    # Update tournament data
    tournament = Tournament.load_tournament_by_id(interaction.guild.id, tournament.id)

    # Edit registration status
    tournament.edit_reg_status("Closed")
    tournament.save()
    await update_tournament_embeds(tournament, interaction)
    
    if interaction.response.is_done():
        await interaction.followup.send(f"Registration closed for '{tournament.name}'!", ephemeral=True)
    else:
        await interaction.response.send_message(f"Registration closed for '{tournament.name}'!", ephemeral=True)
