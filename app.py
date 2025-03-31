import os
from flask import Flask, request, jsonify, render_template
from pymongo import MongoClient, ASCENDING
from datetime import datetime, timedelta
import pytz
import re
from dateutil import parser
from mongo_config import collection,db,client

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('web.html')

def get_date_range_for_today():
    today = datetime.now(pytz.UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    return today, today + timedelta(days=1)

def get_date_range_for_last_week():
    today = datetime.now(pytz.UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    start_of_last_week = today - timedelta(days=today.weekday() + 7)
    end_of_last_week = start_of_last_week + timedelta(days=6)
    return start_of_last_week, end_of_last_week

def get_date_range_for_last_n_days(n):
    today = datetime.now(pytz.UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    start_date = today - timedelta(days=n)
    return start_date, today

def get_date_range_for_this_week():
    today = datetime.now(pytz.UTC)
    start_of_week = today - timedelta(days=today.weekday())  # Monday of this week
    start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_week = start_of_week + timedelta(days=6, hours=23, minutes=59, seconds=59)
    return start_of_week, end_of_week

def extract_explicit_date(user_query):
    date_match = re.search(r"(\d{1,2}(?:st|nd|rd|th)?\s+\w+\s+\d{4}|\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4})", user_query, re.IGNORECASE)
    if date_match:
        try:
            extracted_date = parser.parse(date_match.group(1), fuzzy=True).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=pytz.UTC)
            end_date = extracted_date + timedelta(days=1, seconds=-1)  # Ensure it covers the full day
            print(f"✅ Extracted Date: {extracted_date} to {end_date}")  # Debugging
            return extracted_date, end_date
        except Exception as e:
            print(f"❌ Date Parsing Error: {e}")
            return None, None
    return None, None

def interpret_query(user_query):
    print(f"📝 Received Query: {user_query}")  # Debugging

    query_params = {
        "status": None,
        "start_date": None,
        "end_date": None,
        "agent_name": None,
        "customer": None, 
        "appointment_id": None,
        "count_only": False 
    }
    # ✅ Extract Date Filters Before Anything Else
    cleaned_query = re.sub(r'\b(from|of|for|in)\b\s+', '', user_query, flags=re.IGNORECASE)
    
    if "today" in cleaned_query:
        query_params["start_date"], query_params["end_date"] = get_date_range_for_today()
    elif "last week" in cleaned_query:
        query_params["start_date"], query_params["end_date"] = get_date_range_for_last_week()
    elif "this week" in cleaned_query:
        query_params["start_date"], query_params["end_date"] = get_date_range_for_this_week()
    else:
        match = re.search(r"last (\d+) days", cleaned_query)
        if match:
            query_params["start_date"], query_params["end_date"] = get_date_range_for_last_n_days(int(match.group(1)))

    print(f"🔍 Interpreted Query Params: {query_params}")
    # Extract explicit date
    start_date, end_date = extract_explicit_date(user_query)
    
    print(f"🔍 Extracted Start Date: {start_date}")  # Debugging
    print(f"🔍 Extracted End Date: {end_date}")  # Debugging

    if start_date and end_date:
        query_params["start_date"], query_params["end_date"] = start_date, end_date

    print(f"🔍 Interpreted Query Params: {query_params}")  # Debugging
   
    # ✅ Extract Appointment ID Properly
    match = re.search(r"\b(?:show|get|fetch|details of|find|can you show me|please|needed asap)?\s*(APPT\d+)\b", user_query, re.IGNORECASE)
    if match:
        query_params["appointment_id"] = match.group(1).strip().upper()
        print(f"✅ Extracted Appointment ID: {query_params['appointment_id']}")
    
    # ✅ Ensure "appointment id" is not mistaken as agent name
    agent_match = re.search(r"(?:handled by|by agent)\s+([A-Za-z ]+)", user_query, re.IGNORECASE)
    if agent_match:
        extracted_agent = agent_match.group(1).strip()
        if "appointment" not in extracted_agent.lower():  # ✅ Fix: Avoid incorrect agent extraction
            query_params["agent_name"] = extracted_agent

     # ✅ Extract Customer and Agent from Query
    match_customer = re.search(r"(?:of customer|for customer)\s+([A-Za-z ]+)", user_query, re.IGNORECASE)
    if match_customer:
        query_params["customer"] = match_customer.group(1).strip()
    
       # Extract Agent if present (handled by, by agent)
    match_agent = re.search(r"(?:handled by|by agent|for agent)\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)", user_query, re.IGNORECASE)
    if match_agent:
        query_params["agent_name"] = match_agent.group(1).strip()

    # ✅ Detect "How many" queries
    if user_query.lower().startswith("how many"):
        query_params["count_only"] = True  # Mark it as a count query

    # Ensure customer name is cleaned up from extra terms like "handled by"
    if query_params["customer"]:
       query_params["customer"] = re.sub(r"\s*(?:handled by agent|had|have|has|by agent|for agent|of agent)\s+[A-Za-z ]+", "", query_params["customer"]).strip()


    print(f"🔍 Interpreted Query Params: {query_params}")
  
    # ✅ Extract Status Filters
    if "confirmed" in user_query:
        query_params["status"] = "confirmed"
    elif "missed" in user_query:
        query_params["status"] = "missed"
    elif "rescheduled" in user_query:
        query_params["status"] = "rescheduled"
    elif "cancelled" in user_query:
        query_params["status"] = "cancelled"

    # ✅ Handle "Get All Appointments" Query
    if re.search(r"get all appointments|list all appointments", user_query, re.IGNORECASE):
        query_params["agent_name"] = None
        query_params["customer"] = None

    match = re.search(r"get all appointments for customer\s+([A-Za-z ]+)", user_query, re.IGNORECASE)
    if match:
        query_params["customer"] = match.group(1).strip()
   
    match = re.search(r"get all appointments handled by agent\s+([A-Za-z ]+)", user_query, re.IGNORECASE)
    if match:
        query_params["agent_name"] = match.group(1).strip()

    # Remove date-related phrases before extracting names
    user_query = re.sub(r"\b(this week|last week|last \d+ days|today|had last week|had this week)\b", "", user_query, flags=re.IGNORECASE).strip()
 
    # ✅ Extract Customer Name Only If "of customer" or "for customer" is Present
    match = re.search(r"(?:of customer|for customer|has customer)\s+([A-Za-z ]+)", user_query, re.IGNORECASE)
    if match:
        query_params["customer"] = match.group(1).strip()

    # ✅ Extract Agent Name Correctly
    agent_match = re.search(r"(?:handled by|by|for|of) agent\s+([A-Za-z ]+)", user_query, re.IGNORECASE)
    if agent_match:
        query_params["agent_name"] = agent_match.group(1).strip()

    # ✅ If "handled by" is present but agent is not detected, extract properly
   # Fix for extracting agent name correctly from queries that include customer handling by an agent
    if "handled by" in user_query:
        handled_by_match = re.search(r"([A-Za-z ]+)\s+handled by\s+([A-Za-z ]+)", user_query, re.IGNORECASE)
        if handled_by_match:
           query_params["customer"] = handled_by_match.group(1).strip()  # customer is before 'handled by'
           query_params["agent_name"] = handled_by_match.group(2).strip()  # agent is after 'handled by'

    # ✅ If "handled by" is present but customer is not detected, extract properly'
        handled_by_match = re.search(r"([A-Za-z ]+)\s+handled by\s+([A-Za-z ]+)", user_query, re.IGNORECASE)
        if handled_by_match:
           extracted_customer = handled_by_match.group(1).strip()  # Customer appears before 'handled by'
           extracted_agent = handled_by_match.group(2).strip()      # Agent appears after 'handled by'

    # ✅ Ensure the extracted customer name does not include extra keywords
           if "agent" not in extracted_customer.lower():  
               query_params["customer"] = extracted_customer

           query_params["agent_name"] = extracted_agent  # Agent name is correctly assigned

    #✅ Detect "How many" queries
           if user_query.lower().startswith("how many"):
              query_params["count_only"] = True  # Mark it as a count query
         
    # ✅ Case: "How many appointments does X have?"
    match_how_many = re.search(r"how many (confirmed|missed|cancelled|rescheduled)? ?appointments does ([A-Za-z ]+) have(?: handled by ([A-Za-z ]+))?", user_query, re.IGNORECASE)
    # ✅ Case: "How many appointments handled by Y?"
    match_handled_by = re.search(r"how many appointments handled by ([A-Za-z ]+)", user_query, re.IGNORECASE)
    # ✅ Case: "How many appointments has X handled?"
    match_has_handled = re.search(r"how many appointments has ([A-Za-z ]+) handled", user_query, re.IGNORECASE)   

    if match_how_many:
        if match_how_many.group(1):  # ✅ Extract status (optional)
            query_params["status"] = match_how_many.group(1).strip()
        query_params["customer"] = match_how_many.group(2).strip()
        if match_how_many.group(3):  # ✅ Extract agent (optional)
            query_params["agent_name"] = match_how_many.group(3).strip()
    elif match_handled_by:
        query_params["agent_name"] = match_handled_by.group(1).strip()
    elif match_has_handled:
        query_params["agent_name"] = match_has_handled.group(1).strip()
    elif "appointments" in user_query.lower():
        query_params["count_only"] = "all"  # Mark as count query for all appointments

    # ✅ If "of X" is used without "customer", treat X as an agent
    if query_params["customer"] is None:
        general_agent_match = re.search(r"(?:of|by|for|has)\s+([A-Za-z ]+)", user_query, re.IGNORECASE)
        if general_agent_match:
            query_params["agent_name"] = general_agent_match.group(1).strip()

    # ✅ Clean customer name if it accidentally includes agent info
    if query_params["customer"]:
       query_params["customer"] = re.sub(r"\s*(?:handled by agent|by agent|for agent|of agent)\s+[A-Za-z ]+", "", query_params["customer"]).strip()
   

    print(f"🔍 Interpreted Query Params: {query_params}")
    return query_params


def fetch_appointments_from_mongo(query_params):
    query_filter = {}

    if query_params.get("start_date") and query_params.get("end_date"):
        query_filter["appointment_time"] = {
            "$gte": query_params["start_date"],
            "$lte": query_params["end_date"]
        }

    if query_params.get("appointment_id"):
        query_filter["appointment_id"] = {"$regex": f"^{query_params['appointment_id']}$", "$options": "i"}
    
    if query_params.get("agent_name"):
        query_filter["agent"] = {"$regex": f"^{query_params['agent_name']}$", "$options": "i"}
    
    if query_params.get("customer"):
        query_filter["customer"] = {"$regex": f"^{query_params['customer']}$", "$options": "i"}

    if query_params.get("status"):
        query_filter["status"] = query_params["status"]

    print(f"🔍 Final MongoDB Query Filter: {query_filter}")  # Debugging

    # ✅ Execute MongoDB Query and always return list
    results = list(collection.find(query_filter, {"_id": 0}).sort("appointment_time", ASCENDING))

    for appointment in results:
        if isinstance(appointment.get("appointment_time"), datetime):
            appointment["appointment_time"] = appointment["appointment_time"].isoformat()

    print(f"📢 Number of Appointments Found: {len(results)}")

    return {
        "message": f"Appointments found: {len(results)}",
        "appointments": results
    }

@app.route('/query', methods=['POST'])
def process_query():
    try:
        user_query = request.json.get("query", "").lower()
        query_params = interpret_query(user_query)
        results = fetch_appointments_from_mongo(query_params)
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": "Failed to process query.", "details": str(e)})
    

if __name__ == '__main__':
    port = int(os.getenv("PORT", 5001))
    app.run(host='0.0.0.0', port=port, debug=True)
