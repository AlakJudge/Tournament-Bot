import discord
from tournament import Tournament
from datetime import datetime, time, timedelta
import asyncio
import aiohttp
import re


# Dictionary to hold scheduled notification tasks
scheduled_notification_tasks = {}
scheduled_checkin_tasks = {}

# Check if the user has the admin role or is a server admin
async def check_tournament_admin(interaction: discord.Interaction, tournament: Tournament):          
    admin_role = discord.utils.get(interaction.guild.roles, name=f"({tournament.id}) Tournament Admin")

    if not interaction.user.guild_permissions.administrator and admin_role not in interaction.user.roles:
        if not interaction.response.is_done():
            await interaction.response.send_message(f"Failed. Only Tournament Admins have permission to perform this action.", ephemeral=True)
        else:
            # If the response is already sent, use followup
            await interaction.followup.send(f"Failed. Only Tournament Admins have permission to perform this action.", ephemeral=True)
        return False
    return True

# Function to move the reserve on the first index to the players list and then move all reserves 1 index up.
async def move_reserve_to_player(tournament: Tournament):        
    if (len(tournament.players) < tournament.player_cap and len(tournament.reserves) > 0) or \
    tournament.get_checkin_status(): # Only move if there is space or if check-in is enabled
        tournament.register_player(tournament.reserves[0])
        tournament.reserves.pop(0)
        tournament.save()
        return True
    return False

async def move_players_to_reserve(tournament: Tournament, type: str = None):
    if type == "end_of_checkin":
        players_to_check = tournament.players.copy() # Avoiding iteration issues
        
        for player in players_to_check:
            if player not in tournament.checked_in and player not in tournament.late_checkin:
                tournament.players.remove(player)
                tournament.reserves.append(player)
    else:
        excess_count = len(tournament.players) - tournament.player_cap
        if excess_count > 0:
            for _ in range(excess_count):
                tournament.reserves.append(tournament.players.pop())
    tournament.save()
        
# Convert date and time to a Discord timestamp format and save it
async def unix_convert_date_time(interaction, date: str, time_str: str) -> str:
    # Validate date (DD/MM/YYYY or DDMMYYYY format)
    try:
        parsed_date = datetime.strptime(date, "%d/%m/%Y")
    except ValueError:
        try:
            parsed_date = datetime.strptime(date, "%d%m%Y")
        except ValueError:
            await interaction.response.send_message("Invalid date format. Please use 'DD/MM/YYYY'.", ephemeral=True)
            return
    
    # Validate time (24-hour format)
    try:
        parsed_time = datetime.strptime(time_str, "%H:%M")  # 24-hour format
    except ValueError:
        await interaction.response.send_message("Invalid time format. Please use HH:MM (24-hour format).", ephemeral=True)
        return

    combined_datetime = datetime.combine(parsed_date.date(), parsed_time.time())
    if combined_datetime <= datetime.now():
        await interaction.response.send_message("The date and time must be in the future. Please try again.", ephemeral=True)
        return
    
    unix_timestamp = int(combined_datetime.timestamp()) # Convert to Unix timestamp
    formatted_date_time = f"<t:{unix_timestamp}:F>" # Format: <t:unix_timestamp:F> for full date and time
    return formatted_date_time

# Function to send an announcement message to all active game threads
async def send_announcement(interaction: discord.Interaction, tournament: Tournament, message: str, type: str):
    if type == "threads":
        # Iterate through and find the match
        for match in tournament.matches:
            thread = discord.utils.get(interaction.guild.threads, id=match["thread_id"])
            if not thread.locked:
                await thread.send(f"{message}")
    elif type == "t_channel":
        # Send message to the tournament channel
        tournament_channel = interaction.guild.get_channel(tournament.tournament_channel_id)
        if tournament_channel:
            await tournament_channel.send(f"{message}")

async def schedule_custom_notifications(tournament: Tournament, interaction: discord.Interaction, intervals: list[int], startup: bool = False):
    if not startup: # Only clear notifications if this is not the startup process
        await cancel_scheduled_notifications(interaction.guild.id, tournament.id)
    
    # Convert the date_time field (Discord timestamp) to a datetime object
    start_time = datetime.fromtimestamp(int(tournament.date_time[3:-3]))
    now = datetime.now()

    # Check if the tournament has already started
    if start_time < now:
        await interaction.response.send_message("The tournament has already started. Cannot schedule notifications.", ephemeral=True)
        return

    # Sort intervals so notifications are scheduled in order
    intervals = sorted(intervals, reverse=True)

    tasks = []
    intervals_and_labels = []

    for interval_seconds in intervals:
        notify_time = start_time - timedelta(seconds=interval_seconds)
        delay = (notify_time - now).total_seconds()
        if delay > 0: # Only schedule if the time is in the future
            # Format a human-readable string for confirmation
            label = parse_seconds_to_human_readable(interval_seconds)

            # Add the interval and label to the list that will be stored in the save file
            intervals_and_labels.append({"seconds": interval_seconds, "label": label})

            if interaction.response.is_done():
                await interaction.followup.send(f"Scheduled notification for {label} before the tournament.", ephemeral=True)
            else:
                await interaction.response.send_message(f"Scheduled notification for {label} before the tournament.", ephemeral=True)
            task = asyncio.create_task(send_notification(tournament=tournament, interaction=interaction, delay=delay, interval=label))
            tasks.append(task)
        else:
            if interaction.response.is_done(): 
                await interaction.followup.send(f"Skipped notification for '{interval_seconds}' seconds (time already passed).", ephemeral=True)
            else:
                await interaction.response.send_message(f"Skipped notification for '{interval_seconds}' seconds (time already passed).", ephemeral=True)
        # Store the task in the scheduled_notification_tasks dictionary
        scheduled_notification_tasks[tournament.id] = tasks

    # Save intervals to tournament memory and file
    tournament.notification_intervals = intervals_and_labels
    tournament.save()

