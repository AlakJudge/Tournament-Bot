import json
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
json_file_path = os.path.join(current_dir, "tournaments.json")

class Tournament:
    def __init__(self, id, name, game, date, time, date_time, prize, player_cap=None, thread_msg=None, reg_status="Closed", admin_role=None, participants_role=None, round=0, 
                 reg_channel=None, reg_msg_id=None, admin_msg_channel_id=None, admin_msg_id=None, owner=None, tournament_channel_id=None, tournament_channel_msg_id=None, 
                 participants_channel_id=None, curr_num_matches=None, players=None, reserves=None, tournament_winner=None, matches=None):
        self.id = id
        self.reg_channel = reg_channel
        self.reg_msg_id = reg_msg_id
        self.reg_status = reg_status
        self.admin_msg_channel_id = admin_msg_channel_id
        self.admin_msg_id = admin_msg_id
        self.tournament_channel_id = tournament_channel_id
        self.tournament_channel_msg_id = tournament_channel_msg_id
        self.participants_channel_id = participants_channel_id
        self.curr_num_matches = curr_num_matches
        self.name = name
        self.game = game
        self.date = date
        self.time = time
        self.date_time = date_time
        self.prize = prize
        self.player_cap = player_cap
        self.thread_msg = thread_msg
        self.admin_role = admin_role
        self.owner = owner
        self.participants_role = participants_role
        self.round = round
        self.players = players or []
        self.reserves = reserves or []
        self.matches = matches or []
        self.tournament_winner = tournament_winner or ""

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

    # Restart the tournament with basic info and participants
    def restart(self):
        self.reg_msg_id = None
        self.tournament_channel_id = None
        self.tournament_channel_msg_id = None
        self.participants_channel_id = None
        self.curr_num_matches = 0
        self.thread_msg = None
        self.round = 0
        self.matches = []
        self.tournament_winner = ""

    # Save the tournament details to the json file
    def save(self):
        # Get existing tournaments
        tournaments = Tournament.load_all_tournaments()

        # Update existing tournament or add new one
        updated = False

        if tournaments:
            for t in tournaments:
                if t.id == self.id:
                    t.reg_channel = self.reg_channel
                    t.reg_msg_id = self.reg_msg_id
                    t.admin_msg_channel_id = self.admin_msg_channel_id
                    t.admin_msg_id = self.admin_msg_id
                    t.reg_status = self.reg_status
                    t.tournament_channel_id = self.tournament_channel_id
                    t.tournament_channel_msg_id = self.tournament_channel_msg_id
                    t.participants_channel_id = self.participants_channel_id
                    t.curr_num_matches = self.curr_num_matches
                    t.name = self.name
                    t.game = self.game
                    t.date = self.date
                    t.time = self.time
                    t.date_time = self.date_time
                    t.prize = self.prize
                    t.player_cap = self.player_cap
                    t.thread_msg = self.thread_msg
                    t.admin_role = self.admin_role
                    t.owner = self.owner
                    t.participants_role = self.participants_role
                    t.round = self.round
                    t.players = self.players
                    t.reserves = self.reserves
                    t.matches = self.matches
                    t.tournament_winner = self.tournament_winner
                    updated = True

        # Append to file if it's a new tournament
        if not updated:
            tournaments.append(self)

        with open(json_file_path, "w") as file:
            json.dump([t.__dict__ for t in tournaments], file, indent=4)
    
    # Save all tournaments to JSON
    @staticmethod
    def save_all(tournaments):
        with open(json_file_path, "w") as file:
            json.dump([t.__dict__ for t in tournaments], file, indent=4)
    
    @staticmethod
    def load_all_tournaments():
        tournaments = []
        if os.path.exists(json_file_path):
            try:
                with open(json_file_path, "r") as file:
                    data = json.load(file)
                    for item in data:
                        tournaments.append(
                            Tournament(
                                id=item["id"],
                                reg_channel=item["reg_channel"],
                                reg_msg_id=item["reg_msg_id"],
                                reg_status=item["reg_status"],
                                admin_msg_channel_id=item.get("admin_msg_channel_id"),
                                admin_msg_id=item["admin_msg_id"],
                                tournament_channel_id=item["tournament_channel_id"],
                                tournament_channel_msg_id=item["tournament_channel_msg_id"],
                                participants_channel_id=item["participants_channel_id"],
                                curr_num_matches=item["curr_num_matches"],
                                name=item["name"],
                                game=item["game"],
                                date=item["date"],
                                time=item["time"],
                                date_time=item["date_time"],
                                prize=item["prize"],
                                player_cap=item.get("player_cap"),
                                thread_msg=item.get("thread_msg"),
                                admin_role=item["admin_role"],
                                owner=item["owner"],
                                participants_role=item["participants_role"],
                                round=item.get("round", 0),
                                players=item["players"],
                                reserves=item["reserves"],
                                matches=item["matches"],
                                tournament_winner=item.get("tournament_winner", "")
                            )
                        )

            except json.JSONDecodeError:
                print("File empty or invalid")
        else:
            print("File doesn't exist")
        return tournaments

    @staticmethod
    def load_tournament_by_name(tournament_name):
        tournaments = Tournament.load_all_tournaments()
        for t in tournaments:
            if t.name.lower() == tournament_name.lower():
                return t

        return None
    
    @staticmethod
    def delete_tournament(id):
        tournaments = Tournament.load_all_tournaments()
        tournaments = [t for t in tournaments if t.id != id]
        Tournament.save_all(tournaments)