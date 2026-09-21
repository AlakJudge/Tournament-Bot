
import discord
from tournament import Tournament
from db import record_leaderboard_result
from utils.debug import is_debug_mode_enabled, is_dummy_player, get_mention_safe

async def record_tournament_conclusion(tournament: Tournament, winning_match: dict, interaction: discord.Interaction):
    if tournament.stats_recorded:
        return
    #if is_debug_mode_enabled():
    #    return
    
    #participants = {p for m in tournament.matches for p in m["players"] if not is_dummy_player(p)}
    participants = {p for m in tournament.matches for p in m["players"]}
    if len(participants) < 10:
        return

    tournament.stats_recorded = True
    
    game_key = tournament.game.strip().lower()
    winners = [p for p in winning_match["winners"] if not is_dummy_player(p)]
    finalists = [p for p in winning_match["players"] if p not in winning_match["winners"] and not is_dummy_player(p)]
    other_participants = participants - set(winners) - set(finalists)
    
    for player in winners:
        record_leaderboard_result(tournament.guild_id, game_key, tournament.game, player, wins=1, tournaments_played=1)
    for player in finalists:
        record_leaderboard_result(tournament.guild_id, game_key, tournament.game, player, finals=1, tournaments_played=1)
    for player in other_participants:
        record_leaderboard_result(tournament.guild_id, game_key, tournament.game, player, tournaments_played=1)
    
    tournament.save()
    
    tournament_channel = discord.utils.get(interaction.guild.text_channels, id=tournament.tournament_channel_id)
    if tournament_channel:
        embed = discord.Embed(title=f"📊 Leaderboard Updated — {tournament.game}", color=discord.Color.blurple())
        embed.add_field(name="🥇 Championship", value=", ".join(get_mention_safe(interaction.guild, p) for p in winners), inline=False)
        if finalists:
            embed.add_field(name="🥈 Reached the Final", value=", ".join(get_mention_safe(interaction.guild, p) for p in finalists), inline=False)
        if other_participants:
            embed.add_field(name="✅ Participated", value=", ".join(get_mention_safe(interaction.guild, p) for p in sorted(other_participants)), inline=False)
        await tournament_channel.send(embed=embed)