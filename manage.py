from tournament import *
import discord
from run_tournament import run_tournament

###############################
# TOURNAMENT CREATION SECTION #
###############################

# Class for creating the tournament
# There's one optional field, for the chosen registration channel
# If no registration channel is provided. Registration will be sent to where the tournament was created
class Create_Tournament(discord.ui.Modal):
    def __init__(self, reg_channel:discord.TextChannel, title:str) -> None:
        super().__init__(title=title)
        self.reg_channel = reg_channel.id # Saving the ID of the channel picked for registration
        self.add_item(discord.ui.InputText(label="Tournament Name"))
        self.add_item(discord.ui.InputText(label="Game", placeholder="e.g. Ticket to Ride, Monopoly, Cluedo, etc."))
        self.add_item(discord.ui.InputText(label="Date", placeholder="Format: DD/MM/YYYY"))
        self.add_item(discord.ui.InputText(label="Time", placeholder="Format: HH:MM AM/PM"))

    # Getting the data from the player input modal
    async def callback(self, interaction: discord.Interaction): 
        name = self.children[0].value
        game = self.children[1].value
        date = self.children[2].value
        time = self.children[3].value

        tournament =  create_tournament(name=name, reg_channel=self.reg_channel, game=game, date=date, time=time)
        tournament_creation_embed = create_tournament_embed(tournament) # Create the embed with the tournament details

        # Send the response back to the user and display tournament details
        await interaction.response.send_message(embeds=[tournament_creation_embed])
        await interaction.followup.send(f"Tournament **'{name}'** with ID number **'{tournament.id}'** created successfully!", ephemeral=True)

# Create an embed for tournament
def create_tournament_embed(tournament:Tournament):
    embed = discord.Embed(title=f"{tournament.name} - Tournament Information")
    embed.add_field(name="Game", value=tournament.game, inline=False)
    embed.add_field(name="Date", value=tournament.date, inline=False)
    embed.add_field(name="Time", value=tournament.time, inline=False)
    embed.add_field(name="Players Registered", value=len(tournament.players), inline=False)
    embed.add_field(name="Registration Status", value="Open", inline=False)
    return embed

# Create the new tournament and save to file
def create_tournament(name, reg_channel, game, date, time):
    
    tournaments = Tournament.load_all_tournaments()

    if tournaments:
        id = max([int(t.id) for t in tournaments]) + 1
    else:
        id = 1

    tournament = Tournament(id=id, reg_channel=reg_channel, name=name, game=game, date=date, time=time)
    tournament.save()

    return tournament

###########################
# TOURNAMENT EDIT SECTION #
###########################

# Edit Menu
class Menu(discord.ui.View):
    def __init__(self, tournament:Tournament):
        super().__init__(timeout=None)
        self.tournament = tournament

# View for the edit options select menu
class Edit_Options_View(discord.ui.View):
    def __init__(self, tournament):
        super().__init__()
        self.add_item(Edit_Select_Menu(tournament))

