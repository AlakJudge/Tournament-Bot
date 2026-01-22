import asyncio
import discord
from math import ceil
from random import shuffle
from t_utils import check_tournament_admin, send_announcement
from t_management import create_tournament_embed, update_tournament_embeds
from t_registration import close_registration
from tournament import Tournament
from t_debug import *
import t_debug

# Lock to prevent different data from being edited at the same time and causing conflict
tournament_lock = asyncio.Lock() 


#####################
# RUN SETUP SECTION #
#####################
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
        running_view = Tournament_Running_View(tournament = tournament)
        # Display tournament details embed in tournament channel and pin it
        embed = create_tournament_embed(tournament)
        tournament_channel_msg = await tournament_channel.send(embeds=[embed], view=running_view)
        await tournament_channel_msg.pin()
        await tournament_channel.send(f"# '{tournament.name}' is about to start. GOOD LUCK! :fire:")
        # Save id of that embed
        tournament.tournament_channel_msg_id = tournament_channel_msg.id
    else:
        # Close all active threads if it's not Round 1
        await lock_all_threads(interaction, tournament_channel, tournament.round-1)
    
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
                if t_debug.TOURNAMENT_DEBUG_MODE:
                    pass # keep dummy players in debug mode
                else:
                    await interaction.followup.send(f"User '{players[p_index]}' not found in this server.", ephemeral=True)
                    players.remove(players[p_index])
                continue # skip to next player
            
            # Add user to match thread
            await thread.send(f"{get_mention_safe(guild, players[p_index])}")

            match["players"].append(players[p_index])
            p_index += 1

        start_match_view = Start_Match_View(match_id, tournament)
        tournament.matches.append(match)

        # Fetch admin role to mention
        admin_role: discord.Role = discord.utils.get(interaction.guild.roles, name=tournament.admin_role)    
        
        if not tournament.thread_msg:
            await thread.send("### Hello participants! Please, be respectful and follow the tournament rules!")
        else:
            await thread.send(tournament.thread_msg)
        
        start_match_view = await thread.send(f"Once the match is over, an Admin will press the button below to set the winner of the match.\n"
                                            f"*Tag {admin_role.mention} if you need help with anything*", view=start_match_view)
        await start_match_view.pin()
        # Save the message ID of the thread message with the view
        match["thread_msg_id"] = start_match_view.id
    
    tournament.curr_num_matches = len(games)
    tournament.save()





##############################
# INSIDE GAME THREAD SECTION #
##############################

