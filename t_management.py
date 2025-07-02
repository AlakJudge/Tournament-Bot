from tournament import Tournament
from t_utils import move_reserve_to_player, unix_convert_date_time
import discord

###############################
# TOURNAMENT CREATION SECTION #
###############################

class Create_Tournament(discord.ui.Modal):
    def __init__(self, reg_channel: discord.TextChannel, title: str, player_cap: int) -> None:
        super().__init__(title=title)
        self.reg_channel = reg_channel.id # Saving the ID of the channel picked for registration
        self.player_cap = player_cap
        self.add_item(discord.ui.InputText(label="Tournament Name"))
        self.add_item(discord.ui.InputText(label="Game", placeholder="e.g. Ticket to Ride, Monopoly, Cluedo, etc."))
        self.add_item(discord.ui.InputText(label="Date", placeholder="Format: DD/MM/YYYY"))
        self.add_item(discord.ui.InputText(label="Time", placeholder="Format: HH:MM (e.g. 17:30)"))
        self.add_item(discord.ui.InputText(label="Prize", placeholder="e.g. Expansion, Free Game, etc."))

    # Getting the data from the player input modal
    async def callback(self, interaction: discord.Interaction):
        name = self.children[0].value
        game = self.children[1].value
        date = self.children[2].value
        time = self.children[3].value
        prize = self.children[4].value
        
        # Validate and convert date and time to a Discord timestamp format and save it
        formatted_date_time = await unix_convert_date_time(interaction, date, time)
        if not formatted_date_time:
            return

        tournament =  create_tournament(
            name=name, 
            reg_channel=self.reg_channel, 
            game=game, 
            date=date,
            time=time,
            date_time=formatted_date_time,
            prize=prize, 
            player_cap=self.player_cap,
            guild_id=interaction.guild.id
        )
        tournament_creation_embed = create_tournament_embed(tournament) # Create the embed with the tournament details

        # Create and assign "admin" role to creator
        admin_role = await interaction.guild.create_role(name=f"({tournament.id}) Tournament Admin", permissions=discord.Permissions.none(), mentionable=True)
        await interaction.user.add_roles(admin_role)
        tournament.admin_role = admin_role.name

        # Set tournament owner
        tournament.owner = interaction.user.id

        # Create general role for participants
        participants_role = await interaction.guild.create_role(name=f"({tournament.id}) Tournament Participant", permissions=discord.Permissions.none())
        tournament.participants_role = participants_role.name

        tournament.save()

        # Send the response back to the user and display tournament details
        await interaction.response.send_message(embeds=[tournament_creation_embed], ephemeral=True)
        await interaction.followup.send(f"Tournament **'{name}'** with ID number **'{tournament.id}'** created successfully!", ephemeral=True)

# Create an embed for tournament
def create_tournament_embed(tournament:Tournament):
    embed = discord.Embed(title=f"{tournament.name} - Tournament Information")
    embed.add_field(name="Game", value=tournament.game, inline=False)
    embed.add_field(name="Date & Time (Your Timezone)", value=tournament.date_time, inline=False)
    embed.add_field(name="Prize", value=tournament.prize, inline=False)
    embed.add_field(name="Players Registered", value=f"{len(tournament.players)}/{tournament.player_cap} + *{len(tournament.reserves)} Reserves*", inline=False)
    embed.add_field(name="Registration Status", value=tournament.reg_status, inline=False)
    return embed

# Create the new tournament and save to file
def create_tournament(name, reg_channel, game, date, time, date_time, prize, player_cap: int):
    tournaments = Tournament.load_all_tournaments(reg_channel.guild.id)
    # Set the tournament ID
    if tournaments:
        id = max([int(t.id) for t in tournaments]) + 1
    else:
        id = 1

    tournament = Tournament(
        id=id, 
        reg_channel=reg_channel, 
        name=name, 
        game=game, 
        date=date,
        time=time,
        date_time=date_time,
        prize=prize,
        player_cap=player_cap
        )

    return tournament

