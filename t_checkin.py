import discord
from tournament import Tournament
import asyncio
from datetime import datetime, timedelta
from t_utils import *

async def schedule_checkin(tournament: Tournament, interaction: discord.Interaction, timings: list[int]):
    participant_role = discord.utils.get(interaction.guild.roles, name=f"({tournament.id}) Tournament Participant")

    # Convert the date_time field (Discord timestamp) to a datetime object
    start_time = datetime.fromtimestamp(int(tournament.date_time[3:-3]))
    now = datetime.now()
    
    # Check if the tournament has already started
    if start_time < now:
        await interaction.response.send_message("The tournament has already started. Cannot schedule Tournament Check-in.", ephemeral=True)
        return

    reminder = timings[0]
    start = timings[1]
    duration = timings[2]

    checkin_tasks = []

    # Get reminder time in seconds
    reminder_notify_time = start_time - timedelta(seconds=reminder)
    reminder_delay = (reminder_notify_time - now).total_seconds()

    # Get start checkin time in seconds
    start_notify_time = start_time - timedelta(seconds=start)
    reminder_to_start_delay = (start_notify_time - reminder_notify_time).total_seconds()

    if reminder_delay > 0: # Only send if the time is in the future
        reminder_label = parse_seconds_to_human_readable(int(reminder))
        reminder_delay_label = parse_seconds_to_human_readable(int(reminder_delay))

        if interaction.response.is_done():
            await interaction.followup.send(f"Check-in reminder set to {reminder_label} before the tournament - In {reminder_delay_label}.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Check-in reminder set to {reminder_label} before the tournament - In {reminder_delay_label}.", ephemeral=True)


        message = f"## ⏰ CHECK-IN REMINDER {participant_role.mention} - Tournament Check-in will begin {reminder_label} before the tournament starts - In {parse_seconds_to_human_readable(int(reminder_to_start_delay))}!"\
                    "\nPlease check-in using the button that will become available at that time."
        
        task_reminder = asyncio.create_task(send_notification(tournament, interaction, reminder_delay, reminder_label, message, type=f"checkin_reminder"))
        checkin_tasks.append(task_reminder)

    start_delay = (start_notify_time - now).total_seconds()

    if start_delay > 0:
        start_label = parse_seconds_to_human_readable(int(start))
        start_delay_label = parse_seconds_to_human_readable(int(start_delay))
        duration_label = parse_seconds_to_human_readable(int(duration))

        if interaction.response.is_done():
            await interaction.followup.send(f"Check-in start set to {start_label} before the tournament - In {start_delay_label}. Players will have {duration_label} to check in.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Check-in start set to {start_label} before the tournament - In {start_delay_label}. Player will have {duration_label} to check in.", ephemeral=True)

        # Start check in task
        message = f"## ✅ {participant_role.mention} - Tournament Check-in is now OPEN!"\
                    f"\nPlease check-in using the button below. You have **{parse_seconds_to_human_readable(int(duration))}** to check-in."
        view = Checkin_View(message, tournament)

        task_start = asyncio.create_task(send_notification(tournament, interaction, start_delay, start_label, message, view, type=f"checkin_start", duration=duration_label))
        checkin_tasks.append(task_start)

        # End check in task
        message = f"## ⏳ {participant_role.mention} - Tournament Check-in is now CLOSED! Brackets will be generated shortly."\
                    f"\nIf you check-in from this moment on, you will be added to the 'Late Check-in' list, and might still be able to participate in the tournament."
        
        task_end = asyncio.create_task(send_notification(tournament, interaction, start_delay + duration, start_label, message, type=f"checkin_end"))
        checkin_tasks.append(task_end)

    # Store the tasks in the scheduled_checkin_tasks dictionary
    scheduled_checkin_tasks[tournament.id] = checkin_tasks

    tournament.save()

async def cancel_scheduled_checkin(tournament_id):
    tasks = scheduled_checkin_tasks.get(tournament_id, [])
    for task in tasks:
        task.cancel()
    scheduled_checkin_tasks[tournament_id] = []

async def keep_message_at_bottom(tournament: Tournament, interaction: discord.Interaction, message: str, duration_seconds: int):
    """Send a message that gets deleted and resent every 30 seconds to keep it at the bottom"""
    tournament_channel = interaction.guild.get_channel(tournament.tournament_channel_id)
    if not tournament_channel:
        return
    
    remaining_time = duration_seconds
    
    # Send initial message
    view = Checkin_View(message, tournament)
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
        if remaining_time > 0:
            # Update the duration in the message
            updated_message = f"## ✅ Tournament Check-in is now OPEN!\n"\
                f"Please check-in using the button below. You have **{parse_seconds_to_human_readable(remaining_time)}** to check-in."
            current_message = await tournament_channel.send(updated_message, view=view)

class Checkin_View(discord.ui.View):
    def __init__(self, message, tournament:Tournament):
        super().__init__()
        self.message = message
        self.tournament = tournament

    @discord.ui.button(label="Check-in", style=discord.ButtonStyle.green)
    async def checkin(self, button: discord.ui.Button,interaction: discord.Interaction):
        player = interaction.user.name

        # Update tournament data
        tournament: Tournament = Tournament.load_tournament_by_id(interaction.guild.id, self.tournament.id)

        await check_in_user(interaction, tournament)

    @discord.ui.button(label="Check-out", style=discord.ButtonStyle.red)
    async def checkout(self, button: discord.ui.Button,interaction: discord.Interaction):
        player = interaction.user.name

        # Update tournament data
        tournament: Tournament = Tournament.load_tournament_by_id(interaction.guild.id, self.tournament.id)

        # Check if the player is registered in the tournament
        if player not in tournament.players and player not in tournament.reserves:
            await interaction.response.send_message("You are not registered for this tournament.", ephemeral=True)
            return

        # Check if the player has already checked out
        if player not in tournament.checked_in and player not in tournament.late_checkin:
            await interaction.response.send_message("You have not checked in for this tournament.", ephemeral=True)
            return

        # Mark the user as checked out
        tournament.checkout_player(interaction.user.name)
        tournament.save()
        await interaction.response.send_message("You have successfully checked out of this tournament.", ephemeral=True)


async def check_in_user(interaction: discord.Interaction, tournament: Tournament):
    player = interaction.user.name
    
    # Update tournament data
    tournament: Tournament = Tournament.load_tournament_by_id(interaction.guild.id, tournament.id)
    
    # Check if the player is registered in the tournament
    if player not in tournament.players and player not in tournament.reserves:
        await interaction.response.send_message("You are not registered for this tournament.", ephemeral=True)
        return False
    # Check if the player has already checked in
    if player in tournament.checked_in or player in tournament.late_checkin:
        await interaction.response.send_message("You have already checked in for this tournament.", ephemeral=True)
        return False
    # Set the user as checked in
    if tournament.checkin["ended"]:
        tournament.late_checkin_player(player)
        await interaction.response.send_message("Check-in period has ended. You will be added to the 'Late Check-in' list.", ephemeral=True)
    else:
        tournament.checkin_player(player)
        await interaction.response.send_message("You have successfully checked in for this tournament.", ephemeral=True)
    
    tournament.save()
    return True