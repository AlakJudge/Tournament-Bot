import discord
from tournament import Tournament
from datetime import datetime, timedelta
import asyncio

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
    # Validate date (DD/MM/YYYY format)
    try:
        parsed_date = datetime.strptime(date, "%d/%m/%Y")
        if parsed_date <= datetime.now():
            await interaction.response.send_message("The date has to be in the future. Please try again.", ephemeral=True)
            return
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

async def schedule_notifications(tournament: Tournament, interaction: discord.Interaction, intervals: list[int] = [24, 2]):
    # Convert the date_time field (Discord timestamp) to a datetime object
    start_time = datetime.fromtimestamp(int(tournament.date_time[3:-3]))
    now = datetime.now()

    # Check if the tournament has already started
    if start_time < now:
        await interaction.response.send_message("The tournament has already started. Cannot schedule notifications.", ephemeral=True)
        return

    for interval in intervals:
        delay = (start_time - timedelta(hours=interval) - now).total_seconds()
        if delay > 0:
            if interaction.response.is_done():
                await interaction.followup.send(f"Scheduled notification for {interval} hours before the tournament.", ephemeral=True)
            else:
                await interaction.response.send_message(f"Scheduled notification for {interval} hours before the tournament.", ephemeral=True)
            asyncio.create_task(send_notification(tournament, interaction, delay, interval))

async def send_notification(tournament: Tournament, interaction: discord.Interaction, delay: float, interval: int):
    await asyncio.sleep(delay)  # Wait for the specified delay
    # Get participants role
    participant_role = discord.utils.get(interaction.guild.roles, name=f"({tournament.id}) Tournament Participant")
    message = f"## 🚨 REMINDER {participant_role.mention} 🚨: The tournament '{tournament.name}' will begin in {interval} hours!"
    await send_announcement(interaction, tournament, message, "t_channel")