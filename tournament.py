import json
import os
from db import *

'''current_dir = os.path.dirname(os.path.abspath(__file__))
SERVERS_DIR = os.path.join(current_dir, "servers")
os.makedirs(SERVERS_DIR, exist_ok=True)'''

class Tournament:
    def __init__(self, id, name, game, date, time, date_time, prize, image=None, notification_intervals=None, checkin=None, player_cap=None, thread_msg=None, reg_status="Closed", admin_role=None, participants_role=None, round=0, 
                 reg_channel=None, reg_msg_id=None, admin_msg_channel_id=None, admin_msg_id=None, owner=None, tournament_channel_id=None, tournament_channel_msg_id=None, 
                 participants_channel_id=None, reserves_thread_id=None, curr_num_matches=None, players=None, checked_in=None, late_checkin=None, reserves=None, tournament_winner=None, matches=None, guild_id=None, archived=False):
        self.id = id
        self.reg_channel = reg_channel
        self.reg_msg_id = reg_msg_id
        self.reg_status = reg_status
        self.admin_msg_channel_id = admin_msg_channel_id
        self.admin_msg_id = admin_msg_id
        self.tournament_channel_id = tournament_channel_id
        self.tournament_channel_msg_id = tournament_channel_msg_id
        self.participants_channel_id = participants_channel_id
        self.reserves_thread_id = reserves_thread_id
        self.curr_num_matches = curr_num_matches
        self.name = name
        self.game = game
        self.date = date
        self.time = time
        self.date_time = date_time
        self.prize = prize
        self.image = image
        self.notification_intervals = notification_intervals or []
        self.checkin = checkin or {}
        self.player_cap = player_cap
        self.thread_msg = thread_msg
        self.admin_role = admin_role
        self.owner = owner
        self.participants_role = participants_role
        self.round = round
        self.players = players or []
        self.checked_in = checked_in or []
        self.late_checkin = late_checkin or []
        self.reserves = reserves or []
        self.matches = matches or []
        self.tournament_winner = tournament_winner or ""
        self.guild_id = guild_id
        self.archived = archived

    # Set registration channel
    def set_reg_channel(self, reg_channel):
        self.reg_channel = reg_channel

    def register_player(self, player):
        self.players.append(player)

    def unregister_player(self, player):
        if player in self.players:
            self.players.remove(player)

    def register_reserve(self, player):
        self.reserves.append(player)

    def unregister_reserve(self, player):     
        if player in self.reserves:
            self.reserves.remove(player)
    
    def checkin_player(self, player):
        self.checked_in.append(player)

    def late_checkin_player(self, player):
        self.late_checkin.append(player)

    def checkout_player(self, player):
        if player in self.checked_in:
            self.checked_in.remove(player)
        elif player in self.late_checkin:
            self.late_checkin.remove(player)

    # Edit tournament name
    def edit_name(self, new_name):
        self.name = new_name

    # Edit tournament game
    def edit_game(self, new_game):
        self.game = new_game

    # Edit tournament date
    def edit_date(self, new_date):
        self.date = new_date

    # Edit tournament time
    def edit_time(self, new_time):
        self.time = new_time

    # Edit tournament date_time
    def edit_date_time(self, new_date_time):
        self.date_time = new_date_time
        
    # Edit tournament prize
    def edit_prize(self, new_prize):
        self.prize = new_prize

    # Edit player cap
    def edit_player_cap(self, new_player_cap):
        self.player_cap = new_player_cap

    # Edit image
    def edit_image(self, new_image):
        self.image = new_image

    # Edit thread message
    def edit_thread_msg(self, new_thread_msg):
        self.thread_msg = new_thread_msg

    # Edit registration status
    def edit_reg_status(self, new_status):
        self.reg_status = new_status

    # Move tournament to the next round
    def next_round(self):
        self.round = self.round + 1

    # Set the winner of the tournament
    def set_tournament_winner(self, tournament_winner):
        self.tournament_winner = tournament_winner

    # Set check-in details
    def set_checkin(self, reminder, start, duration, status=False, ended=False):
        self.checkin = {
            "reminder": reminder,
            "start": start,
            "duration": duration,
            "status": status,
            "ended": ended
        }

    def get_checkin_status(self):
        return self.checkin.get("status", False)

    # Restart the tournament with basic info and participants
    def restart(self, restart_games_only=False):
        if not restart_games_only:
            self.reg_msg_id = None
            self.tournament_channel_id = None
            self.tournament_channel_msg_id = None
            self.participants_channel_id = None
            self.reserves_thread_id = None
            self.curr_num_matches = 0
            self.thread_msg = None
            self.checkin = {}
            self.checked_in = []
            self.late_checkin = []
        self.round = 0
        self.matches = []
        self.tournament_winner = ""

    # Save the tournament details to the json file
    def save(self):
        tournament_data = self.to_dict()
        update_tournament(self.guild_id, self.id, tournament_data)
    
    @staticmethod
    def load_all_tournaments(guild_id: int):
        tournaments_data = find_all_tournaments(guild_id)
        return [Tournament.from_dict(data) for data in tournaments_data]
    
    @staticmethod
    def load_all_tournaments_with_archived(guild_id: int):
        tournaments_data = find_all_tournaments(guild_id, include_archived=True)
        return [Tournament.from_dict(data) for data in tournaments_data]
    
    @staticmethod
    def load_tournament_by_id(guild_id, tournament_id):
        data = find_tournament_by_id(guild_id, tournament_id)
        if data:
            return Tournament.from_dict(data)
        return None

    @staticmethod
    def delete_tournament(guild_id, tournament_id):
        return delete_tournament_db(guild_id, tournament_id)

    @staticmethod
    def archive_tournament(guild_id, tournament_id):
        return archive_tournament_db(guild_id, tournament_id)

    @staticmethod
    def from_dict(data):
        # Create a Tournament object from a dictionary (from MongoDB)
        return Tournament(
            id=data.get("id"),
            name=data.get("name"),
            game=data.get("game"),
            date=data.get("date"),
            time=data.get("time"),
            date_time=data.get("date_time"),
            prize=data.get("prize"),
            image=data.get("image"),
            notification_intervals=data.get("notification_intervals", []),
            checkin=data.get("checkin", {}),
            player_cap=data.get("player_cap"),
            thread_msg=data.get("thread_msg"),
            reg_status=data.get("reg_status", "Closed"),
            admin_role=data.get("admin_role"),
            participants_role=data.get("participants_role"),
            round=data.get("round", 0),
            reg_channel=data.get("reg_channel"),
            reg_msg_id=data.get("reg_msg_id"),
            admin_msg_channel_id=data.get("admin_msg_channel_id"),
            admin_msg_id=data.get("admin_msg_id"),
            owner=data.get("owner"),
            tournament_channel_id=data.get("tournament_channel_id"),
            tournament_channel_msg_id=data.get("tournament_channel_msg_id"),
            participants_channel_id=data.get("participants_channel_id"),
            reserves_thread_id=data.get("reserves_thread_id"),
            curr_num_matches=data.get("curr_num_matches"),
            players=data.get("players", []),
            checked_in=data.get("checked_in", []),
            late_checkin=data.get("late_checkin", []),
            reserves=data.get("reserves", []),
            tournament_winner=data.get("tournament_winner", ""),
            matches=data.get("matches", []),
            guild_id=data.get("guild_id"),
            archived=data.get("archived", False)
        )

    def to_dict(self):
        # Convert Tournament object to dictionary (for MongoDB)
        return {
            "id": self.id,
            "name": self.name,
            "game": self.game,
            "date": self.date,
            "time": self.time,
            "date_time": self.date_time,
            "prize": self.prize,
            "image": self.image,
            "notification_intervals": self.notification_intervals,
            "checkin": self.checkin,
            "player_cap": self.player_cap,
            "thread_msg": self.thread_msg,
            "reg_status": self.reg_status,
            "admin_role": self.admin_role,
            "participants_role": self.participants_role,
            "round": self.round,
            "reg_channel": self.reg_channel,
            "reg_msg_id": self.reg_msg_id,
            "admin_msg_channel_id": self.admin_msg_channel_id,
            "admin_msg_id": self.admin_msg_id,
            "owner": self.owner,
            "tournament_channel_id": self.tournament_channel_id,
            "tournament_channel_msg_id": self.tournament_channel_msg_id,
            "participants_channel_id": self.participants_channel_id,
            "reserves_thread_id": self.reserves_thread_id,
            "curr_num_matches": self.curr_num_matches,
            "players": self.players,
            "checked_in": self.checked_in,
            "late_checkin": self.late_checkin,
            "reserves": self.reserves,
            "tournament_winner": self.tournament_winner,
            "matches": self.matches,
            "guild_id": self.guild_id,
            "archived": self.archived
    }