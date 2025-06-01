from pymongo import MongoClient
from datetime import datetime
import pytz

# Replace with your MongoDB Atlas connection string
MONGO_URI = ""mongodb://localhost:27017/""

client = MongoClient(MONGO_URI)
db = client["crm_db"]  # Change to your actual database name
collection = db["appointments"]  # Change to your actual collection name


# Update all documents
for doc in collection.find():
    if isinstance(doc["appointment_time"], str):  # Only convert if it's a string
        new_time = datetime.strptime(doc["appointment_time"], "%Y-%m-%dT%H:%M:%S.%f")
        collection.update_one({"_id": doc["_id"]}, {"$set": {"appointment_time": new_time}})

print("✅ All dates converted to ISODate format!")
print(collection.find_one())  # Ab `appointment_time` datetime format me hoga

start_date = datetime(2025, 3, 24, 0, 0, tzinfo=pytz.UTC)
end_date = datetime(2025, 3, 30, 0, 0, tzinfo=pytz.UTC)
