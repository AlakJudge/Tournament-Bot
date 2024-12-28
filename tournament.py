import json
import os

class Tournament:
    def __init__(self, id, reg_channel, name, game, date, time, round=1, players=None, winners=None, winner=None):
        self.id = id
        self.reg_channel = reg_channel
        self.name = name
        self.game = game
        self.date = date
        self.time = time
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

    #
    def set_winner(self, winner):
        self.winner = winner

    #
    def save(self):
        # Get existing tournaments
        tournaments = Tournament.load_all_tournaments()

        # Update existing tournament or add new one
        updated = False

        if tournaments:
            for t in tournaments:
                if t.id == self.id:
                    t.reg_channel = self.reg_channel
                    t.name = self.name
                    t.game = self.game
                    t.date = self.date
                    t.time = self.time
                    t.round = self.round
                    t.players = self.players
                    t.winners = self.winners
                    t.winner = self.winner
                    updated = True

        # Append to file if it's a new tournament
        if not updated:
            tournaments.append(self)

        # Save all tournaments to JSON
        with open("tournaments.json", "w") as file:
            json.dump([t.__dict__ for t in tournaments], file, indent=4)

    @staticmethod
    def save_all(tournaments):
        with open("tournaments.json", "w") as file:
            json.dump([t.__dict__ for t in tournaments], file, indent=4)
    
    @staticmethod
    def load_all_tournaments(file_path="Tournament-Bot\\tournaments.json"):
        tournaments = []
        if os.path.exists(file_path):
            try:
                with open(file_path, "r") as file:
                    data = json.load(file)
                    for item in data:
                        tournaments.append(
                            Tournament(
                                id=item["id"],
                                reg_channel=item["reg_channel"],
                                name=item["name"],
                                game=item["game"],
                                date=item["date"],
                                time=item["time"],
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

    def display(self):
        print()
        print(f"## TOURNAMENT - {self.name.upper()} ##")
        print(f"- ID: {self.id}")
        print(f"- Game: {self.game}")
        print(f"- Date: {self.date}")
        print(f"- Time: {self.time}")
        print(f"- Players Registered: {len(self.players)}")
        for i, player in enumerate(self.players, 1):
            print(f"{i}. {player}")
