from random import shuffle
from math import ceil

import discord

from tournament import Tournament
from utils.debug import get_user_safe, get_mention_safe, is_dummy_player, is_debug_mode_enabled
from utils.helpers import tournament_lock
from views.registration import close_registration
from views.management import create_tournament_embed, update_tournament_embeds

# Function that controls the flow of the tournament
async def run_tournament(t:Tournament, interaction: discord.Interaction):
    tournament: Tournament = Tournament.load_tournament_by_id(interaction.guild.id, t.id)

    # Check if there are any registered players
    if not len(tournament.players) > 0:
        await interaction.response.send_message("Cannot start the tournament as there are no registered players.", ephemeral=True)
        return

    # Only collect details for next round if there's no final winner yet
    if not tournament.tournament_winner: 
        details = set_details(tournament)
        await interaction.response.send_modal(details)         
        await details.wait()
        async with tournament_lock:
            # This will run if it's a brand new tournament
            if tournament.round == 1:
                if tournament.reg_status == "Open":
                    await close_registration(interaction, tournament)
                await set_brackets(interaction, tournament, details.game_size, details.min_games)
            # This one includes the list of the winners from the previous round
            else:
                await set_brackets(interaction, tournament, details.game_size, details.min_games, get_round_winners(tournament))
    else:
        tournament_channel = discord.utils.get(interaction.guild.text_channels, id=tournament.tournament_channel_id)
        participant_role = discord.utils.get(interaction.guild.roles, name=f"({tournament.id}) Tournament Participant")
        await tournament_channel.send(f"# The winner of '{tournament.name}' is {get_mention_safe(interaction.guild, tournament.tournament_winner)}! CONGRATULATIONS! :tada::tada:\n"
                                    f"Thank you all {participant_role.mention}s for attending and being awesome. See you next time! :fire:")
        await lock_all_threads(interaction, tournament_channel, tournament.round)

# Set the match details for the current round
class set_details(discord.ui.Modal):
    def __init__(self, tournament:Tournament) -> None:
        super().__init__(title="Running Details", timeout=None)
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

        async with tournament_lock:
            self.tournament.next_round() # Set round to +1
            self.tournament.save() # Save to json file

        await interaction.response.send_message(f"You've selected:\n- Game Size: {self.game_size}\n- Min Games: {self.min_games}", ephemeral=True)
       
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
    tournament_channel = discord.utils.get(guild.text_channels, id=tournament.tournament_channel_id)

    # Create tournament channel message if round 1
    if tournament.round == 1:
        # Create view for ongoing tournament buttons
        from views.running.tournament_view import Tournament_Running_View
        running_view = Tournament_Running_View(tournament = tournament)
        # Display tournament details embed in tournament channel and pin it
        embed = create_tournament_embed(tournament)
        tournament_channel_msg = await tournament_channel.send(embeds=[embed], view=running_view)
        await tournament_channel_msg.pin()
        await tournament_channel.send(f"# '{tournament.name}' is ready to start. GOOD LUCK! :fire:")
        # Save id of that embed
        tournament.tournament_channel_msg_id = tournament_channel_msg.id
    else:
        # Close all active threads if it's not Round 1
        await lock_all_threads(interaction, tournament_channel, tournament.round-1)
    
    # Fetch admin role or create if it doesn't exist
    admin_role: discord.Role = discord.utils.get(interaction.guild.roles, name=tournament.admin_role)
    if not admin_role:
        # Give it to tournament owner
        admin_role = await interaction.guild.create_role(name=tournament.admin_role)
        await interaction.guild.get_member(tournament.owner).add_roles(admin_role)

    # Distribute players evenly into matches
    for index, game in enumerate(games):
        # Set match id
        match_id = f"R{tournament.round}-G{index+1}"
        
        # Create threads for each match and name it final round if it's the last round
        if len(games) == 1:
            thread_name = f"🔥Final Round🔥"
        else:
            thread_name = f"Round {tournament.round} - Game {index+1}"

        thread = await tournament_channel.create_thread(
            name=thread_name, 
            type=discord.ChannelType.private_thread,
            auto_archive_duration = 10080 # Hide after 1 week
            )
        await thread.send(f"## :fire: Welcome to your match! :fire:")
        
        # Turn off "anyone can invite" to the thread
        await thread.edit(invitable=False)

        match = {
            "id": match_id,
            "players": [],
            "winners": [],
            "thread_id": thread.id,
            "thread_msg_id": None, # Will be set later when the thread message is sent
        }

        for _ in range(game):
            # Get user ID and mention in thread
            user = get_user_safe(guild, players[p_index])
            if not user:
                # Remove the player from the list if not in debug mode
                if is_debug_mode_enabled():
                    pass # keep dummy players in debug mode
                else:
                    await interaction.followup.send(f"User '{players[p_index]}' not found in this server.", ephemeral=True)
                    players.remove(players[p_index])
                continue # skip to next player
            
            # Add user to match thread
            await thread.send(f"{get_mention_safe(guild, players[p_index])}")

            match["players"].append(players[p_index])
            p_index += 1
        
        from views.running.match_views import Start_Match_View

        start_match_view = Start_Match_View(match_id, tournament)
        tournament.matches.append(match)
        
        if not tournament.thread_msg:
            await thread.send("### Hello participants! Please, be respectful and follow the tournament rules!")
        else:
            await thread.send(tournament.thread_msg)
        
        start_match_view = await thread.send(f"Once the match is over, an Admin will press the button below to set the winner of the match.\n"
                                            f"*Tag {admin_role.mention} if you need help with anything*", view=start_match_view)
        await start_match_view.pin()
        # Save the message ID of the thread message with the view
        match["thread_msg_id"] = start_match_view.id
    
    # Create a thread exclusive for late check in and reserves to communicate with admins
    if (tournament.reserves or tournament.late_checkin) and tournament.round == 1:
        reserves_thread = await tournament_channel.create_thread(
            name="Reserves",
            type=discord.ChannelType.private_thread
        )
        await reserves_thread.send(f"## 📢 This thread is for reserves and late check-ins. {admin_role.mention} will communicate with you here.")
        tournament.reserves_thread_id = reserves_thread.id
        # Add all late check in and reserves to the thread
        if tournament.late_checkin:
            await reserves_thread.send(f"### LATE CHECK-INS (priority):\n")
            for player in tournament.late_checkin:
                user = get_user_safe(guild, player)
                if user:
                    await reserves_thread.send(f"{get_mention_safe(guild, player)}")
        if tournament.reserves:
            await reserves_thread.send(f"\n### RESERVES:\n")
            for player in tournament.reserves:
                user = get_user_safe(guild, player)
                if user:
                    await reserves_thread.send(f"{get_mention_safe(guild, player)}")

    tournament.curr_num_matches = len(games)
    tournament.save()