# Drop-down menu to edit tournament
class Edit_Select_Menu(discord.ui.Select):
    def __init__(self, tournament:Tournament):
        self.tournament = tournament
        options = [
                discord.SelectOption(
                    label="Edit Name",
                    description="Edit the name of the tournament"
                ),
                discord.SelectOption(
                    label="Edit Game",
                    description="Edit the game to be played in the tournament"
                ),
                discord.SelectOption(
                    label="Edit Date",
                    description="Edit the date of the tournament"
                ),
                discord.SelectOption(
                    label="Edit Time",
                    description="Edit the time of the tournament"
                )
            ]
        super().__init__(placeholder="Select a field to edit...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        match self.values[0]:
            case "Edit Name":
                modal =  Editing_Modal(self.tournament, "Name")
            case "Edit Game":
                modal =  Editing_Modal(self.tournament, "Game")
            case "Edit Date":
                modal =  Editing_Modal(self.tournament, "Date")
            case "Edit Time":
                modal =  Editing_Modal(self.tournament, "Time")

        await interaction.response.send_modal(modal)

# Modal pop-up to edit a field
class Editing_Modal(discord.ui.Modal):
    def __init__(self, tournament, field):
        super().__init__(title="Edit Field Value")
        self.add_item(discord.ui.InputText(label=f"New {field}"))
        self.tournament = tournament
        self.field = field

    async def callback(self, interaction: discord.Interaction):
        new_value = self.children[0].value
        match self.field:
            case "Name":
                self.tournament.edit_name(new_value)
            case "Game":
                self.tournament.edit_game(new_value)
            case "Date":
                self.tournament.edit_date(new_value)
            case "Time":
                self.tournament.edit_time(new_value)

        await interaction.response.send_message(f"{self.field} updated to {new_value}.", ephemeral=True)
        await edit_embed(self.tournament, interaction)
        self.tournament.save()

# Edit the tournament embeds
async def edit_embed(tournament:Tournament, interaction):
    new_embed = create_tournament_embed(tournament)

    # Edit registration embed in the designated registration channel
    if tournament.reg_msg_id:
        reg_channel = await interaction.guild.fetch_channel(tournament.reg_channel) # Get the channel set for registration
        message = await reg_channel.fetch_message(tournament.reg_msg_id) # Get the message with the registration details
        await message.edit(embed=new_embed) 
    
    # Edit the tournament embed in the tournament lounge channel
    tournaments_lounge = discord.utils.get(interaction.guild.text_channels, name="🏆tournaments-lounge")
    admin_message = await tournaments_lounge.fetch_message(tournament.admin_msg_id)
    await admin_message.edit(embed=new_embed)

# "Are you sure?" confirmation view for deleting a tournament
class Delete_Confirmation_View(discord.ui.View):
    def __init__(self, message, tournament:Tournament):
        super().__init__()
        self.message = message
        self.tournament = tournament

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.green)
    async def confirm(self, button: discord.ui.Button,interaction: discord.Interaction):
        Tournament.delete_tournament(self.tournament.id)

        # Delete all messages related to the tournament, if they exist
        if self.tournament.reg_msg_id and self.tournament.admin_msg_id:
            reg_channel = await interaction.guild.fetch_channel(self.tournament.reg_channel)
            message = await reg_channel.fetch_message(self.tournament.reg_msg_id)
            await message.delete()

            admin_message =  await interaction.channel.fetch_message(self.tournament.admin_msg_id)
            await admin_message.delete()
            await self.message.delete()

        await interaction.response.send_message(f"Tournament '{self.tournament.name}' Deleted successfully.", ephemeral=True)

    @discord.ui.button(label="No", style=discord.ButtonStyle.red)
    async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
        # If "No" is clicked, cancel the action
        await self.message.delete()
        await interaction.response.send_message("Action cancelled.", ephemeral=True)

###################################
# TOURNAMENT REGISTRATION SECTION #
###################################

# Main Registration Menu
class Registration(discord.ui.View):    
    def __init__(self, tournament:Tournament):
        super().__init__(timeout=None)
        self.tournament = tournament
    
    @discord.ui.button(label="Register", style = discord.ButtonStyle.green)
    async def register(self, button: discord.ui.Button, interaction: discord.Interaction):
        # Get user and participants channel
        player_name = interaction.user.name
        player = discord.utils.get(interaction.guild.members, name=player_name) 
        participants_channel = await interaction.guild.fetch_channel(self.tournament.participants_channel_id)

        # Get tournament details and check if the user is already registered. Stop duplicate register if so.
        tournament:Tournament = Tournament.load_tournament_by_name(self.tournament.name)
        for p in tournament.players:
            if player_name == p:
                await interaction.response.send_message(f"Registration failed. '{player_name}' is already registered to '{self.tournament.name}'.", ephemeral=True)
                return
        
        k_view = kick_view(self.tournament)
        self.tournament.register_player(player_name)
        self.tournament.save() # Save registration to file
        await edit_embed(self.tournament, interaction) # Edit the embed with updated number of players
        await interaction.response.defer()
        await participants_channel.send(f"{player.mention} registered to '{self.tournament.name}' successfully.", view=k_view)

    @discord.ui.button(label="Unregister", style = discord.ButtonStyle.red)
    async def unregister(self, button: discord.ui.Button, interaction: discord.Interaction):
        # Get user
        player_name = interaction.user.name
        player = discord.utils.get(interaction.guild.members, name=player_name) 
        # Get participants channel
        participants_channel = await interaction.guild.fetch_channel(self.tournament.participants_channel_id)
        # Unregister player then save change to file
        self.tournament.unregister_player(player_name)
        self.tournament.save()

        await edit_embed(self.tournament, interaction)
        await interaction.response.defer()
        await participants_channel.send(f"{player.mention} unregistered from '{self.tournament.name}'.")