async def cancel_scheduled_notifications(guild_id, tournament_id):
    tasks = scheduled_notification_tasks.get(tournament_id, [])
    for task in tasks:
        task.cancel()
    scheduled_notification_tasks[tournament_id] = []

    # Get tournament, then clear the notification intervals
    tournaments = Tournament.load_all_tournaments(guild_id)
    tournament = next((t for t in tournaments if t.id == tournament_id), None)
    if tournament:
        tournament.notification_intervals = []  # Clear the notification intervals from file
        tournament.save() 

async def send_notification(tournament: Tournament, interaction: discord.Interaction, delay: float, interval: str, message: str = None, view: discord.ui.View = None, type: str = None, duration: str = None):
    await asyncio.sleep(delay)  # Wait for the specified delay

    participant_role = discord.utils.get(interaction.guild.roles, name=f"({tournament.id}) Tournament Participant")

    if type == "checkin_reminder":
        pass
    elif type == "checkin_start":
        # For check-in start, use the repeating message function
        duration_seconds = parse_time_string_reverse(duration)  # Convert duration back to seconds
        await keep_message_at_bottom(tournament, interaction, message, duration_seconds, view, type="checkin_start")
        return
    elif type == "checkin_end":
        tournament.checkin["ended"] = True
        await move_players_to_reserve(tournament, type="end_of_checkin")
    else:
        message = f"## 🚨 REMINDER {participant_role.mention} 🚨: The tournament '{tournament.name}' will begin in {interval}!"
    
    await send_announcement(interaction, tournament, message, "t_channel")

# Function to parse time strings like "30m", "2h", etc.
def parse_time_string(s):
    match = re.match(r"(\d+)([smhd])", s)
    if not match:
        return None
    value, unit = match.groups()
    value = int(value)
    if unit == "s":
        return value
    elif unit == "m":
        return value * 60
    elif unit == "h":
        return value * 3600
    elif unit == "d":
        return value * 86400
    return None

def parse_seconds_to_human_readable(seconds: int) -> str:
    if seconds >= 86400:
        return f"{seconds // 86400} day(s)"
    elif seconds >= 3600:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if minutes > 0:
            return f"{hours} hour(s) and {minutes} minute(s)"
        return f"{hours} hour(s)"        
    elif seconds >= 60:
        minutes = seconds // 60
        seconds = seconds % 60
        if seconds > 0:
            return f"{minutes} minute(s) and {seconds} second(s)"
        return f"{minutes} minute(s)"
    else:
        return f"{seconds} seconds"
    
def parse_time_string_reverse(duration_str: str) -> int:
    """Convert human readable time to seconds"""
    # Extract number from strings like "30 minutes", "2 hours", etc.
    import re
    match = re.search(r'(\d+)\s*(second|minute|hour|day)', duration_str)
    if match:
        value = int(match.group(1))
        unit = match.group(2)
        
        if unit.startswith('second'):
            return value
        elif unit.startswith('minute'):
            return value * 60
        elif unit.startswith('hour'):
            return value * 3600
        elif unit.startswith('day'):
            return value * 86400
    return 0

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
        
async def keep_message_at_bottom(tournament: Tournament, interaction: discord.Interaction, message: str, duration_seconds: int, view=None, type: str = None):
    """Send a message that gets deleted and resent every 30 seconds to keep it at the bottom"""
    tournament_channel = interaction.guild.get_channel(tournament.tournament_channel_id)
    if not tournament_channel:
        return
    
    remaining_time = duration_seconds
    
    # Send initial message
    current_message = await tournament_channel.send(message, view=view)

    # Calculate how many 30-second intervals we need
    intervals = duration_seconds // 30

    for _ in range(intervals):
        await asyncio.sleep(30)  # Wait 30 seconds
        remaining_time -= 30
        
        try:
            if remaining_time > 0:
                await current_message.delete()
        except discord.NotFound:
            pass  
        except discord.Forbidden:
            pass 
        
        # Update message with remaining time if needed
        if remaining_time > 0 and type == "checkin_start":
            # Update the duration in the message
            updated_message = f"## ✅ Tournament Check-in is now OPEN!\n"\
                f"Please check-in using the button below. You have **{parse_seconds_to_human_readable(remaining_time)}** to check-in."
            current_message = await tournament_channel.send(updated_message, view=view)


async def validate_image_url(url: str) -> bool:
    """Check if URL is accessible and points to an image"""
    try:
        # Basic format check first
        if not (url.startswith("http://") or url.startswith("https://")):
            return False
        
        async with aiohttp.ClientSession() as session:
            async with session.head(url, timeout=5) as response:
                # Check if URL is accessible
                if response.status != 200:
                    return False
                
                # Check if content type is an image
                content_type = response.headers.get('content-type', '').lower()
                return content_type.startswith('image/')
                
    except (aiohttp.ClientError, asyncio.TimeoutError):
        return False