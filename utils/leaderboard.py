from tournament import Tournament
from db import record_leaderboard_result
from utils.debug import is_debug_mode_enabled, is_dummy_player

async def record_tournament_conclusion(tournament: Tournament, winning_match: dict):
    if tournament.stats_recorded:
        return
    if is_debug_mode_enabled():
        return
    
    participants = {p for m in tournament.matches for p in m["players"] if not is_dummy_player(p)}
    if len(participants) < 10:
        return

    tournament.stats_recorded = True
    
    game_key = tournament.game.strip().lower()
    winners = [p for p in winning_match["winners"] if not is_dummy_player(p)]
    finalists = [p for p in winning_match["players"] if p not in winning_match["winners"] and not is_dummy_player(p)]
    
    for player in winners:
        record_leaderboard_result(tournament.guild_id, game_key, tournament.game, player, wins=1, tournaments_played=1)
    for player in finalists:
        record_leaderboard_result(tournament.guild_id, game_key, tournament.game, player, finals=1, tournaments_played=1)
    for player in participants - set(winners) - set(finalists):
        record_leaderboard_result(tournament.guild_id, game_key, tournament.game, player, tournaments_played=1)
    
    tournament.save()