# Logic for Kick button
class kick_view(discord.ui.View):
    def __init__(self, tournament:Tournament):
        super().__init__(timeout=None)
        self.tournament = tournament

    @discord.ui.button(label="Kick", style=discord.ButtonStyle.red)
    async def kick_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        # Get the user and participants channel
        player_name = interaction.user.name
        player = discord.utils.get(interaction.guild.members, name=player_name)
        participants_channel = await interaction.guild.fetch_channel(self.tournament.participants_channel_id)
        # Check if player is still in the server
        if not player:
            await interaction.response.send_message("Unable to kick. Player not found.", ephemeral=True)
            return
        # Unregister the player from the tournament
        self.tournament.unregister_player(player_name)
        self.tournament.save()
        # Edit the embed with updated number of players
        await edit_embed(self.tournament, interaction)

        await participants_channel.send(f"{player.mention} has been kicked from '{self.tournament.name}'.")
        await interaction.response.defer()


######################
# ADMIN MENU SECTION #
######################

# Admin Menu
class Admin(discord.ui.View):
    def __init__(self, tournament:Tournament):
        super().__init__(timeout=None)
        self.tournament = tournament
    
    def get_embed(self):
        return create_tournament_embed(self.tournament)
    
    # Open Registration button
    @discord.ui.button(label="Open Registration", style = discord.ButtonStyle.green)
    async def open_reg(self, button: discord.ui.Button, interaction: discord.Interaction):
        registration_view = Registration(self.tournament)
        reg_channel = await interaction.guild.fetch_channel(self.tournament.reg_channel)

        if not self.tournament.reg_msg_id:            
            msg = await reg_channel.send("", view=registration_view, embed=create_tournament_embed(self.tournament))
            self.tournament.reg_msg_id = msg.id
            self.tournament.save()
            # Create channel for participants logs and management
            category = discord.utils.get(interaction.guild.categories, name="Tournaments")
            participants_channel:discord.TextChannel = await interaction.guild.create_text_channel("participants-"+self.tournament.name, category=category)
            self.tournament.participants_channel_id = participants_channel.id
            
            await interaction.response.send_message(f"Registration opened for '{self.tournament.name}'!", ephemeral=True)
        else:
            # Fetch message and embed if it already exists
            reg_msg = await reg_channel.fetch_message(self.tournament.reg_msg_id)
            reg_embed = reg_msg.embeds[0]

            # Edit registration status - Return if Registration is already Open
            for index, field in enumerate(reg_embed.fields):
                if field.name == "Registration Status":
                    if field.value == "Open":
                        await interaction.response.send_message(f"Registration is already open.", ephemeral=True)
                        return
                    reg_embed.set_field_at(index, name=field.name, value="Open", inline=field.inline)
                    break

            # Re-enable buttons
            for item in registration_view.children:
                if isinstance(item, discord.ui.Button):
                    item.disabled = False

            # Update the original message to re-enable buttons
            await reg_msg.edit(view=registration_view, embed=reg_embed)
            await interaction.response.send_message(f"Registration opened for '{self.tournament.name}'!", ephemeral=True)

    # Close Registration button
    @discord.ui.button(label="Close Registration", style = discord.ButtonStyle.red)
    async def close_reg(self, button: discord.ui.Button, interaction: discord.Interaction):  
        # Fetch registration channel, message and embed, and recreate view
        reg_channel = await interaction.guild.fetch_channel(self.tournament.reg_channel)
        reg_msg = await reg_channel.fetch_message(self.tournament.reg_msg_id)
        reg_embed = reg_msg.embeds[0]
        registration_view = Registration(self.tournament)
        # Disable all buttons in the view
        for item in registration_view.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        # Edit registration status
        for index, field in enumerate(reg_embed.fields):
            if field.name == "Registration Status":
                reg_embed.set_field_at(index, name=field.name, value="Closed", inline=field.inline)
                break
        # Update the original message to disable buttons
        await reg_msg.edit(view=registration_view, embed=reg_embed)

        await interaction.response.send_message(f"Registration closed for '{self.tournament.name}'!", ephemeral=True)

    # Start Tournament button
    @discord.ui.button(label="Start Tournament", style = discord.ButtonStyle.green)
    async def run_tournament(self, button: discord.ui.Button, interaction: discord.Interaction):   
        await run_tournament(self.tournament, interaction)        

    # Edit Tournament button
    @discord.ui.button(label="Edit Tournament", style = discord.ButtonStyle.blurple)
    async def edit_tournament(self, button: discord.ui.Button, interaction: discord.Interaction):
        view = Edit_Options_View(self.tournament)
        await interaction.response.send_message("", view=view, ephemeral=True)

    # Delete Tournament button
    @discord.ui.button(label="Delete Tournament", style = discord.ButtonStyle.red)
    async def delete_tournament(self,  button: discord.ui.Button, interaction: discord.Interaction):
        view = Delete_Confirmation_View(message=interaction.message, tournament = self.tournament)
        await interaction.response.send_message(f"Are you sure you want to **DELETE** '{self.tournament.name}'?", view=view)
