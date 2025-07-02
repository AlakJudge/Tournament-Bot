import discord
from tournament import Tournament
from datetime import datetime, timedelta
import asyncio
import re

# Dictionary to hold scheduled notification tasks
scheduled_notification_tasks = {}

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
    if len(tournament.players) < tournament.player_cap and len(tournament.reserves) > 0:
        tournament.register_player(tournament.reserves[0])
        tournament.reserves.pop(0)
        tournament.save()
        return True
    return False

# Convert date and time to a Discord timestamp format and save it
async def unix_convert_date_time(interaction, date: str, time: str) -> str:
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
        parsed_time = datetime.strptime(time, "%H:%M")  # 24-hour format
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
            if interval_seconds >= 86400:
                label = f"{interval_seconds // 86400} days"
            elif interval_seconds >= 3600:
                label = f"{interval_seconds // 3600} hours"
            elif interval_seconds >= 60:
                label = f"{interval_seconds // 60} minutes"
            else:
                label = f"{interval_seconds} seconds"

            # Add the interval and label to the list that will be stored in the save file
            intervals_and_labels.append({"seconds": interval_seconds, "label": label})

            if interaction.response.is_done():
                await interaction.followup.send(f"Scheduled notification for {label} before the tournament.", ephemeral=True)
            else:
                await interaction.response.send_message(f"Scheduled notification for {label} before the tournament.", ephemeral=True)
            task = asyncio.create_task(send_notification(tournament, interaction, delay, label))
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

async def send_notification(tournament: Tournament, interaction: discord.Interaction, delay: float, interval: int):
    await asyncio.sleep(delay)  # Wait for the specified delay
    # Get participants role
    participant_role = discord.utils.get(interaction.guild.roles, name=f"({tournament.id}) Tournament Participant")
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
        return f"{seconds // 86400} days"
    elif seconds >= 3600:
        return f"{seconds // 3600} hours"
    elif seconds >= 60:
        return f"{seconds // 60} minutes"
    else:
        return f"{seconds} seconds"

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