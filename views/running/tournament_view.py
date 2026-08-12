import asyncio
import discord
from utils.helpers import check_tournament_admin
from views.management import create_tournament_embed
from views.running.logic import run_tournament
from views.running.match_views import Start_Match_View, ready_check, not_ready_forfeit, Set_Winner_Modal, Add_Player_Modal
from tournament import Tournament

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

    @discord.ui.button(label="➕ Add New Match", style=discord.ButtonStyle.blurple, custom_id="add_match_button")
    async def add_match(self, button: discord.ui.Button, interaction: discord.Interaction):
        # Check if the user has the admin role or is a server admin
        if not await check_tournament_admin(interaction, self.tournament):
            return
        
        tournament_channel = discord.utils.get(interaction.guild.text_channels, id=self.tournament.tournament_channel_id)
        admin_role = discord.utils.get(interaction.guild.roles, name=self.tournament.admin_role)
        
        new_match_id = f"R{self.tournament.round}-G{len(self.tournament.matches)+1}"
        thread = await tournament_channel.create_thread(
            name=f"Round {self.tournament.round} - Game {len(self.tournament.matches)+1}", 
            type=discord.ChannelType.private_thread,
            auto_archive_duration = 10080 # Hide after 1 week
            )
        
        new_match = {
            "id": new_match_id,
            "players": [],
            "winners": [],
            "votes": {},
            "have_voted": [],
            "vote_status": "pending",
            "thread_id": thread.id,
            "thread_msg_id": None,
            "is_bye": False
        }

        if not self.tournament.thread_msg:
            await thread.send("### Hello participants! Please, be respectful and follow the tournament rules!")
        else:
            await thread.send(self.tournament.thread_msg)
        
        start_match_view = Start_Match_View(new_match_id, self.tournament)
        start_match_view = await thread.send(f"Once the match is over, an Admin will press the button below to set the winner of the match.\n"
                                            f"*Tag {admin_role.mention} if you need help with anything*", view=start_match_view)
        await start_match_view.pin()

        # Save the message ID of the thread message with the view
        new_match["thread_msg_id"] = start_match_view.id

        self.tournament.matches.append(new_match)
        self.tournament.curr_num_matches += 1
        self.tournament.save()
        
        await interaction.response.send_message(f"New match {new_match_id} and thread created.", ephemeral=True)
    
    @discord.ui.button(label="❌ Remove Match", style=discord.ButtonStyle.red, custom_id="remove_match_button")
    async def remove_match(self, button: discord.ui.Button, interaction: discord.Interaction):
        # Check if the user has the admin role or is a server admin
        if not await check_tournament_admin(interaction, self.tournament):
            return
        
        await interaction.response.send_modal(Remove_Match_Modal(self.tournament))

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
        
class Remove_Match_Modal(discord.ui.Modal):
    def __init__(self, tournament: Tournament):
        super().__init__(title="Remove Match")
        self.tournament = tournament
        self.add_item(discord.ui.InputText(
            label="Match ID to Remove", 
            style=discord.InputTextStyle.short, 
            placeholder="R1-G1",
            required=True))

    async def callback(self, interaction: discord.Interaction):
        match_id_to_remove = self.children[0].value.strip()
        match_to_remove = next((match for match in self.tournament.matches if match["id"] == match_id_to_remove), None)
        
        if not match_to_remove:
            await interaction.response.send_message(f"No match found with ID {match_id_to_remove}.", ephemeral=True)
            return
        
        # Remove the match from the tournament
        self.tournament.matches.remove(match_to_remove)
        self.tournament.curr_num_matches -= 1
        self.tournament.save()
        
        # Also delete the thread associated with the match
        thread = discord.utils.get(interaction.guild.threads, id=match_to_remove["thread_id"])
        if thread:
            await thread.delete()
        
        await interaction.response.send_message(f"Match {match_id_to_remove} has been removed.", ephemeral=True)