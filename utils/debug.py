from tournament import Tournament
import discord

# Dummy user for testing
class DummyUser:
    def __init__(self, name, user_id=None):
        self.name = name
        self.display_name = name
        self.id = user_id or hash(name) % 1000000  # Generate fake ID from name
        self.mention = f"<@{self.id}>"
        self.bot = False
    
    def __str__(self):
        return self.name

# Tournament debug mode flag
TOURNAMENT_DEBUG_MODE = False

# Enable/disable debug mode globally
def set_debug_mode(enabled: bool):
    global TOURNAMENT_DEBUG_MODE
    TOURNAMENT_DEBUG_MODE = enabled
    
def is_debug_mode_enabled():
    return TOURNAMENT_DEBUG_MODE

# Get Discord user object or dummy user based on debug mode
def get_user_safe(guild, player_name):
    if is_debug_mode_enabled():
        # In debug mode, check if it's a dummy player (starts with "dummy_")
        if player_name.startswith("dummy_"):
            return DummyUser(player_name)
    
    # Try to get real Discord user
    user = discord.utils.get(guild.members, name=player_name)
    
    if user:
        return user
    else:
        return None

# Get user mention or fallback string
def get_mention_safe(guild, player_name):
    user = get_user_safe(guild, player_name)
    if user and hasattr(user, 'mention'):
        return user.mention
    return f"**{player_name}**"  # Fallback to bold name

# Get mentions for multiple players
def get_mentions_safe(guild, player_names):
    mentions = [get_mention_safe(guild, name) for name in player_names]
    return ", ".join(mentions)

# Add dummy players for testing
async def add_dummy_players(tournament: Tournament, count: int):
    if not TOURNAMENT_DEBUG_MODE:
        return False, "Debug mode not enabled"
    
    added = 0
    current_dummy_count = 0
    
    # Find existing dummy players to avoid duplicates
    for player in tournament.players:
        if is_dummy_player(player):
            current_dummy_count += 1
    
    for i in range(current_dummy_count, current_dummy_count + count):
        dummy_name = f"dummy_player_{i+1:03d}"
        
        # Add to players if space available
        if len(tournament.players) < tournament.player_cap:
            if dummy_name not in tournament.players:
                tournament.players.append(dummy_name)
                added += 1
        # Add to reserves if players full
        elif dummy_name not in tournament.reserves:
            tournament.reserves.append(dummy_name)
            added += 1

    
    tournament.save()
    return True, f"Added {added} dummy players"

# Check if a player name is a dummy player
def is_dummy_player(player_name: str) -> bool:
    return player_name.startswith("dummy_")

# Validate that a player is a real Discord user (not dummy)
def validate_real_user(guild, player_name: str) -> bool:
    if TOURNAMENT_DEBUG_MODE and is_dummy_player(player_name):
        return True  # Allow dummy players in debug mode
    
    user = discord.utils.get(guild.members, name=player_name)
    return user is not None

# Remove all dummy players from tournament
async def clean_dummy_players(tournament: Tournament):
    original_players = len(tournament.players)
    original_reserves = len(tournament.reserves)
    
    tournament.players = [p for p in tournament.players if not is_dummy_player(p)]
    tournament.reserves = [r for r in tournament.reserves if not is_dummy_player(r)]
    
    removed = (original_players - len(tournament.players)) + (original_reserves - len(tournament.reserves))
    tournament.save()
    
    return removed