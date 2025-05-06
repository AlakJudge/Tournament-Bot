import discord
from tournament import Tournament
from datetime import datetime

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