class Start_Match_View(discord.ui.View):
    def __init__(self, match_id, tournament: Tournament):
        super().__init__(timeout=None)
        self.match_id = match_id 
        self.tournament: Tournament = tournament

    @discord.ui.button(label="🏅 Set Winner", style=discord.ButtonStyle.green, custom_id="set_winner_button")
    async def set_winner(self, button: discord.ui.Button, interaction: discord.Interaction):
        # Check if the user has the admin role or is a server admin
        if not await check_tournament_admin(interaction, self.tournament):
            return

        self.tournament = Tournament.load_tournament_by_id(interaction.guild.id, self.tournament.id) # update tournament info

        winner_view = Select_Winner_View(self.tournament, self.match_id)
        await interaction.response.send_message(f"An Admin may now select the winner(s) of the match.", view=winner_view)

    @discord.ui.button(label="➕ Add Reserve", style=discord.ButtonStyle.blurple, custom_id="add_reserve_button")
    async def add_reserve(self, button: discord.ui.Button, interaction: discord.Interaction):
        # Check if the user has the admin role or is a server admin
        if not await check_tournament_admin(interaction, self.tournament):
            return
        
        # Defer as it could take a while with more players registered
        await interaction.response.defer()

        # Update tournament data
        self.tournament = Tournament.load_tournament_by_id(interaction.guild.id, self.tournament.id)

        # Add first reserve in the list to match
        if self.tournament.reserves:
            if len(self.tournament.late_checkin) > 0:
                reserve = self.tournament.late_checkin[0]
            else:
                reserve = self.tournament.reserves[0]
            success = await add_player_to_match(interaction=interaction, t=self.tournament, match_id=self.match_id, player=reserve)
            if success:
                if interaction.response.is_done():
                    await interaction.followup.send(f"Reserve '{reserve}' added to match successfully.", ephemeral=True)
                else:
                    await interaction.response.send_message(f"Reserve '{reserve}' added to match successfully.", ephemeral=True)
            else:
                if interaction.response.is_done():
                    await interaction.followup.send(f"Failed to add reserve '{reserve}' to match.", ephemeral=True)
                else:
                    await interaction.response.send_message(f"Failed to add reserve '{reserve}' to match.", ephemeral=True)
        else:
            if interaction.response.is_done():
                await interaction.followup.send("No reserves available to add.", ephemeral=True)
            else:
                await interaction.response.send_message("No reserves available to add.", ephemeral=True)

    @discord.ui.button(label="⏩ Transfer Player", style=discord.ButtonStyle.blurple, custom_id="transfer_player_button")
    async def transfer_player(self, button: discord.ui.Button, interaction: discord.Interaction):
        # Check if the user has the admin role or is a server admin
        if not await check_tournament_admin(interaction, self.tournament):
            return
        
        # Update tournament data
        self.tournament = Tournament.load_tournament_by_id(interaction.guild.id, self.tournament.id)

        # Ephemeral drop-down menu to select one of the players in the match for a transfer
        transfer_view = Transfer_Player_View(self.tournament, self.match_id)
        await interaction.response.send_message("", view=transfer_view, ephemeral=True)

    @discord.ui.button(label="❌ Remove Player", style=discord.ButtonStyle.blurple, custom_id="remove_player_button")
    async def remove_player(self, button: discord.ui.Button, interaction: discord.Interaction):
        # Check if the user has the admin role or is a server admin
        if not await check_tournament_admin(interaction, self.tournament):
            return
        
        # Update tournament data
        self.tournament = Tournament.load_tournament_by_id(interaction.guild.id, self.tournament.id)
        
        # Ephemeral drop-down menu to select one of the players in the match to remove
        remove_view = Remove_Player_View(self.tournament, self.match_id)
        await interaction.response.send_message("", view=remove_view, ephemeral=True)

    @discord.ui.button(label="✅ Ready Check", style=discord.ButtonStyle.green, custom_id="ready_check_button")
    async def ready_up(self, button: discord.ui.Button, interaction: discord.Interaction):
        # Check if the user has the admin role or is a server admin
        if not await check_tournament_admin(interaction, self.tournament):
            return
           
        view, thread, match_players = await ready_check(interaction, self.tournament, self.match_id)
        
        if interaction.response.is_done():
            await interaction.followup.send("Ready check sent to all players.", ephemeral=True)
        else:            
            await interaction.response.send_message("Ready check sent to all players.", ephemeral=True)

        await not_ready_forfeit(self.tournament, interaction, view, thread, match_players)

class Transfer_Player_View(discord.ui.View):    
    def __init__(self, tournament, match_id):
        super().__init__(timeout=None)
        self.add_item(Transfer_Player_Menu(tournament, match_id))

