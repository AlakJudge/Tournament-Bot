from typing import Final
import os
import discord
from dotenv import load_dotenv
import manage
from tournament import Tournament
import run_tournament

load_dotenv()
TOKEN: Final[str] = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = discord.Bot(intents=intents)

# Globals
admin_message_id = None
reg_tournament_message_id = None

@bot.event
async def on_ready():
    print(f"{bot.user} is online")

# Slash command to create a tournament
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

        tournament =  manage.create_tournament(name=name, reg_channel=self.reg_channel, game=game, date=date, time=time)
        tournament_creation_embed = create_tournament_embed(tournament) # Create the embed with the tournament details

        # Send the response back to the user and display tournament details
        await interaction.response.send_message(embeds=[tournament_creation_embed])
        await interaction.followup.send(f"Tournament **'{name}'** with ID number **'{tournament.id}'** created successfully!", ephemeral=True)

# Edit Menu
class Menu(discord.ui.View):
    def __init__(self, tournament:Tournament):
        super().__init__()
        self.tournament = tournament

# Main Registration Menu
class Registration(discord.ui.View):    
    def __init__(self, tournament:Tournament):
        super().__init__()
        self.value = None
        self.tournament = tournament
    
    @discord.ui.button(label="Register", style = discord.ButtonStyle.green)
    async def register(self, button: discord.ui.Button, interaction: discord.Interaction):
        player = interaction.user.name # Set the player with their username
        self.tournament.register_player(player)
        self.tournament.save() # Save registration to file
        await edit_embed(self.tournament, interaction) # Edit the embed with updated number of players
        await interaction.response.send_message(f"'{player}' registered to '{self.tournament.name}' successfully.")

    @discord.ui.button(label="Unregister", style = discord.ButtonStyle.red)
    async def unregister(self, button: discord.ui.Button, interaction: discord.Interaction):
        player = interaction.user.name
        self.tournament.unregister_player(player)
        self.tournament.save()
        await edit_embed(self.tournament, interaction)
        await interaction.response.send_message(f"{player} unregistered successfully.")

# Admin Menu
class Admin(discord.ui.View):
    def __init__(self, tournament:Tournament):
        super().__init__()
        self.tournament = tournament
    
    def get_embed(self):
        return create_tournament_embed(self.tournament)
    
    # Open Registration button
    @discord.ui.button(label="Open Registration", style = discord.ButtonStyle.green)
    async def open_reg(self, button: discord.ui.Button, interaction: discord.Interaction):
        registration_view = Registration(self.tournament)

        reg_channel = await interaction.guild.fetch_channel(self.tournament.reg_channel)
        msg = await reg_channel.send("", view=registration_view, embed=create_tournament_embed(self.tournament))
        global reg_tournament_message_id
        reg_tournament_message_id = msg.id
        await interaction.response.send_message(f"Registration opened for {self.tournament.name}!", ephemeral=True)

    # Start Tournament button
    @discord.ui.button(label="Start Tournament", style = discord.ButtonStyle.green)
    async def run_tournament(self, button: discord.ui.Button, interaction: discord.Interaction):   
        await run_tournament.run_tournament(self.tournament, interaction)        

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

# Start tournament
class Start_Tournament():
    def __init__(self, tournament:Tournament) -> None:
        self.tournament = tournament

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
        if reg_tournament_message_id and reg_tournament_message_id:
            reg_channel = await interaction.guild.fetch_channel(self.tournament.reg_channel)
            message = await reg_channel.fetch_message(reg_tournament_message_id)
            await message.delete()
        admin_message =  await interaction.channel.fetch_message(admin_message_id)
        await admin_message.delete()
        await self.message.delete()

        await interaction.response.send_message(f"Tournament '{self.tournament.name}' Deleted successfully.", ephemeral=True)

    @discord.ui.button(label="No", style=discord.ButtonStyle.red)
    async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
        # If "No" is clicked, cancel the action
        await self.message.delete()
        await interaction.response.send_message("Action cancelled.", ephemeral=True)

# Edit the tournament embeds
async def edit_embed(tournament:Tournament, interaction):
    new_embed = create_tournament_embed(tournament)

    # Edit registration embed in the designated registration channel
    if reg_tournament_message_id:
        reg_channel = await interaction.guild.fetch_channel(tournament.reg_channel) # Get the channel set for registration
        message = await reg_channel.fetch_message(reg_tournament_message_id) # Get the message with the registration details
        await message.edit(embed=new_embed) 
    
    # Edit the tournament embed in the tournament lounge channel
    tournaments_lounge = discord.utils.get(interaction.guild.text_channels, name="tournaments-lounge")
    admin_message = await tournaments_lounge.fetch_message(admin_message_id)
    await admin_message.edit(embed=new_embed)

# Create an embed for tournament
def create_tournament_embed(tournament:Tournament):
    embed = discord.Embed(title=f"{tournament.name} - Tournament Information")
    embed.add_field(name="Game", value=tournament.game, inline=False)
    embed.add_field(name="Date", value=tournament.date, inline=False)
    embed.add_field(name="Time", value=tournament.time, inline=False)
    embed.add_field(name="Players Registered", value=len(tournament.players), inline=False)
    return embed

# Slash command to CREATE a new tournament
@bot.slash_command(name="create", description="Create a new tournament", guild_ids=[1286841607576092763])
async def create(
    ctx: discord.ApplicationContext,
    registration_channel: discord.TextChannel = discord.Option(
        discord.TextChannel, # Making sure the command recognizes the input as a channel
        description="The channel where player registration for the tournament will take place")
):   
    # Display the Modal requesting input from the user
    modal = Create_Tournament(reg_channel=registration_channel, title="Create Tournament")
    await ctx.send_modal(modal)

# Slash command to display a LIST OF ALL ACTIVE TOURNAMENTS
@bot.slash_command(name="tournaments_list", description="Show a list of all active tournaments and their ID numbers")
async def tournament_list(ctx):
    tournaments = Tournament.load_all_tournaments()
    list = discord.Embed(title="List of Tournaments", color=discord.Color.blue())

    # Loop to add each tournament from the tournaments list
    for t in tournaments:
        list.add_field(name=f"({t.id}) - {t.name}", value=f"Game: {t.game}", inline=False)
    await ctx.respond(embed=list)

# Slash command to ADMIN a tournament
@bot.slash_command(name = "admin", 
                    description = "Administrate a Tournament by entering its ID number.",
                    guild_ids=[1286841607576092763],
                    default_member_permissions=discord.Permissions(manage_channels=True))
async def admin(ctx, id:int = discord.Option(description="Find this ID number by using the tournaments_list command")):
   
    tournaments = Tournament.load_all_tournaments()
    tournament = next((t for t in tournaments if t.id == int(id)), None) # Go through all tournaments and find the id entered.

    # Only allow users with this permission to admin tournaments (TODO: Change this to a tournament organizer role)
    if not ctx.author.guild_permissions.manage_channels:
        await ctx.respond("You don't have the required permissions to use this command.", ephemeral=True)
        return
    
    if not tournament:
        await ctx.respond("Tournament not found.", ephemeral=True)
        return
    
    view = Admin(tournament)
    embed = view.get_embed()
    await ctx.respond("", view=view, embed=embed)

    admin_msg = await ctx.interaction.original_response()    
    global admin_message_id # Set global variable for the id of the admin message (TODO: Incorporate this into the Tournament class)
    admin_message_id = admin_msg.id

def main():
    bot.run(TOKEN)

if __name__ == '__main__':
        main()