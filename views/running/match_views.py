import discord
import asyncio

from tournament import Tournament
from utils.helpers import check_tournament_admin
from utils.debug import get_user_safe
from views.running.logic import tournament_lock, run_tournament, add_player_to_match, remove_player_from_match, set_match_winner, all_winners_selected, send_round_winners

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
