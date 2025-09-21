# student_agent.py
import os
from typing_extensions import TypedDict
from typing import Annotated, Dict, Any, List
from datetime import datetime, timedelta
from bson import ObjectId
from pymongo import MongoClient
from dotenv import load_dotenv
from openai import AsyncOpenAI
from agents import Agent, OpenAIChatCompletionsModel, Runner, function_tool
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.mongodb import MongoDBSaver

from collections import defaultdict

# ----------------------------
# Load environment variables
# ----------------------------
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MONGO_URI = os.getenv("DATABASE_URI", "mongodb://localhost:27017")
DB_NAME = "campus"

# ----------------------------
# MongoDB setup
# ----------------------------
mongo_client = MongoClient(MONGO_URI)
db = mongo_client[DB_NAME]
students = db["students"]
threads = db["threads"]
activity_logs = db["activity_logs"]

# ----------------------------
# Helper functions
# ----------------------------
def _objid_to_str(doc):
    if isinstance(doc, dict):
        return {k: _objid_to_str(v) for k, v in doc.items()}
    elif isinstance(doc, list):
        return [_objid_to_str(v) for v in doc]
    elif isinstance(doc, ObjectId):
        return str(doc)
    else:
        return doc

def get_or_create_thread_id(student_id: str) -> str:
    record = threads.find_one({"student_id": student_id})
    if record:
        return record["thread_id"]
    new_thread_id = str(ObjectId())
    threads.insert_one({"student_id": student_id, "thread_id": new_thread_id})
    return new_thread_id

# ----------------------------
# Student Management Tools
# ----------------------------
@function_tool
def add_student(name: str, student_id: str, department: str, email: str) -> Dict[str, Any]:
    if students.find_one({"email": email}):
        return {"error": "Email already exists"}
    student = {"name": name, "student_id": student_id, "department": department, "email": email, "created_at": datetime.utcnow()}
    students.insert_one(student)
    return {"message": "Student added successfully", "student": _objid_to_str(student)}

@function_tool
def get_student(student_id: str) -> Dict[str, Any]:
    student = students.find_one({"student_id": student_id}, {"_id": 0})
    return student or {"error": "Student not found"}

@function_tool
def update_student(student_id: str, field: str, new_value: str) -> Dict[str, Any]:
    if field == "email" and students.find_one({"email": new_value}):
        return {"error": "Email already exists"}
    result = students.update_one({"student_id": student_id}, {"$set": {field: new_value}})
    if result.matched_count == 0:
        return {"error": "Student not found"}
    return get_student(student_id)

@function_tool
def delete_student(student_id: str) -> Dict[str, Any]:
    result = students.delete_one({"student_id": student_id})
    if result.deleted_count == 0:
        return {"error": "Student not found"}
    return {"message": f"Student {student_id} deleted"}

@function_tool
def list_students() -> List[Dict[str, Any]]:
    return _objid_to_str(list(students.find({}, {"_id": 0})))

# ----------------------------
# Analytics Tools
# ----------------------------
@function_tool
def get_total_students() -> Dict[str, Any]:
    return {"total_students": students.count_documents({})}

@function_tool
def get_students_by_department() -> List[Dict[str, Any]]:
    pipeline = [{"$group": {"_id": "$department", "count": {"$sum": 1}}}]
    return _objid_to_str(list(students.aggregate(pipeline)))

@function_tool
def get_recent_onboarded_students(limit: int = 5) -> List[Dict[str, Any]]:
    result = students.find({}, {"_id": 0}).sort("created_at", -1).limit(limit)
    return _objid_to_str(list(result))

@function_tool
def get_active_students_last_7_days() -> List[Dict[str, Any]]:
    since = datetime.utcnow() - timedelta(days=7)
    result = activity_logs.find({"last_active": {"$gte": since}}, {"_id": 0})
    return _objid_to_str(list(result))

# ----------------------------
# FAQ & Events
# ----------------------------
@function_tool
def get_cafeteria_timings() -> Dict[str, str]:
    return {"cafeteria_timings": "Monday-Saturday, 8 AM - 8 PM"}

@function_tool
def get_library_hours() -> Dict[str, str]:
    return {"library_hours": "Monday-Saturday, 9 AM - 10 PM"}

@function_tool
def get_event_schedule() -> List[Dict[str, str]]:
    return [
        {"event": "Orientation", "date": "2025-09-25", "time": "10:00 AM"},
        {"event": "AI Workshop", "date": "2025-10-02", "time": "2:00 PM"}
    ]

