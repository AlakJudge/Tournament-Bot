from math import ceil

from tournament import Tournament
from random import shuffle
import discord
from manage import *
import manage

# Function that controls the flow of the tournament
async def run_tournament(tournament:Tournament, interaction: discord.Interaction):

    # Only collect details for next round if there's no final winner yet
    if not tournament.winner: 
        details = set_details(tournament)
        await interaction.response.send_modal(details)         
        await details.wait() 
        # This will run if it's a brand new tournament
        if tournament.round == 1: 
            await set_brackets(interaction, tournament, details.game_size, details.min_games)
        # This one includes the list of the winners from the previous round
        else:
            await set_brackets(interaction, tournament, details.game_size, details.min_games, t_players=tournament.winners)
    else:
        tournament_channel = discord.utils.get(interaction.guild.text_channels, id=tournament.tournament_channel_id)
        user: discord.Member = discord.utils.get(interaction.guild.members, name=tournament.winner)
        await tournament_channel.send(f"# The winner is {user.mention}! CONGRATULATIONS! :tada::tada:")
        await lock_all_threads(interaction, tournament_channel)

# Set the match details for the current round
class set_details(discord.ui.Modal):
    def __init__(self, tournament:Tournament) -> None:
        super().__init__(title="Running Details")

        if tournament.round == 1:
            total_players = len(tournament.players)
        else:
            total_players = len(tournament.winners)

        self.add_item(discord.ui.InputText(label="Max players per game?", placeholder="Cannot be higher than 5."))
        self.add_item(discord.ui.InputText(label="Minimum number of games?", placeholder=f"Cannot be higher than {total_players//2}"))

    async def callback(self, interaction: discord.Interaction):
        self.game_size = int(self.children[0].value)
        self.min_games = int(self.children[1].value)

        await interaction.response.send_message(f"You've selected:\nGame Size: {self.game_size} -- Min Games: {self.min_games}", ephemeral=True)

class Start_Match_View(discord.ui.View):
    def __init__(self, match, tournament):
        super().__init__()
        self.match = match 
        self.tournament = tournament

    @discord.ui.button(label="Start Match", style=discord.ButtonStyle.green)
    async def start_match(self, button: discord.ui.Button, interaction: discord.Interaction):
        winner_view = Select_Winner_View(self.tournament, self.match)
        await interaction.response.send_message(f"Match Started! Once it's over, please select the winner below.", view=winner_view)

class Select_Winner_View(discord.ui.View):    
    def __init__(self, tournament, match):
        super().__init__()
        self.add_item(Select_Winner_Menu(tournament, match))

# Drop-down menu to select the winner of the match
class Select_Winner_Menu(discord.ui.Select):
    def __init__(self, tournament:Tournament, match):
        self.tournament = tournament
        self.match = match

        options = []

        for player in match:
                options.append(                
                    discord.SelectOption(
                        label=f"{player}",
                        description=f"Select {player} as the winner of the match."
                    )
                )            
        super().__init__(placeholder="Select the winner of the match.", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"{self.values[0]} is the winner of this match!")
        if self.tournament.curr_num_matches == 1:
            self.tournament.set_winner(self.values[0])
            self.tournament.save()
            await run_tournament(self.tournament, interaction)
        else:
            self.tournament.winners.append(self.values[0])
        
        # Only proceed if all winners have been selected
        tournament_channel = discord.utils.get(interaction.guild.text_channels, id=self.tournament.tournament_channel_id)
        if len(self.tournament.winners) == self.tournament.curr_num_matches and not self.tournament.winners[self.tournament.curr_num_matches-1] == None :
            view = Next_Round_Confirmation_View(tournament = self.tournament)
            confirmation_message = await tournament_channel.send(f"### All winners have been selected. Would you like to proceed to the next round?", view=view)
            view.conf_message = confirmation_message

# Ask Admin if they'd like to proceed to the next round with a confirmation button
class Next_Round_Confirmation_View(discord.ui.View):
    def __init__(self, tournament:Tournament, conf_message=None):
        super().__init__()
        self.conf_message = conf_message
        self.tournament = tournament

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.green)
    async def confirm(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.tournament.next_round() # Set round to +1
        self.tournament.save() # Save to json file

        await run_tournament(self.tournament, interaction) # Start the next round of the tournament
        await interaction.followup.send(f"## ROUND {self.tournament.round} STARTED!")
        if self.conf_message:
            await self.conf_message.delete()

# Function with the logic to divide players into brackets, create the threads and allocate the players respectively
async def set_brackets(interaction, tournament:Tournament, game_size: int, min_games: int, t_players:list = None):
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
    
    matches = []
    p_index = 0
    guild = interaction.guild

    # Create tournament channel if round 1
    if tournament.round == 1:
        category = discord.utils.get(guild.categories, name="Tournaments")
        tournament_channel:discord.TextChannel = await guild.create_text_channel("chat-"+tournament.name, category=category)
        tournament.tournament_channel_id = tournament_channel.id

        # Display tournament details embed in tournament channel and pin it
        embed = manage.create_tournament_embed(tournament)
        tournament_channel_msg = await tournament_channel.send(embeds=[embed])
        await tournament_channel_msg.pin()
        # Save id of that embed
        tournament.tournament_channel_msg_id = tournament_channel_msg.id
        
    else:
        tournament_channel = discord.utils.get(interaction.guild.text_channels, id=tournament.tournament_channel_id)

    # Close all active threads if it's not Round 1
    if not tournament.round == 1:
        await lock_all_threads(interaction, tournament_channel)

    # Distribute players evenly into matches
    for game in games:
        # Create threads for each match
        thread = await tournament_channel.create_thread(name=f"Round {tournament.round} - Game {len(matches)+1}", type=discord.ChannelType.private_thread)
        await thread.send(f"##  Welcome to your match!")
        match = []
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

            match.append(players[p_index])
            p_index += 1

        matches.append(match)

        start_match_view = Start_Match_View(match, tournament)
        await thread.send("### Hello participants! Once all players are ready, press the button below to start the match.", view=start_match_view)
    
    tournament.curr_num_matches = len(matches)
    tournament.save()

    # Reset round winners list
    tournament.winners = []

# Lock all current open threads
async def lock_all_threads(interaction, channel: discord.TextChannel):
    
    # Fetch active threads in the channel, iterate and lock each thread
    for thread in channel.threads:
        if not thread.locked: 
            await thread.edit(locked=True)

    await interaction.followup.send(f"All past game threads in {channel.mention} have been locked.")