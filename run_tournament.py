from math import ceil

from tournament import Tournament
from random import shuffle
import discord
from manage import *
import manage

# Function that controls the flow of the tournament
async def run_tournament(t:Tournament, interaction: discord.Interaction):
    tournament: Tournament = Tournament.load_tournament_by_name(t.name)

    # Only collect details for next round if there's no final winner yet
    if not tournament.tournament_winner: 
        details = set_details(tournament)
        await interaction.response.send_modal(details)         
        await details.wait()
        # This will run if it's a brand new tournament
        if tournament.round == 1: 
            await set_brackets(interaction, tournament, details.game_size, details.min_games)
        # This one includes the list of the winners from the previous round
        else:
            await set_brackets(interaction, tournament, details.game_size, details.min_games, get_round_winners(tournament))
    else:
        tournament_channel = discord.utils.get(interaction.guild.text_channels, id=tournament.tournament_channel_id)
        user: discord.Member = discord.utils.get(interaction.guild.members, name=tournament.tournament_winner)
        await tournament_channel.send(f"# The winner of '{tournament.name}' is {user.mention}! CONGRATULATIONS! :tada::tada:")
        await lock_all_threads(interaction, tournament_channel, tournament.round)

# Set the match details for the current round
class set_details(discord.ui.Modal):
    def __init__(self, tournament:Tournament) -> None:
        super().__init__(title="Running Details")
        self.tournament = tournament

        if tournament.round == 0:
            total_players = len(tournament.players)
        else:
            total_players = len(get_round_winners(tournament))

        self.add_item(discord.ui.InputText(label="Max players per game?", placeholder="Cannot be higher than 6."))
        self.add_item(discord.ui.InputText(label="Minimum number of games?", placeholder=f"Cannot be higher than {total_players//2}"))

    async def callback(self, interaction: discord.Interaction):
        self.game_size = int(self.children[0].value)
        self.min_games = int(self.children[1].value)

        self.tournament.next_round() # Set round to +1
        self.tournament.save() # Save to json file

        await interaction.response.send_message(f"You've selected:\nGame Size: {self.game_size} -- Min Games: {self.min_games}", ephemeral=True)

class Start_Match_View(discord.ui.View):
    def __init__(self, match_id: int, tournament: Tournament):
        super().__init__(timeout=None)
        self.match_id = match_id 
        self.tournament: Tournament = tournament

    @discord.ui.button(label="Start Match", style=discord.ButtonStyle.green)
    async def start_match(self, button: discord.ui.Button, interaction: discord.Interaction):
        # Check if the user has the admin role or is a server admin
        if not await manage.Admin.check_tournament_admin(interaction, self.tournament):
            return
        
        self.tournament = Tournament.load_tournament_by_name(self.tournament.name) # update tournament info from file

        winner_view = Select_Winner_View(self.tournament, self.match_id)
        await interaction.response.send_message(f"Match Started! Once it's over, an Admin will select the winner below.", view=winner_view)

class Select_Winner_View(discord.ui.View):    
    def __init__(self, tournament, match_id):
        super().__init__(timeout=None)
        self.add_item(Select_Winner_Menu(tournament, match_id))

