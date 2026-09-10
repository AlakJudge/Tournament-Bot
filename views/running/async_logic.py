from random import shuffle
from math import ceil
import asyncio
import time

import discord

from tournament import Tournament
from utils.helpers import parse_time_string
from utils.debug import  get_mention_safe
from views.running.logic import get_round_winners, set_brackets

scheduled_round_deadline_tasks = {} 

class setup_async_mode(discord.ui.Modal):
    def __init__(self, tournament:Tournament) -> None:
        super().__init__(title="Running Details", timeout=300)
        self.tournament = tournament

        self.add_item(discord.ui.InputText(label="Max players per game?", placeholder="Cannot be higher than 6."))
        self.add_item(discord.ui.InputText(label="Minimum players in each game?", placeholder=f"Cannot be lower than 2 and cannot be higher than the max players per game."))
        self.add_item(discord.ui.InputText(label="Time limit per round?", placeholder="e.g., '2h', '5m', '30s'"))

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

        self.submitted = True
        
        # Save the async configuration to the tournament object
        self.tournament.async_config = {
            "min_players_per_match": self.min_players_per_match,
            "max_players_per_match": self.max_players_per_match,
            "round_deadline_seconds": self.round_deadline_seconds
        }

        await interaction.response.send_message(
            f"You've selected:\n"
            f"- Max Players per Game: {self.max_players_per_match}\n"
            f"- Min Players per Game: {self.min_players_per_match}\n"
            f"- Time Limit per Round: {self.children[2].value}", ephemeral=True)

# Keep table count within the range of min and max players per game
def valid_table_count_range(n: int, min_size: int, max_size: int):
    if n < min_size:
        return None
    low = max(1, ceil(n / max_size))
    high = n // min_size
    
    return (low, high) if low <= high else None

def compute_bye_count_and_table_count(total: int, max_size: int, min_size: int) -> tuple[int, int]:
        for bye_count in range(0, max_size):
            seated = total - bye_count
            table_range = valid_table_count_range(seated, min_size, max_size)
            
            if table_range is not None:
                return bye_count, table_range[0]  # Fewest tables possible with the given bye_count
            
        return 0, 1 # If no valid configuration is found, return 0 byes and 1 table as a fallback (edge case)        
    
def select_bye_players(pool: list[str], bye_count: int, bye_history: dict) -> list[str]:
    if bye_count <= 0:
        return []
    
    candidates = pool.copy()
    shuffle(candidates)
    candidates.sort(key=lambda player: bye_history.get(player, 0))
    return candidates[:bye_count]

def distribute_evenly(players: list[str], num_tables: int) -> list[int]:
    total = len(players)
    base = total // num_tables
    remainder = total % num_tables
    games = [base] * num_tables
    
    for i in range(remainder):
        games[i] += 1
    
    return games

async def run_async_round(tournament: Tournament, interaction: discord.Interaction):
    tournament: Tournament = Tournament.load_tournament_by_id(interaction.guild.id, tournament.id)
    tournament_channel = discord.utils.get(interaction.guild.text_channels, id=tournament.tournament_channel_id)

    pool = tournament.players if tournament.round == 0 else get_round_winners(tournament)
    
    participant_role = discord.utils.get(interaction.guild.roles, name=tournament.participants_role)
    if  not interaction.response.is_done():
        await interaction.response.defer(ephemeral=True)
    await tournament_channel.send(f"Running round {tournament.round + 1} with {len(pool)} participants...", delete_after=10)
    
    if len(pool) <= 1:
        if pool:
            tournament.set_tournament_winner(pool[0])
            tournament.save()
            await tournament_channel.send(f"# The winner of '{tournament.name}' is {get_mention_safe(interaction.guild, tournament.tournament_winner)}! CONGRATULATIONS! :tada::tada:\n"
                                                f"Thank you all {participant_role.mention}s for attending and being awesome. See you next time! :fire:")
        return
    
    tournament.next_round()
            
    max_size = tournament.async_config["max_players_per_match"]
    min_size = tournament.async_config["min_players_per_match"]
    bye_count, num_tables = compute_bye_count_and_table_count(len(pool), max_size, min_size)
    
    shuffle(pool)
    bye_players = select_bye_players(pool, bye_count, tournament.bye_history)
    remaining = [p for p in pool if p not in bye_players]
    
    games = distribute_evenly(remaining, num_tables)
    await set_brackets(
        interaction, 
        tournament, 
        precomputed_games=games, 
        t_players=remaining, 
        is_final_round=(num_tables == 1 and bye_count == 0)
        )
    
    # Bye entries are appended after set_brackets to ensure they are not included in the current round's matches
    for player in bye_players:
        match_id = f"R{tournament.round}-G{len(tournament.matches) + 1}"
        tournament.matches.append({
            "id": match_id,
            "players": [player],
            "winners": [player],
            "votes": {},
            "have_voted": [],
            "vote_status": "confirmed",
            "thread_id": None,
            "thread_msg_id": None,
            "is_bye": True
        })
        tournament.bye_history[player] = tournament.bye_history.get(player, 0) + 1
        
    tournament.curr_num_matches = num_tables + bye_count
    tournament.save()
    await schedule_round_deadline(tournament, interaction)
            
            
async def schedule_round_deadline(tournament: Tournament, interaction: discord.Interaction, delay: float = None):
    await cancel_round_deadline(tournament.id) 
    
    if delay is None:
        delay = tournament.async_config["round_deadline_seconds"]
        tournament.async_config["round_deadline_at"] = time.time() + delay
        tournament.save()
        
    task = asyncio.create_task(round_deadline_sweep(tournament, interaction, delay, tournament.round))
    scheduled_round_deadline_tasks[tournament.id] = task
    
async def cancel_round_deadline(tournament_id):
    task = scheduled_round_deadline_tasks.get(tournament_id, None)
    if task:
        task.cancel()
        
async def round_deadline_sweep(tournament: Tournament, interaction: discord.Interaction, delay: float, round_to_check: int):
    await asyncio.sleep(delay)
    
    tournament: Tournament = Tournament.load_tournament_by_id(interaction.guild.id, tournament.id)
    if tournament.round != round_to_check:
        return  # Round has changed, no action needed
    
    round_matches = [m for m in tournament.matches if m["id"].startswith(f"R{tournament.round}-")]
    pending = [m for m in round_matches if not m["winners"]]
    if not pending:
        return  # All matches have winners, no action needed
    
    tournament_channel = discord.utils.get(interaction.guild.text_channels, id=tournament.tournament_channel_id)
    admin_role = discord.utils.get(interaction.guild.roles, name=tournament.admin_role)
    pending_list = "\n".join(f"- **{m['id']}**: {', '.join(m['players'])}" for m in pending)
    await tournament_channel.send(
        f"⏰ {admin_role.mention} Round {round_to_check}'s deadline has passed with matches still unresolved:\n\n"
        f"{pending_list}\n\nPlease set winners manually using each match thread's [🏅 Set Winner button]."
    )