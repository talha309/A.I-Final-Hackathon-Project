# agent.py
import os
from dotenv import load_dotenv
from pymongo import MongoClient
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.mongodb import MongoDBSaver
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from typing import TypedDict, List, Dict, Any
from tools import (
    add_student, get_student, update_student, delete_student, list_students,
    get_total_students, get_students_by_department, get_recent_onboarded_students,
    get_active_students_last_7_days, get_cafeteria_timings, get_library_hours,
    get_event_schedule, send_email
)

load_dotenv()

# --- LLM setup ---
llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash",
    google_api_key=os.getenv("GEMINI_API_KEY")
)

# Bind tools to LLM
tools = [
    add_student, get_student, update_student, delete_student, list_students,
    get_total_students, get_students_by_department, get_recent_onboarded_students,
    get_active_students_last_7_days, get_cafeteria_timings, get_library_hours,
    get_event_schedule, send_email
]
llm_with_tools = llm.bind_tools(tools)

# --- LangGraph State ---
class AgentState(TypedDict):
    messages: List[HumanMessage | AIMessage | ToolMessage]

# --- Agent Logic ---
def agent_node(state: AgentState) -> AgentState:
    messages = state["messages"]
    response = llm_with_tools.invoke(messages)
    
    # Handle tool calls if present
    if hasattr(response, "tool_calls") and response.tool_calls:
        tool_call = response.tool_calls[0]
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        
        # Find the tool by name
        tool = next((t for t in tools if t.__name__ == tool_name), None)
        if tool:
            try:
                tool_result = tool.invoke(**tool_args)
                return {
                    "messages": messages + [
                        response,
                        ToolMessage(content=str(tool_result), tool_call_id=tool_call["id"])
                    ]
                }
            except Exception as e:
                return {
                    "messages": messages + [
                        response,
                        ToolMessage(content=f"Error calling {tool_name}: {str(e)}", tool_call_id=tool_call["id"])
                    ]
                }
        else:
            return {
                "messages": messages + [
                    response,
                    ToolMessage(content=f"Tool {tool_name} not found", tool_call_id=tool_call["id"])
                ]
            }
    return {"messages": messages + [response]}

# --- LangGraph Workflow ---
workflow = StateGraph(AgentState)
workflow.add_node("agent", agent_node)
workflow.set_entry_point("agent")
workflow.add_edge("agent", END)

# --- MongoDBSaver for memory ---
MONGO_URI = os.getenv("DATABASE_URI", "mongodb://localhost:27017")
mongo_client = MongoClient(MONGO_URI)
db_name = os.getenv("DB_NAME", "campus_admin")
memory_saver = MongoDBSaver(mongo_client[db_name], collection_name="langgraph_memory")

# Compile the agent
agent = workflow.compile(checkpointer=memory_saver)

# Export agent and memory_saver
__all__ = ["agent", "memory_saver"]