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
    """Get the tournaments collection for a specific guild"""
    collection_name = f"tournaments_{guild_id}"
    return db[collection_name]

def insert_tournament(guild_id, tournament_data):
    """Insert a new tournament"""
    collection = get_tournaments_collection(guild_id)
    result = collection.insert_one(tournament_data)
    return result.inserted_id

def update_tournament(guild_id, tournament_id, tournament_data):
    """Update an existing tournament"""
    collection = get_tournaments_collection(guild_id)
    result = collection.replace_one({"id": tournament_id}, tournament_data, upsert=True)
    return result.modified_count > 0 or result.upserted_id is not None

def find_tournament_by_id(guild_id, tournament_id):
    """Find a tournament by its ID"""
    collection = get_tournaments_collection(guild_id)
    return collection.find_one({"id": tournament_id})

def find_all_tournaments(guild_id, include_archived=False):
    """Find all tournaments for a guild"""
    collection = get_tournaments_collection(guild_id)
    
    if include_archived:
        return list(collection.find({}))
    else:
        return list(collection.find({"archived": {"$ne": True}}))

def delete_tournament_db(guild_id, tournament_id):
    """Delete a tournament"""
    collection = get_tournaments_collection(guild_id)
    result = collection.delete_one({"id": tournament_id})
    return result.deleted_count > 0

def archive_tournament_db(guild_id, tournament_id):
    """Archive a tournament"""
    collection = get_tournaments_collection(guild_id)
    result = collection.update_one(
        {"id": tournament_id},
        {"$set": {"archived": True}}
    )
    return result.modified_count > 0

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
