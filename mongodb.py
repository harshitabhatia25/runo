import json
import pymongo

# MongoDB Atlas Connection URI (Replace with your actual URI)
MONGO_URI = "mongodb+srv://bhatiaharshita25:%40Mummy07@cluster0.wutsa1o.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

# Database and Collection Names
DATABASE_NAME = "crm_db"  # Change this
COLLECTION_NAME = "collection"  # Change this

# Load JSON data from file
JSON_FILE_PATH = "appointments_sample.json"  # Change this

# Connect to MongoDB
client = pymongo.MongoClient(MONGO_URI)
db = client[DATABASE_NAME]
collection = db[COLLECTION_NAME]

# Read JSON file
with open(JSON_FILE_PATH, "r", encoding="utf-8") as file:
    data = json.load(file)  # Load JSON data

# Ensure data is in list format
if isinstance(data, dict):
    data = [data]  # Convert single JSON object to list

# Insert into MongoDB
result = collection.insert_many(data)
print(f"Inserted {len(result.inserted_ids)} documents successfully!")