# Add a player to a match while the tournament is running
async def add_player_to_match(interaction: discord.Interaction, t: Tournament, match_id: int, player: str):
    async with tournament_lock:
        # Update tournament data
        tournament = Tournament.load_tournament_by_id(interaction.guild.id, t.id)

        # Get player user object
        user = get_user_safe(interaction.guild, player)
        
        if not is_debug_mode_enabled() and not user:
            return False
        
        # Iterate through and find the match
        match = next((m for m in tournament.matches if m["id"] == match_id), None)
        if match:
            if player not in match["players"]:
                # Handle late check-in players
                if player in tournament.late_checkin:
                    tournament.late_checkin.remove(player)
                    tournament.checked_in.append(player)
                # Remove from reserve list and add to player list if player is a reserve
                if player in tournament.reserves:
                    tournament.reserves.pop(tournament.reserves.index(player))
                    tournament.players.append(player)
                    await update_tournament_embeds(tournament, interaction)    
                match["players"].append(player)
                tournament.save()
                await send_message_to_game_thread(interaction, tournament, match_id, f"{get_mention_safe(interaction.guild, player)} has been added to this match.")
                return True
            else:
                await send_message_to_game_thread(interaction, tournament, match_id, f"Failed. {get_mention_safe(interaction.guild, player)} is already in this match.")
                return False 
        await send_message_to_game_thread(interaction, tournament, match_id, f"Failed. Match not found.")
        return False 