###########################
# TOURNAMENT EDIT SECTION #
###########################

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
                ),
                discord.SelectOption(
                    label="Edit Prize",
                    description="Edit the prize of the tournament"
                ),
                discord.SelectOption(
                    label="Edit Player Cap",
                    description="Edit the maximum number of players allowed in the tournament"
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
            case "Edit Prize":
                modal =  Editing_Modal(self.tournament, "Prize")
            case "Edit Player Cap":
                modal = Editing_Modal(self.tournament, "Player Cap")

        await interaction.response.send_modal(modal)

# Modal pop-up to edit a field
class Editing_Modal(discord.ui.Modal):
    def __init__(self, tournament, field):
        super().__init__(title="Edit Field Value")
        self.add_item(discord.ui.InputText(label=f"New {field}"))
        self.tournament: Tournament = tournament
        self.field = field

    async def callback(self, interaction: discord.Interaction):
        new_value = self.children[0].value
        match self.field:
            case "Name":
                self.tournament.edit_name(new_value)
            case "Game":
                self.tournament.edit_game(new_value)
            case "Date":
                self.tournament.edit_date_time(await unix_convert_date_time(interaction, new_value, self.tournament.time))
                self.tournament.edit_date(new_value)
            case "Time":
                self.tournament.edit_date_time(await unix_convert_date_time(interaction, self.tournament.date, new_value))
                self.tournament.edit_time(new_value)
            case "Prize":
                self.tournament.edit_prize(new_value)
            case "Player Cap":
                # Check if value is an intenger and send error if not
                if not new_value.isdigit():
                    await interaction.response.send_message("Player Cap must be a number.", ephemeral=True)
                    return
                # Get difference to check if it's possible to promote a reserve to player, and how many
                difference = int(new_value) - self.tournament.player_cap 
                # Overwrite the player cap
                self.tournament.edit_player_cap(int(new_value))
                
                for _ in range(difference):
                    # Promote reserves to players
                    if await move_reserve_to_player(self.tournament):
                        promoted_player = discord.utils.get(interaction.guild.members, name=self.tournament.players[-1])
                        # Send message to tournament channel saying who was promoted from reserve to player
                        tournament_channel = await interaction.guild.fetch_channel(self.tournament.tournament_channel_id)
                        await tournament_channel.send(f"**{promoted_player.mention} has been promoted from reserve to player!**")

        if not interaction.response.is_done():
            await interaction.response.send_message(f"{self.field} updated to {new_value}.", ephemeral=True)
        else:
            await interaction.followup.send(f"{self.field} updated to {new_value}.", ephemeral=True)
        self.tournament.save()
        await update_tournament_embeds(self.tournament, interaction)

# Edit the tournament embeds
async def update_tournament_embeds(t:Tournament, interaction: discord.Interaction):
    tournament: Tournament = Tournament.load_tournament_by_name(interaction.guild.id, t.name)
    new_embed = create_tournament_embed(tournament)

    # Edit registration embed in the designated registration channel
    if tournament.reg_msg_id:
        reg_channel = await interaction.guild.fetch_channel(tournament.reg_channel) # Get the channel set for registration
        try:
            message = await reg_channel.fetch_message(tournament.reg_msg_id) # Get the message with the registration details
            await message.edit(embed=new_embed)
        except discord.NotFound:
            if interaction.response.is_done():
                await interaction.followup.send("Registration message not found.", ephemeral=True)
            else:
                await interaction.response.send_message("Registration message not found.", ephemeral=True)            

    # Edit the tournament embed in the tournament lounge channel
    tournaments_lounge = discord.utils.get(interaction.guild.text_channels, name="🏆tournaments-lounge")
    admin_message = await tournaments_lounge.fetch_message(tournament.admin_msg_id)
    await admin_message.edit(embed=new_embed)

    # Edit the tournament embed in the tournament channel
    if tournament.tournament_channel_msg_id:
        tournament_channel = await interaction.guild.fetch_channel(tournament.tournament_channel_id)
        tournament_message = await tournament_channel.fetch_message(tournament.tournament_channel_msg_id)
        await tournament_message.edit(embed=new_embed)

# "Are you sure?" confirmation view for DELETING a tournament
class Delete_Confirmation_View(discord.ui.View):
    def __init__(self, message, tournament:Tournament):
        super().__init__()
        self.message = message
        self.tournament = tournament

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.green)
    async def confirm(self, button: discord.ui.Button,interaction: discord.Interaction):
        Tournament.delete_tournament(self.tournament.id)

        # Delete all messages related to the tournament, if they exist
        await delete_all_tournament_messages(interaction, self.tournament)

        # Delete yes/no buttons view
        await self.message.delete()
        
        # Delete tournament roles
        await delete_tournament_roles(interaction, self.tournament, "Tournament deleted by admin.")

        await interaction.response.send_message(f"Tournament '{self.tournament.name}' Deleted successfully.", ephemeral=True)

    @discord.ui.button(label="No", style=discord.ButtonStyle.red)
    async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
        # If "No" is clicked, cancel the action
        await self.message.delete()
        await interaction.response.send_message("Action cancelled.", ephemeral=True)

# "Are you sure?" confirmation view for ARCHIVING a tournament
class Archive_Confirmation_View(discord.ui.View):
    def __init__(self, message, tournament:Tournament):
        super().__init__()
        self.message = message
        self.tournament = tournament

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.green)
    async def confirm(self, button: discord.ui.Button,interaction: discord.Interaction):
        Tournament.archive_tournament(interaction.guild.id, self.tournament.id)

        # Delete all messages related to the tournament, if they exist
        await delete_all_tournament_messages(interaction, self.tournament)

        # Delete yes/no buttons view
        await self.message.delete()
        
        # Delete tournament roles
        await delete_tournament_roles(interaction, self.tournament, "Tournament archived by admin.")

        await interaction.response.send_message(f"Tournament '{self.tournament.name}' Archived successfully.", ephemeral=True)

    @discord.ui.button(label="No", style=discord.ButtonStyle.red)
    async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
        # If "No" is clicked, cancel the action
        await self.message.delete()
        await interaction.response.send_message("Action cancelled.", ephemeral=True)

# Delete all roles related to the tournament
async def delete_tournament_roles(interaction: discord.Interaction, tournament: Tournament, reason: str):
        admin_role: discord.Role = discord.utils.get(interaction.guild.roles, name=tournament.admin_role)
        try:
            await admin_role.delete(reason=reason)
        except discord.NotFound:
            pass  

        participants_role: discord.Role = discord.utils.get(interaction.guild.roles, name=tournament.participants_role)            
        try:
            await participants_role.delete(reason=reason)
        except discord.NotFound:
            pass

# Delete all messages related to the tournament, if they exist
async def delete_all_tournament_messages(interaction: discord.Interaction, tournament: Tournament):
    if tournament.reg_msg_id:
        reg_channel = await interaction.guild.fetch_channel(tournament.reg_channel)
        try:
            reg_msg = await reg_channel.fetch_message(tournament.reg_msg_id)
            await reg_msg.delete()
        except discord.NotFound:
            pass
    if tournament.admin_msg_id:
        admin_message =  await interaction.channel.fetch_message(tournament.admin_msg_id)
        try:
            await admin_message.delete()
        except discord.NotFound:
            pass