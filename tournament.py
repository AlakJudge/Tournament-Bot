import json
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
json_file_path = os.path.join(current_dir, "tournaments.json")

class Tournament:
    def __init__(self, id, name, game, date, time, admin_role=None, round=1, 
                 reg_channel=None, reg_msg_id=None, admin_msg_id=None, tournament_channel_id=None, 
                 tournament_channel_msg_id=None, participants_channel_id=None, curr_num_matches=None, players=None, winners=None, winner=None):
        self.id = id
        self.reg_channel = reg_channel
        self.reg_msg_id = reg_msg_id
        self.admin_msg_id = admin_msg_id
        self.tournament_channel_id = tournament_channel_id
        self.tournament_channel_msg_id = tournament_channel_msg_id
        self.participants_channel_id = participants_channel_id
        self.curr_num_matches = curr_num_matches
        self.name = name
        self.game = game
        self.date = date
        self.time = time
        self.admin_role = admin_role
        self.round = round
        self.players = players or []
        self.winners = winners or []
        self.winner = winner or ""
    
    # Register new player
    def register_player(self, player):
        self.players.append(player)

    # Unregister player
    def unregister_player(self, player):
        if player in self.players:
            self.players.remove(player)

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

    # Move tournament to the next round
    def next_round(self):
        self.round = self.round + 1

    # Set the winner of the tournament
    def set_winner(self, winner):
        self.winner = winner

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
                    t.admin_msg_id = self.admin_msg_id
                    t.tournament_channel_id = self.tournament_channel_id
                    t.tournament_channel_msg_id = self.tournament_channel_msg_id
                    t.participants_channel_id = self.participants_channel_id
                    t.curr_num_matches = self.curr_num_matches
                    t.name = self.name
                    t.game = self.game
                    t.date = self.date
                    t.time = self.time
                    t.admin_role = self.admin_role
                    t.round = self.round
                    t.players = self.players
                    t.winners = self.winners
                    t.winner = self.winner
                    updated = True

        # Append to file if it's a new tournament
        if not updated:
            tournaments.append(self)

        # Save all tournaments to JSON
        with open(json_file_path, "w") as file:
            json.dump([t.__dict__ for t in tournaments], file, indent=4)

    @staticmethod
    def save_all(tournaments):
        with open("tournaments.json", "w") as file:
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
                                admin_msg_id=item["admin_msg_id"],
                                tournament_channel_id=item["tournament_channel_id"],
                                tournament_channel_msg_id=item["tournament_channel_msg_id"],
                                participants_channel_id=item["participants_channel_id"],
                                curr_num_matches=item["curr_num_matches"],
                                name=item["name"],
                                game=item["game"],
                                date=item["date"],
                                time=item["time"],
                                admin_role=item["admin_role"],
                                round=item.get("round", 1),
                                players=item["players"],
                                winners=item["winners"],
                                winner=item.get("winner", "")
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