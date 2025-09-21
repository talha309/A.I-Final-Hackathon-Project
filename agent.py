# agent.py
import os
from dotenv import load_dotenv
from pymongo import MongoClient
from langgraph.checkpoint.mongodb import MongoDBSaver
from agents import Agent, OpenAIChatCompletionsModel
from tools import (
    add_student, get_student, update_student, delete_student, list_students,
    get_total_students, get_students_by_department, get_recent_onboarded_students,
    get_active_students_last_7_days, get_cafeteria_timings, get_library_hours,
    get_event_schedule, send_email
)
from openai import AsyncOpenAI

load_dotenv()

# --- OpenAI client (used for Gemini via OpenAI SDK) ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = AsyncOpenAI(
    api_key=GEMINI_API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)


# Model wrapper for the agents SDK
model = OpenAIChatCompletionsModel(model="gemini-2.0-flash", openai_client=client)

# Build agent with tools
agent = Agent(
    name="Campus Admin Agent",
    instructions=(
        "You are the Campus Admin assistant. You **must** only perform actions after admin asks. "
        "You can call the provided tools to manage students, analytics, FAQ and notifications."
    ),
    model=model,
    tools=[
        add_student, get_student, update_student, delete_student, list_students,
        get_total_students, get_students_by_department, get_recent_onboarded_students,
        get_active_students_last_7_days, get_cafeteria_timings, get_library_hours,
        get_event_schedule, send_email,
    ],
)

# --- LangGraph MongoDBSaver for memory (threaded history) ---
MONGO_URI =  os.getenv("DATABASE_URI", "mongodb://localhost:27017")
mongo_client = MongoClient(MONGO_URI)
# Use same DB as db.py to centralize
db_name = os.getenv("DB_NAME", "campus_admin")
memory_db = mongo_client[db_name]
memory_saver = MongoDBSaver(memory_db, collection_name="langgraph_memory")

# Export agent and memory_saver
__all__ = ["agent", "memory_saver"]
