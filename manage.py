from tournament import Tournament
import discord

# Where the admin will be able to create a new tournament
def create_tournament(name, reg_channel, game, date, time):
    
    tournaments = Tournament.load_all_tournaments()

    if tournaments:
        id = max([int(t.id) for t in tournaments]) + 1
    else:
        id = 1

    tournament = Tournament(id=id, reg_channel=reg_channel, name=name, game=game, date=date, time=time)
    tournament.save()

    return tournament