# ----------------------------
# Notifications
# ----------------------------
@function_tool
def send_email(student_id: str, message: str) -> Dict[str, Any]:
    student = students.find_one({"student_id": student_id}, {"_id": 0})
    if not student:
        return {"error": "Student not found"}
    print(f"[MOCK EMAIL] To: {student['email']} | Msg: {message}")
    return {"status": "sent", "to": student["email"], "message": message}

# ----------------------------
# OpenAI SDK Agent
# ----------------------------
openai_client = AsyncOpenAI(
    api_key=GEMINI_API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)

TOOLS = [
    add_student, get_student, update_student, delete_student, list_students,
    get_total_students, get_students_by_department,
    get_recent_onboarded_students, get_active_students_last_7_days,
    get_cafeteria_timings, get_library_hours, get_event_schedule,
    send_email
]

PROMPT = """
You are Campus Assistant. Use the tools to answer queries in JSON.
Always validate emails before adding students.
Respond clearly in structured JSON.
"""

agent = Agent(
    name="Campus Assistant",
    instructions=PROMPT,
    model=OpenAIChatCompletionsModel(model="gemini-2.0-flash", openai_client=openai_client),
    tools=TOOLS,
)

# ----------------------------
# LangGraph Memory for multi-turn
# ----------------------------
class MessagesState(TypedDict):
    messages: Annotated[list, add_messages]

def assistant(state: MessagesState):
    return {"messages": [agent.invoke(state["messages"])]}

builder = StateGraph(MessagesState)
builder.add_node("assistant", assistant)
builder.add_edge(START, "assistant")
builder.add_edge("assistant", END)

memory = MongoDBSaver(mongo_client)  # <- Correct client
graph = builder.compile(checkpointer=memory)

# ----------------------------
# FastAPI App
# ----------------------------
app = FastAPI(title="Campus Assistant Agent")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"]
)

# --- Chat Endpoints ---
@app.get("/chat")
async def chat(q: str, student_id: str):
    thread_id = get_or_create_thread_id(student_id)
    config = {"configurable": {"thread_id": thread_id}}
    result = graph.invoke({"messages": [("user", q)]}, config)
    return result

@app.get("/chat/stream")
async def chat_stream(q: str, student_id: str):
    thread_id = get_or_create_thread_id(student_id)
    config = {"configurable": {"thread_id": thread_id}}

    async def event_generator():
        async for event in graph.astream({"messages": [("user", q)]}, config):
            yield f"data: {event}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# --- REST-style Student CRUD for Postman ---
@app.get("/students")
def get_students_list():
    return list_students()

@app.post("/students")
def create_student(name: str, student_id: str, department: str, email: str):
    return add_student(name, student_id, department, email)

@app.get("/students/{student_id}")
def read_student(student_id: str):
    return get_student(student_id)

@app.put("/students/{student_id}")
def modify_student(student_id: str, field: str, new_value: str):
    return update_student(student_id, field, new_value)

@app.delete("/students/{student_id}")
def remove_student(student_id: str):
    return delete_student(student_id)

# --- Analytics Endpoints ---
@app.get("/analytics")
def analytics():
    return {
        "total_students": get_total_students(),
        "students_by_department": get_students_by_department(),
        "recent_onboarded": get_recent_onboarded_students(),
        "active_last_7_days": get_active_students_last_7_days()
    }

@app.get("/analytics/dashboard")
def analytics_dashboard():
    # Total students
    total_students = students.count_documents({})

    # Students by department (for Pie Chart)
    pipeline = [{"$group": {"_id": "$department", "count": {"$sum": 1}}}]
    dept_data = list(students.aggregate(pipeline))
    dept_chart = [{"department": d["_id"], "value": d["count"]} for d in dept_data]

    # Recent onboardings (last 5 students)
    recent = list(students.find({}, {"_id": 0}).sort("created_at", -1).limit(5))

    # Activity heatmap (group by day of week + hour)
    since = datetime.utcnow() - timedelta(days=7)
    logs = list(activity_logs.find({"last_active": {"$gte": since}}, {"_id": 0}))
    heatmap = defaultdict(lambda: defaultdict(int))
    for log in logs:
        dt = log["last_active"]
        day = dt.strftime("%A")
        hour = dt.hour
        heatmap[day][hour] += 1
    heatmap = {day: dict(hours) for day, hours in heatmap.items()}

    return {
        "total_students": total_students,
        "students_by_department": dept_chart,
        "recent_onboarded": recent,
        "activity_heatmap": heatmap
    }