# Drop-down menu to select the winner of the match
class Select_Winner_Menu(discord.ui.Select):
    def __init__(self, tournament:Tournament, match_id):
        self.tournament = tournament
        self.match_id = match_id

        # Iterate through and find the corresponding match
        match = next(m for m in self.tournament.matches if m["id"] == self.match_id)
        
        options = [                
            discord.SelectOption(
                label=player,
                description=f"Select {player} as the winner of the match."
            )
            for player in match["players"]
        ]            
        super().__init__(placeholder="Select the winner of the match.", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        # Check if the user has the admin role or is a server admin
        if not await manage.Admin.check_tournament_admin(interaction, self.tournament):
            return
        
        self.tournament = Tournament.load_tournament_by_name(self.tournament.name) # update tournament info from file

        winner: discord.Member = discord.utils.get(interaction.guild.members, name=self.values[0]) 
        await interaction.response.send_message(f"## {winner.mention} is the winner of this match!")

        # Iterate through and find the corresponding match
        match = next(m for m in self.tournament.matches if m["id"] == self.match_id)
        match["winner"] = winner.name  # Update the winner for the correct match
        self.tournament.save()
        
        if self.tournament.curr_num_matches == 1:
            self.tournament.set_tournament_winner(winner.name)
            self.tournament.save()
            await run_tournament(self.tournament, interaction)
        else:
            # Get tournament channel object
            tournament_channel = discord.utils.get(interaction.guild.text_channels, id=self.tournament.tournament_channel_id)
            # Check if all round winners have been selected
            if all_winners_selected(self.tournament):
                await tournament_channel.send("## All winners have been selected. We're ready for the next round! :fire:")

        # Disable to prevent multiple winners
        self.disabled = True
        if self.view:
            # Update the view and message
            for child in self.view.children:
                if isinstance(child, discord.ui.Select):
                    child.disabled = True
            await interaction.message.edit(view=self.view)

# Admin buttons available after the tournament has started
class Tournament_Running_View(discord.ui.View):
    def __init__(self, tournament:Tournament):
        super().__init__(timeout=None)
        self.tournament: Tournament = tournament

    @discord.ui.button(label="Go to next round", style=discord.ButtonStyle.blurple)
    async def go_to_next_round(self, button: discord.ui.Button, interaction: discord.Interaction):
        # Check if the user has the admin role or is a server admin
        if not await manage.Admin.check_tournament_admin(interaction, self.tournament):
            return
        
        await run_tournament(self.tournament, interaction) # Start the next round of the tournament
        
        self.tournament = Tournament.load_tournament_by_name(self.tournament.name) # Update tournament data
       
        # Refresh the view/buttons in the tournament channel
        tournament_channel = discord.utils.get(interaction.guild.text_channels, id=self.tournament.tournament_channel_id)
        embed = manage.create_tournament_embed(self.tournament)
        new_view = Tournament_Running_View(self.tournament)
        msg = await tournament_channel.fetch_message(self.tournament.tournament_channel_msg_id)
        await msg.edit(embed=embed, view=new_view)

        
        await interaction.followup.send(f"## ROUND {self.tournament.round} STARTED!")

    @discord.ui.button(label="Add player to match", style=discord.ButtonStyle.blurple)
    async def add_player(self, button: discord.ui.Button, interaction: discord.Interaction):
        # Check if the user has the admin role or is a server admin
        if not await manage.Admin.check_tournament_admin(interaction, self.tournament):
            return
        
        # Modal requesting play name and match id. Will add new player to an existing match
        await interaction.response.send_modal(AddPlayerModal(self.tournament))
        
# Function with the logic to divide players into brackets, create the threads and allocate the players respectively
async def set_brackets(interaction: discord.Interaction, tournament:Tournament, game_size: int, min_games: int, t_players:list = None):
    players = []
    if not t_players:
        t_players = tournament.players

    # Randomize brackets
    shuffle(t_players)

    for p in t_players:
        players.append(p)

    total_players = len(players)

    # Approximate number of games
    number_of_games = ceil(total_players / game_size)
    while number_of_games < min_games:
        number_of_games += 1
    # Even distribution of players per game
    players_per_game = total_players // number_of_games
    remainder = total_players % number_of_games
    # Set the number of players in each game
    games = [players_per_game] * number_of_games
    # Distribute remainder of players
    for i in range(remainder):
        games[i] += 1
    
    p_index = 0
    guild: discord.Guild = interaction.guild

    # Create tournament channel if round 1
    if tournament.round == 1:
        category = discord.utils.get(guild.categories, name="TOURNAMENTS")
        tournament_channel:discord.TextChannel = await guild.create_text_channel("🗨chat-"+tournament.name, category=category)
        tournament.tournament_channel_id = tournament_channel.id
        # Create view for ongoing tournament buttons
        running_view = Tournament_Running_View(tournament = tournament)
        # Display tournament details embed in tournament channel and pin it
        embed = manage.create_tournament_embed(tournament)
        tournament_channel_msg = await tournament_channel.send(embeds=[embed], view=running_view)
        await tournament_channel_msg.pin()
        await tournament_channel.send(f"# '{tournament.name}' has started. GOOD LUCK! :fire:")
        # Save id of that embed
        tournament.tournament_channel_msg_id = tournament_channel_msg.id
        
    else:
        tournament_channel = discord.utils.get(guild.text_channels, id=tournament.tournament_channel_id)
        # Close all active threads if it's not Round 1
        await lock_all_threads(interaction, tournament_channel, tournament.round-1)

    # Distribute players evenly into matches
    for index, game in enumerate(games):
        # Set match id
        match_id = f"R{tournament.round}-G{index+1}"
        # Create threads for each match
        thread = await tournament_channel.create_thread(name=f"Round {tournament.round} - Game {index+1}", type=discord.ChannelType.private_thread)
        await thread.send(f"## :fire: Welcome to your match! :fire:")
        
        match = {
            "id": match_id,
            "players": [],
            "winner": None,
            "thread_id": thread.id
        }

        for _ in range(game):
            # Get user ID and mention in thread
            user: discord.Member = discord.utils.get(guild.members, name=players[p_index])
            if not user:
                await interaction.followup.send(f"User '{players[p_index]}' not found in this server.")
                return
            # Add user to tournament channel
            await tournament_channel.set_permissions(user, view_channel=True, send_messages=True)
            # Add user to match thread
            await thread.send(f"{user.mention}")

            match["players"].append(players[p_index])
            p_index += 1

        start_match_view = Start_Match_View(match_id, tournament)
        tournament.matches.append(match)

        # Fetch admin role to mention
        admin_role: discord.Role = discord.utils.get(interaction.guild.roles, name=tournament.admin_role)    
        await thread.send("### Hello participants! Once all players are ready, an Admin will press the button below to start the match.\n"
                          f"*Tag {admin_role.mention} if you need help with anything*", view=start_match_view)
    
    tournament.curr_num_matches = len(games)
    tournament.save()

# Get winners for all matches in the round
def get_round_winners(tournament: Tournament):
    return [match["winner"] for match in tournament.matches if match["winner"]]

# Add a player to a match while the tournament is running
async def add_player_to_match(interaction, tournament: Tournament, match_id: int, player: str):
    # Get player user object
    user: discord.Member = discord.utils.get(interaction.guild.members, name=player)
    # Iterate through and find the match
    match = next((m for m in tournament.matches if m["id"] == match_id), None)
    if match:
        if player not in match["players"]:
            match["players"].append(player)
            tournament.save()
            await send_message_to_game_thread(interaction, tournament, match_id, f"{user.mention} has been added to the match.")
            return True
        else:
            print("Failed. Player already in match.")
            return False 
    print("Failed. Match not found.")
    return False 

# Function to find and send a message to a specific game thread
async def send_message_to_game_thread(interaction, tournament, match_id, message):
    match = next((m for m in tournament.matches if m["id"] == match_id), None)
    if match:
        thread = discord.utils.get(interaction.guild.threads, id=match["thread_id"])
        if thread:
            await thread.send(message)
        else:
            print(f"Thread with ID {match['thread_id']} not found.")
    else:
        print(f"Match with ID {match_id} not found.")

# Modal for adding new player to match
class AddPlayerModal(discord.ui.Modal):
    def __init__(self, tournament: Tournament):
        super().__init__(title="Add Player to Match")
        self.tournament = tournament
        self.add_item(discord.ui.InputText(label="Player Name"))
        self.add_item(discord.ui.InputText(label="match_id"))

    async def callback(self, interaction: discord.Interaction):
        player = self.children[0].value
        match_id = self.children[1].value

        success = await add_player_to_match(interaction, self.tournament, match_id, player)

        if success:
            await interaction.response.send_message(f"{player} added to Match {match_id}.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Failed to add {player} to Match {match_id}.", ephemeral=True)

# Lock all current open threads
async def lock_all_threads(interaction, channel: discord.TextChannel, round: int):
    
    # Fetch active threads in the channel, iterate and lock each thread
    for thread in channel.threads:
        if not thread.locked: 
            await thread.edit(locked=True)

    await interaction.followup.send(f"*All Round {round} game threads in {channel.mention} have been locked*")

def all_winners_selected(tournament: Tournament):
    for match in tournament.matches:
        if not match["winner"]:
            return False
    return True