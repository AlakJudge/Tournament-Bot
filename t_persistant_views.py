from tournament import Tournament
from t_registration import Registration, kick_view
from t_admin_menu import T_Admin
from t_running import Tournament_Running_View, Start_Match_View
import re
import discord

async def restore_registration_view(bot):
    # Iterate through each guild the bot is in
    for guild in bot.guilds:
        for tournament in Tournament.load_all_tournaments(guild.id):
            if tournament.reg_msg_id:
                channel = guild.get_channel(tournament.reg_channel)
                if channel:
                    try:
                        await channel.fetch_message(tournament.reg_msg_id)
                        view = Registration(tournament)
                        bot.add_view(view, message_id=tournament.reg_msg_id)
                    except Exception as e:
                        print(f"Failed to restore registration view for tournament {tournament.id} in server {guild.id}: {e}")
                        tournament.reg_msg_id = None
                        tournament.reg_channel = None
                        tournament.save()
                else:
                    print(f"Registration channel {tournament.reg_channel} not found for tournament {tournament.id} in server {guild.id}")
                    tournament.reg_msg_id = None
                    tournament.reg_channel = None
                    tournament.save()

async def restore_admin_menu_view(bot):
    # Iterate through each guild the bot is in
    for guild in bot.guilds:
        for tournament in Tournament.load_all_tournaments(guild.id):
            if tournament.admin_msg_id and tournament.admin_msg_channel_id:  # Check both exist
                # Get the tournaments-lounge channel
                channel = guild.get_channel(tournament.admin_msg_channel_id)
                if channel:
                    try:
                        # Check if bot has access to the channel
                        permissions = channel.permissions_for(guild.me)
                        if not permissions.view_channel or not permissions.read_message_history:
                            print(f"Bot lacks permissions for admin channel {channel.id} in tournament {tournament.id}, server {guild.id}")
                            continue
                            
                        await channel.fetch_message(tournament.admin_msg_id)
                        view = T_Admin(tournament)
                        bot.add_view(view, message_id=tournament.admin_msg_id)
                    except discord.NotFound:
                        print(f"Admin message not found for tournament {tournament.id} in server {guild.id}")
                    except discord.Forbidden:
                        print(f"Bot lacks permissions to access admin message for tournament {tournament.id} in server {guild.id}")
                    except Exception as e:
                        print(f"Failed to restore admin menu view for tournament {tournament.id} in server {guild.id}: {e}")
                else:
                    print(f"Admin channel {tournament.admin_msg_channel_id} not found for tournament {tournament.id} in server {guild.id}")
                    tournament.admin_msg_id = None
                    tournament.admin_msg_channel_id = None
                    tournament.save()

async def restore_kick_views(bot):
    # Iterate through each guild the bot is in
    for guild in bot.guilds:
        for tournament in Tournament.load_all_tournaments(guild.id):
            if not tournament.participants_channel_id:
                continue

            channel = guild.get_channel(tournament.participants_channel_id)
            
            # Go through all messages in the channel and restore kick views in all messages
            if channel:
                try:
                    async for message in channel.history(limit=None):
                        # Find the username in the message content
                        match = re.search(r"<@!?(\d+)>", message.content)
                        if match:
                            user_id = int(match.group(1))
                            member = channel.guild.get_member(user_id)
                            player_name = member.name if member else None
                        view = kick_view(tournament, player_name)
                        bot.add_view(view, message_id=message.id)
                except Exception as e:
                    print(f"Failed to restore kick views for tournament {tournament.id} in server {guild.id}: {e}")

async def restore_tournament_channel_view(bot):
    # Iterate through each guild the bot is in
    for guild in bot.guilds:
        for tournament in Tournament.load_all_tournaments(guild.id):
            # Check if both channel and message IDs exist and are not None
            if tournament.tournament_channel_id and tournament.tournament_channel_msg_id:
                channel = guild.get_channel(tournament.tournament_channel_id)
                if channel:
                    try:
                        # Check if bot has access to the channel
                        permissions = channel.permissions_for(guild.me)
                        if not permissions.view_channel or not permissions.read_message_history:
                            print(f"Bot lacks permissions for tournament channel {channel.id} in tournament {tournament.id}")
                            continue
                            
                        await channel.fetch_message(tournament.tournament_channel_msg_id)
                        view = Tournament_Running_View(tournament)
                        bot.add_view(view, message_id=tournament.tournament_channel_msg_id)
                    except discord.NotFound:
                        print(f"Tournament message {tournament.tournament_channel_msg_id} not found for tournament {tournament.id} in server {guild.id}")
                        tournament.tournament_channel_id = None
                        tournament.tournament_channel_msg_id = None
                        tournament.save()
                    except discord.Forbidden:
                        print(f"Bot lacks permissions to access tournament message for server {guild.id}, tournament {tournament.id}")
                    except Exception as e:
                        print(f"Failed to restore tournament channel view for server {guild.id}, tournament {tournament.id}: {e}")
                else:
                    print(f"Tournament channel {tournament.tournament_channel_id} not found for tournament {tournament.id} (server: {guild.id})")
                    tournament.tournament_channel_id = None
                    tournament.tournament_channel_msg_id = None
                    tournament.save()

async def restore_threads_views(bot):
    # Iterate through each guild the bot is in
    for guild in bot.guilds:
        for tournament in Tournament.load_all_tournaments(guild.id):
            changed = False

            if not tournament.tournament_channel_id and not tournament.tournament_channel_msg_id:
                continue
            
            channel = guild.get_channel(tournament.tournament_channel_id)
            if channel:
                try:
                    for match in tournament.matches:
                        match_id = match.get("id")
                        thread_id = match.get("thread_id")
                        if not thread_id:
                            continue

                        thread = guild.get_channel(thread_id)  
                        if not thread:
                            match["thread_id"] = None
                            match["thread_msg_id"] = None
                            changed = True
                            continue

                        msg_id = match.get("thread_msg_id")
                        if msg_id:
                            view = Start_Match_View(match_id=match_id, tournament=tournament)
                            bot.add_view(view, message_id=msg_id)
                            print(f"Restored view for thread {thread_id} in tournament {tournament.id} in server {guild.id}")
                            
                except Exception as e:
                    print(f"Failed to restore threads views for tournament {tournament.id} in server {guild.id}: {e}")
                
                if changed:
                    tournament.save()
                    
            else:
                print(f"Tournament channel {tournament.tournament_channel_id} not found for tournament {tournament.id} in server {guild.id}")
                tournament.tournament_channel_id = None
                tournament.tournament_channel_msg_id = None
                tournament.save()

async def restore_all_views(bot):
    await restore_registration_view(bot)
    await restore_admin_menu_view(bot)
    await restore_kick_views(bot)
    await restore_tournament_channel_view(bot)
    await restore_threads_views(bot)