import discord

from tournament import Tournament
from utils.helpers import parse_time_string


class setup_async_mode(discord.ui.Modal):
    def __init__(self, tournament:Tournament) -> None:
        super().__init__(title="Running Details", timeout=300)
        self.tournament = tournament

        self.add_item(discord.ui.InputText(label="Max players per game?", placeholder="Cannot be higher than 6."))
        self.add_item(discord.ui.InputText(label="Minimum players in each game?", placeholder=f"Cannot be lower than 2 and cannot be higher than the max players per game."))
        self.add_item(discord.ui.InputText(label="Time limit per round?", placeholder="e.g., '2h', '5m', '30s'"))
        self.add_item(discord.ui.InputText(label="Time limit per game?", placeholder="e.g., '2h', '5m', '30s'"))

    async def callback(self, interaction: discord.Interaction):
        try:
            self.max_players_per_match = int(self.children[0].value)
            self.min_players_per_match = int(self.children[1].value)
        except ValueError:
            await interaction.response.send_message("Please enter valid integers for max and min players per game.", ephemeral=True)
            return
        
        if self.min_players_per_match < 2 or self.min_players_per_match > self.max_players_per_match:
            await interaction.response.send_message("Minimum players must be at least 2 and no higher than the max players per game.", ephemeral=True)
            return
        
        self.round_deadline_seconds = parse_time_string(self.children[2].value)
        if self.round_deadline_seconds is None:
            await interaction.response.send_message("Invalid time format for 'Time limit per round'. Use e.g. '2h', '5m', '30s'.", ephemeral=True)
            return
        
        self.match_deadline_seconds = parse_time_string(self.children[3].value)
        if self.match_deadline_seconds is None:
            await interaction.response.send_message("Invalid time format for 'Time limit per game'. Use e.g. '2h', '5m', '30s'.", ephemeral=True)
            return

        self.submitted = True
        
        # Save the async configuration to the tournament object
        self.tournament.async_config = {
            "max_players_per_match": self.max_players_per_match,
            "min_players_per_match": self.min_players_per_match,
            "round_deadline_seconds": self.round_deadline_seconds,
            "match_deadline_seconds": self.match_deadline_seconds
        }

        await interaction.response.send_message(
            f"You've selected:\n"
            f"- Max Players per Game: {self.max_players_per_match}\n"
            f"- Min Players per Game: {self.min_players_per_match}\n"
            f"- Time Limit per Round: {self.children[2].value}\n"
            f"- Time Limit per Game: {self.children[3].value}", ephemeral=True)
       