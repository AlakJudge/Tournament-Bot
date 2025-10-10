from tournament import Tournament
import discord

class DummyInteraction:
    class DummyResponse:
        @staticmethod
        async def send_message(*args, **kwargs):
            pass  # Do nothing

        @staticmethod
        def is_done():
            return True  # Pretend the response is always done

    class DummyFollowup:
        @staticmethod
        async def send(*args, **kwargs):
            pass  # Do nothing

    def __init__(self, guild):
        self.guild = guild
        self.response = DummyInteraction.DummyResponse()
        self.followup = DummyInteraction.DummyFollowup()

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

def set_debug_mode(enabled: bool):
    """Enable/disable debug mode globally"""
    global TOURNAMENT_DEBUG_MODE
    TOURNAMENT_DEBUG_MODE = enabled

def get_user_safe(guild, player_name):
    """
    Get Discord user object or dummy user based on debug mode
    Returns: discord.Member or DummyUser or None
    """
    if TOURNAMENT_DEBUG_MODE:
        # In debug mode, check if it's a dummy player (starts with "dummy_")
        if player_name.startswith("dummy_"):
            return DummyUser(player_name)
    
    # Try to get real Discord user
    user = discord.utils.get(guild.members, name=player_name)
    
    if user:
        return user
    else:
        return None

def get_mention_safe(guild, player_name):
    """
    Get user mention or fallback string
    Returns: str (either mention or just the name)
    """
    user = get_user_safe(guild, player_name)
    if user and hasattr(user, 'mention'):
        return user.mention
    return f"**{player_name}**"  # Fallback to bold name

def get_mentions_safe(guild, player_names):
    """
    Get mentions for multiple players
    Returns: str (comma-separated mentions or names)
    """
    mentions = [get_mention_safe(guild, name) for name in player_names]
    return ", ".join(mentions)

# Add dummy players for testing
async def add_dummy_players(tournament: Tournament, count: int):
    if not TOURNAMENT_DEBUG_MODE:
        return False, "Debug mode not enabled"
    
    added = 0
    for i in range(count):
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

def is_dummy_player(player_name: str) -> bool:
    """Check if a player name is a dummy player"""
    return player_name.startswith("dummy_") or TOURNAMENT_DEBUG_MODE

def validate_real_user(guild, player_name: str) -> bool:
    """Validate that a player is a real Discord user (not dummy)"""
    if TOURNAMENT_DEBUG_MODE and is_dummy_player(player_name):
        return True  # Allow dummy players in debug mode
    
    user = discord.utils.get(guild.members, name=player_name)
    return user is not None

async def clean_dummy_players(tournament: Tournament):
    """Remove all dummy players from tournament"""
    original_players = len(tournament.players)
    original_reserves = len(tournament.reserves)
    
    tournament.players = [p for p in tournament.players if not is_dummy_player(p)]
    tournament.reserves = [r for r in tournament.reserves if not is_dummy_player(r)]
    
    removed = (original_players - len(tournament.players)) + (original_reserves - len(tournament.reserves))
    tournament.save()
    
    return removed