# Remove a player from a match while the tournament is running
async def remove_player_from_match(interaction, tournament: Tournament, match_id: int, player: str):
    async with tournament_lock:
        # Update tournament data
        tournament = Tournament.load_tournament_by_id(interaction.guild.id, tournament.id)

        user = get_user_safe(interaction.guild, player)
        match = next((m for m in tournament.matches if m["id"] == match_id), None)

        if match:
            if player in match["players"]:
                match["players"].remove(player)
                tournament.save()
                await send_message_to_game_thread(interaction, tournament, match_id, f"{get_mention_safe(interaction.guild, player)} has been removed from this match.")
                # Also remove from thread
                thread = discord.utils.get(interaction.guild.threads, id=match["thread_id"])
                if thread:
                    if not is_dummy_player(player):
                        await thread.remove_user(user)
                    # If match is now empty, lock the thread
                    if not match["players"]:
                        await thread.edit(locked=True, name=f"{thread.name}🔒")
                        await thread.send(f"## This match has no players. The thread will be locked.")
                return True
            else:
                print("Failed. Player not in match.")
                return False 
        print("Failed. Match not found.")
        return False

# Set the winner of a match while the tournament is running
async def set_match_winner(interaction, tournament: Tournament, match_id: int, player: str):
    async with tournament_lock:
        # Iterate through and find the match
        match = next((m for m in tournament.matches if m["id"] == match_id), None)
        if match:
            match["winners"].append(player)
            tournament.save()

            mentions = ", ".join(discord.utils.get(interaction.guild.members, name=p).mention for p in match["winners"])
            await send_message_to_game_thread(interaction, tournament, match_id, f"## Winners of this match: {mentions}")
            return True

        print("Failed. Match not found.")
        return False

# Get winners for all matches in the round
def get_round_winners(tournament: Tournament):
    # Determine the last round number
    last_round = max(int(match["id"].split('-')[0][1:]) for match in tournament.matches)
    # Filter matches to get only those from the last round
    last_round_matches = [match for match in tournament.matches if match["id"].startswith(f"R{last_round}-")]
    # Extract the winners from those matches. Flatten the list of winners
    winners = [winner for match in last_round_matches for winner in match["winners"] if match["winners"]]
    return winners

# Send message of all winners from the previous round to tournament channel
async def send_round_winners(interaction: discord.Interaction, tournament: Tournament):
    # Fetch tournament channel object
    tournament_channel = discord.utils.get(interaction.guild.text_channels, id=tournament.tournament_channel_id)
    # Get the winners from the previous round
    winners = get_round_winners(tournament)

    winners_users = []
    for winner in winners:
        user = get_user_safe(interaction.guild, winner)
        if not user:
            await interaction.followup.send(f"User '{winner}' not found in this server.", ephemeral=True)
            winners.remove(winner)  # Remove the player from the list
            continue
        winners_users.append(user) # Add the user to the list

    # Send the list of winners to the tournament channel
    if winners_users:
        await tournament_channel.send(f"## Congratulations to all **Round {tournament.round} Winners! :fire:**\n"
                                        f"{', '.join(get_mention_safe(interaction.guild, user.name) for user in winners_users)}")
    else:
        await interaction.followup.send("## No winners found for the previous round.")

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

# Lock all current open threads
async def lock_all_threads(interaction: discord.Interaction, channel: discord.TextChannel, round: int):
    
    # Fetch active threads in the channel, iterate and lock each thread
    for thread in channel.threads:
        if not thread.locked: 
            await thread.edit(locked=True, name=f"{thread.name}🔒")

    # check if interaction has been responded to
    if interaction.response.is_done():
        await interaction.followup.send(f"*All Round {round} game threads in {channel.mention} have been locked*")
    else:
        await interaction.response.send_message(f"*All Round {round} game threads in {channel.mention} have been locked*")

# Function to check if all current round winners have been selected
def all_winners_selected(tournament: Tournament):
    # Find all matches in the current round
    current_round = max(int(match["id"].split('-')[0][1:]) for match in tournament.matches)
    round_matches = [match for match in tournament.matches if match["id"].startswith(f"R{current_round}-")]

    for match in round_matches:
        if not match["winners"]:
            return False
    return True

# Refresh all Start_Match_View instances with updated tournament data
async def refresh_match_views(interaction: discord.Interaction, tournament: Tournament):
    updated_tournament = Tournament.load_tournament_by_id(interaction.guild.id, tournament.id)
    
    for match in updated_tournament.matches:
        if match.get("thread_msg_id"):
            thread = discord.utils.get(interaction.guild.threads, id=match["thread_id"])
            if thread:
                try:
                    thread_msg = await thread.fetch_message(match["thread_msg_id"])
                    # Create a new view with updated tournament data
                    from views.running.match_views import Start_Match_View
                    new_view = Start_Match_View(match["id"], updated_tournament)
                    await thread_msg.edit(view=new_view)
                except discord.NotFound:
                    continue