class Transfer_Player_Menu(discord.ui.Select):
    def __init__(self, tournament: Tournament, match_id: str):
        self.tournament = tournament
        self.match_id = match_id

        match = next((m for m in self.tournament.matches if m["id"] == self.match_id), None)

        options = [
            discord.SelectOption(
                label=player, 
                description=f"Transfer {player} to another match")
            for player in match["players"]
        ]

        super().__init__(
            placeholder="Select a player to transfer...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):        
        # Get the selected player
        selected_player = self.values[0]
        
        modal = Transfer_Modal(self.tournament, selected_player, self.match_id)
        await interaction.response.send_modal(modal)

class Remove_Player_View(discord.ui.View):    
    def __init__(self, tournament, match_id):
        super().__init__(timeout=None)
        self.add_item(Remove_Player_Menu(tournament, match_id))

class Remove_Player_Menu(discord.ui.Select):
    def __init__(self, tournament: Tournament, match_id: str):
        self.tournament = tournament
        self.match_id = match_id

        match = next((m for m in self.tournament.matches if m["id"] == self.match_id), None)

        options = [
            discord.SelectOption(
                label=player, 
                description=f"Remove {player} from the match")
            for player in match["players"]
        ]

        super().__init__(
            placeholder="Select a player to remove...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):        
        selected_player = self.values[0]

        # Check if the user has the admin role or is a server admin
        if not await check_tournament_admin(interaction, self.tournament):
            return
        
        # Remove player from match
        success = await remove_player_from_match(interaction, self.tournament, self.match_id, selected_player)
        if success:
            await interaction.response.send_message(f"{selected_player} removed from Match {self.match_id}.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Failed to remove {selected_player} from Match {self.match_id}.", ephemeral=True)

# Modal for transferring player to another match. Collect new match id
class Transfer_Modal(discord.ui.Modal):
    def __init__(self, tournament, player, old_match_id):
        super().__init__(title="Edit Field Value")
        self.add_item(discord.ui.InputText(label=f"Player being transferred", value=player))
        self.add_item(discord.ui.InputText(label=f"Transfer {player} to: ", placeholder="Enter new match id"))
        self.tournament: Tournament = tournament
        self.player = player
        self.old_match_id = old_match_id

    async def callback(self, interaction: discord.Interaction):
        player = self.children[0].value
        new_match_id = self.children[1].value

        success = await add_player_to_match(interaction, self.tournament, new_match_id, player)

        if success:
            await interaction.response.send_message(f"{player} added to Match {new_match_id}.", ephemeral=True)
            await remove_player_from_match(interaction, self.tournament, self.old_match_id, player) # Remove player from old match
        else:
            await interaction.response.send_message(f"Failed to add {player} to Match {new_match_id}.", ephemeral=True)

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

        super().__init__(
            placeholder="Select the winner of the match.", 
            min_values=1, 
            max_values=(len(match["players"])), # Allow selecting multiple winners
            options=options)

    async def callback(self, interaction: discord.Interaction):
        async with tournament_lock:
            # Check if the user has the admin role or is a server admin
            if not await check_tournament_admin(interaction, self.tournament):
                return
            
            self.tournament = Tournament.load_tournament_by_id(interaction.guild.id, self.tournament.id)

            winners = [get_user_safe(interaction.guild, value) for value in self.values]
            mentions = ", ".join(winner.mention for winner in winners)

            await interaction.response.send_message(f"## Winners of this match: {mentions}")

            # Iterate through and find the corresponding match
            match = next(m for m in self.tournament.matches if m["id"] == self.match_id)
            match["winners"] = [winner.name for winner in winners] # Update the match with multiple winners
            self.tournament.save()
            
            # Handle tournament progression logic
            if self.tournament.curr_num_matches == 1:
                self.tournament.set_tournament_winner(", ".join(match["winners"]))
                self.tournament.save()
                await run_tournament(self.tournament, interaction)
            else:
                # Get tournament channel object
                tournament_channel = discord.utils.get(interaction.guild.text_channels, id=self.tournament.tournament_channel_id)
                # Check if all round winners have been selected
                if all_winners_selected(self.tournament):
                    await send_round_winners(interaction, self.tournament)
                    await tournament_channel.send("## We're ready for the next round! :fire:")

            # Disable to prevent multiple winners
            self.disabled = True
            if self.view:
                # Update the view and message
                for child in self.view.children:
                    if isinstance(child, discord.ui.Select):
                        child.disabled = True
                await interaction.message.edit(view=self.view)

class Ready_Check_View(discord.ui.View):    
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Ready_Check_Button())

# Allow players to show they're ready to start the match
class Ready_Check_Button(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Ready ✅", style=discord.ButtonStyle.green)
        self.clicked_users = set()

    async def callback(self, interaction: discord.Interaction):
        user_name = interaction.user.name

        # Check if the user has already clicked the button
        if user_name in self.clicked_users:
            await interaction.response.send_message(f"You've already clicked the button, {interaction.user.mention}.", ephemeral=True)
            return
        else:
            self.clicked_users.add(user_name)
            await interaction.response.send_message(f"{interaction.user.display_name} is ready!")

async def ready_check(interaction: discord.Interaction, tournament: Tournament, match_id: int):
    # Find the match, thread, and match players
    match = next(m for m in tournament.matches if m["id"] == match_id)
    thread = discord.utils.get(interaction.guild.threads, id=match["thread_id"])
    match_players = [player for player in match["players"]]
    
    view = Ready_Check_View()
    await thread.send(f"## Are you ready to start? @everyone", view=view, allowed_mentions=discord.AllowedMentions(everyone=True))

    return view, thread, match_players
        
async def not_ready_forfeit(tournament: Tournament, interaction: discord.Interaction, view: Ready_Check_View, thread: discord.Thread, match_players: list):   
    # Wait for 5 minutes
    await asyncio.sleep(300)

    # Tag players who did not click the ready button
    not_ready_players = [player for player in match_players if player not in view.children[0].clicked_users]

    # Convert player names to user objects
    not_ready_players = [get_user_safe(interaction.guild, player) for player in not_ready_players]

    # Send message to players who did not click the ready button
    if not_ready_players:
        not_ready_mentions = " ".join(player.mention for player in not_ready_players)
        await thread.send(f"## The following players are not ready: {not_ready_mentions}\n### You have 5 minutes to ready up, or forfeit the match.") 
        # If they are still not ready after 5 minutes, give option to remove them from the match
        asyncio.create_task(final_not_ready_forfeit(tournament, interaction, view, thread, match_players))
    else:
        await thread.send(f"## All players are ready! Let's start the match!")

async def final_not_ready_forfeit(tournament: Tournament, interaction: discord.Interaction, view: Ready_Check_View, thread: discord.Thread, match_players: list):
    # Wait for 5 minutes
    await asyncio.sleep(300)

    final_not_ready_list = [player for player in match_players if player not in view.children[0].clicked_users]

    if not final_not_ready_list:
        await thread.send(f"## All players are ready! Let's start the match!")
        return  # All players are ready
    
    # Get match_id
    match_id = next((m["id"] for m in tournament.matches if m["thread_id"] == thread.id), None)

    final_not_ready_users = [discord.utils.get(interaction.guild.members, name=player) for player in final_not_ready_list]
    final_mentions = " ".join(user.mention for user in final_not_ready_users if user)

    await thread.send (f"## ❌ The following players are still not ready: {final_mentions}\n")
    await thread.send (f"### Would you like to remove them from the match?")
    remove_view = Remove_Player_View(tournament, match_id)
    await thread.send("", view=remove_view)
    

###################################
# TOURNAMENT RUNNING VIEW SECTION #
###################################

# Admin buttons available after the tournament has started
class Tournament_Running_View(discord.ui.View):
    def __init__(self, tournament:Tournament):
        super().__init__(timeout=None)
        self.tournament: Tournament = tournament

    @discord.ui.button(label="🏁 Go to Next Round", style=discord.ButtonStyle.green, custom_id="next_round_button")
    async def go_to_next_round(self, button: discord.ui.Button, interaction: discord.Interaction):
        # Check if the user has the admin role or is a server admin
        if not await check_tournament_admin(interaction, self.tournament):
            return
        
        await run_tournament(self.tournament, interaction) # Start the next round of the tournament

        self.tournament = Tournament.load_tournament_by_id(interaction.guild.id, self.tournament.id) # Update tournament data

        # Refresh the view/buttons in the tournament channel
        tournament_channel = discord.utils.get(interaction.guild.text_channels, id=self.tournament.tournament_channel_id)
        embed = create_tournament_embed(self.tournament)
        new_view = Tournament_Running_View(self.tournament)
        msg = await tournament_channel.fetch_message(self.tournament.tournament_channel_msg_id)
        await msg.edit(embed=embed, view=new_view)

        if self.tournament.curr_num_matches == 1:
            await interaction.followup.send(f"## THE FINALS HAVE STARTED! :fire:")
        else:
            await interaction.followup.send(f"## ROUND {self.tournament.round} STARTED!")

    @discord.ui.button(label="➕ Add Player to Match", style=discord.ButtonStyle.blurple, custom_id="add_player_button")
    async def add_player(self, button: discord.ui.Button, interaction: discord.Interaction):
        # Check if the user has the admin role or is a server admin
        if not await check_tournament_admin(interaction, self.tournament):
            return
        
        # Modal requesting play name and match id. Will add new player to an existing match
        await interaction.response.send_modal(Add_Player_Modal(self.tournament))

    @discord.ui.button(label="🏅 Set Match Winner", style=discord.ButtonStyle.blurple, custom_id="set_match_winner_button")
    async def set_winner(self, button: discord.ui.Button, interaction: discord.Interaction):
        # Check if the user has the admin role or is a server admin
        if not await check_tournament_admin(interaction, self.tournament):
            return
        
        # Modal to select the match to set the winner for and the name of the winner
        await interaction.response.send_modal(Set_Winner_Modal(self.tournament))

    @discord.ui.button(label="📣 Announcement", style=discord.ButtonStyle.blurple, custom_id="announcement_button")
    async def send_announcement(self, button: discord.ui.Button, interaction: discord.Interaction):
        # Check if the user has the admin role or is a server admin
        if not await check_tournament_admin(interaction, self.tournament):
            return
                
        # Modal to collect user announcement, then send it to all active threads
        await interaction.response.send_modal(Announcement_Modal(self.tournament))

    @discord.ui.button(label="✅ Ready Check All Games", style=discord.ButtonStyle.blurple, custom_id="ready_check_all_button")
    async def ready_all(self, button: discord.ui.Button, interaction: discord.Interaction):
        # Check if the user has the admin role or is a server admin
        if not await check_tournament_admin(interaction, self.tournament):
            return

        # List to store view, thread, and match_players for each match
        ready_check_data = []   

        await interaction.response.defer()

        # Prepare list of coroutines for ready_check
        ready_check_coros = []
        for match in self.tournament.matches:
            thread = discord.utils.get(interaction.guild.threads, id=match["thread_id"])
            if not thread.locked:
                ready_check_coros.append(ready_check(interaction, self.tournament, match["id"]))

        # Run all ready checks concurrently
        ready_check_results = await asyncio.gather(*ready_check_coros)

        # Collect results into ready_check_data
        ready_check_data = [
            (view, thread, match_players)
            for (view, thread, match_players) in ready_check_results
        ]

        await interaction.followup.send("Ready check sent to all players.", ephemeral=True)

        # Wait 5 mins, then tag all players not ready yet in each active thread
        tasks = [
            not_ready_forfeit(self.tournament, interaction, view, thread, match_players)
            for view, thread, match_players in ready_check_data
        ]
        await asyncio.gather(*tasks)

    @discord.ui.button(label="⏳ Show Pending Matches", style=discord.ButtonStyle.blurple, custom_id="show_pending_matches_button")
    async def show_pending_matches(self, button: discord.ui.Button, interaction: discord.Interaction):
        # Update tournament data
        tournament: Tournament = Tournament.load_tournament_by_id(interaction.guild.id, self.tournament.id)

        # Filter matches to get only those from the current round
        last_round = max(int(match["id"].split('-')[0][1:]) for match in tournament.matches)# Determine the last round number
        # Filter matches to get only those from the last round
        last_round_matches = [match for match in tournament.matches if match["id"].startswith(f"R{last_round}-")]
        # Create a list of pending matches
        pending_matches_list = "\n".join([f"**{match['id']}**\n{'\n'.join(match['players'])}" for match in last_round_matches if not match["winners"]])
        # Send the list of pending matches to the tournament channel
        if pending_matches_list:
            await interaction.response.send_message(f"## ⏳Pending Matches:\n{pending_matches_list}", ephemeral=True)
        else:
            await interaction.response.send_message("## All winners have been selected. No pending matches found.", ephemeral=True)

# Add a player to a match while the tournament is running
async def add_player_to_match(interaction: discord.Interaction, t: Tournament, match_id: int, player: str):
    # Update tournament data
    tournament = Tournament.load_tournament_by_id(interaction.guild.id, t.id)

    # Get player user object
    user = get_user_safe(interaction.guild, player)
    
    if not t_debug.TOURNAMENT_DEBUG_MODE and not user:
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
                if not t_debug.is_dummy_player(player):
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

# Modal for adding new player to match
class Add_Player_Modal(discord.ui.Modal):
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

# Set the winner of a match while the tournament is running
async def set_match_winner(interaction, tournament: Tournament, match_id: int, player: str):

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

# Modal for setting match winner
class Set_Winner_Modal(discord.ui.Modal):
    def __init__(self, tournament: Tournament):
        super().__init__(title="Add Player to Match")
        self.tournament = tournament
        self.add_item(discord.ui.InputText(label="Player Name"))
        self.add_item(discord.ui.InputText(label="match_id"))
    
    async def callback(self, interaction: discord.Interaction):
        player = self.children[0].value
        match_id = self.children[1].value
        tournament: Tournament = Tournament.load_tournament_by_id(interaction.guild.id, self.tournament.id) # update tournament data from file
        success = await set_match_winner(interaction, tournament, match_id, player)

        if success:
            # Check if it's the last match of the tournament
            if tournament.curr_num_matches == 1:
                tournament.set_tournament_winner(player)
                tournament.save()
                await run_tournament(tournament, interaction)
            else:
                # Fetch tournament channel object
                tournament_channel = discord.utils.get(interaction.guild.text_channels, id=tournament.tournament_channel_id)
                # Check if all round winners have been selected
                if all_winners_selected(tournament):
                    await send_round_winners(interaction, tournament)
                    await tournament_channel.send("## We're ready for the next round! :fire:")
                await interaction.response.send_message(f"{player} set as {match_id} winner.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Failed to set {player} as {match_id} winner.", ephemeral=True)

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
                    new_view = Start_Match_View(match["id"], updated_tournament)
                    await thread_msg.edit(view=new_view)
                except discord.NotFound:
                    continue



###############################
# AUXILIARY FUNCTIONS SECTION #
###############################

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

# Modal to collect user input(announcement), then send it to all active threads
class Announcement_Modal(discord.ui.Modal):
    def __init__(self, tournament: Tournament):
        super().__init__(title="Send Announcement")
        self.tournament = tournament
        self.add_item(discord.ui.InputText(
            label="Announcement Message", 
            style=discord.InputTextStyle.paragraph, 
            placeholder="Message...",
            required=True))

    async def callback(self, interaction: discord.Interaction):
        message = self.children[0].value
        await interaction.response.send_message("Sending announcement to all threads...", ephemeral=True)
        
        threads = [discord.utils.get(interaction.guild.threads, id=match["thread_id"])
            for match in self.tournament.matches if match.get("thread_id")]
        
        # Send concurrently if thread not locked
        await asyncio.gather(*(thread.send(message) for thread in threads if thread and not thread.locked))
        await interaction.followup.send(f"Announcement sent to all active game threads.", ephemeral=True)