import os
from pymongo import MongoClient

# Load .env file only if not in GitHub Actions environment
if os.getenv("GITHUB_ACTIONS") != "true":
    from dotenv import load_dotenv
    load_dotenv()

# Use your MongoDB connection string from your cluster
MONGODB_URI = os.getenv("MONGODB_URI")
client = MongoClient(MONGODB_URI)
db = client["Servers"] 

def get_tournaments_collection(guild_id):
    collection_name = f"tournaments_{guild_id}"
    return db[collection_name]

def insert_tournament(guild_id, tournament_data):
    collection = get_tournaments_collection(guild_id)
    result = collection.insert_one(tournament_data)
    return result.inserted_id

def update_tournament(guild_id, tournament_id, tournament_data):
    collection = get_tournaments_collection(guild_id)
    result = collection.replace_one({"id": tournament_id}, tournament_data, upsert=True)
    return result.modified_count > 0 or result.upserted_id is not None

def find_tournament_by_id(guild_id, tournament_id):
    collection = get_tournaments_collection(guild_id)
    return collection.find_one({"id": tournament_id})

def find_all_tournaments(guild_id, include_archived=False):
    collection = get_tournaments_collection(guild_id)
    
    if include_archived:
        return list(collection.find({}))
    else:
        return list(collection.find({"archived": {"$ne": True}}))

def delete_tournament_db(guild_id, tournament_id):
    collection = get_tournaments_collection(guild_id)
    result = collection.delete_one({"id": tournament_id})
    return result.deleted_count > 0

def archive_tournament_db(guild_id, tournament_id):
    collection = get_tournaments_collection(guild_id)
    result = collection.update_one(
        {"id": tournament_id},
        {"$set": {"archived": True}}
    )
    return result.modified_count > 0

def get_leaderboard_collection(guild_id):
    collection_name = f"leaderboard_{guild_id}"
    return db[collection_name]

def record_leaderboard_result(guild_id, game_key, game_display, player, **increments):
    collection = get_leaderboard_collection(guild_id)
    all_stats = ("wins", "finals", "tournaments_played")
    set_on_insert = {stat: 0 for stat in all_stats if stat not in increments}
    
    update = {"$inc": increments, "$set": {"game_display": game_display}}
    if set_on_insert:
        update["$setOnInsert"] = set_on_insert
        
    collection.update_one(
        {"game_key": game_key, "player": player},
        update,
        upsert=True
    )
    
def adjust_leaderboard_stat(guild_id, game_key, game_display, player, stat, amount):
    collection = get_leaderboard_collection(guild_id)
    entry = collection.find_one({"game_key": game_key, "player": player}) or {}
    stats = {
        "wins":  entry.get("wins", 0),
        "finals": entry.get("finals", 0),
        "tournaments_played": entry.get("tournaments_played", 0)
    }
    stats[stat] = max(0, stats[stat] + amount)
    
    if all(v == 0 for v in stats.values()):
        collection.delete_one({"game_key": game_key, "player": player})
        return None

    collection.update_one(
        {"game_key": game_key, "player": player},
        {"$set": {**stats, "game_display": game_display}},
        upsert=True
    )
    
    return stats
    
def find_leaderboard(guild_id, game_key, limit=10):
    collection = get_leaderboard_collection(guild_id)
    return list(
        collection.find({"game_key": game_key})
        .sort([("wins", -1), ("finals", -1), ("tournaments_played", -1)]).limit(limit)
    )
    
# Distinct game displays for /leaderboard's autocomplete
def find_leaderboard_games(guild_id):
    return get_leaderboard_collection(guild_id).distinct("game_display")

def test_connection():
    try:
        print("Collections:", db.list_collection_names())
        print("Connection successful!")
        return True
    except Exception as e:
        print("MongoDB connection error:", e)
        return False

if __name__ == "__main__":
   test_connection()
