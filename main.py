# main.py
import os
from fastapi import FastAPI, Depends, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import StreamingResponse
import jwt
import datetime
from agents import Runner

from db import get_admin_collection, hash_password, verify_password
from tools import (
    add_student, get_student, update_student, delete_student, list_students,
    get_total_students, get_students_by_department, get_recent_onboarded_students,
    get_active_students_last_7_days, get_cafeteria_timings, get_library_hours,
    get_event_schedule, send_email
)
from agent import agent, memory_saver

# Config / secrets
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = int(os.getenv("ACCESS_TOKEN_EXPIRE_HOURS", "12"))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="admin/login")

app = FastAPI(title="Campus Admin Agent")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ----------------------------
# Admin Signup & Login (JWT)
# ----------------------------
@app.post("/admin/signup")
def admin_signup(email: str = Body(...), password: str = Body(...), name: str = Body(None)):
    admins = get_admin_collection()
    email = email.lower().strip()
    if admins.find_one({"email": email}):
        raise HTTPException(status_code=400, detail=f"Admin with email {email} already exists")
    hashed = hash_password(password)
    admin = {"email": email, "password": hashed, "name": name or "", "created_at": datetime.datetime.utcnow(), "verified": True}
    # NOTE: For now, set verified True for admin signup. If you want verification, modify flow.
    admins.insert_one(admin)
    return {"message": "Admin created successfully", "admin": {"email": email, "name": name}}


@app.post("/admin/login")
def admin_login(form_data: OAuth2PasswordRequestForm = Depends()):
    admins = get_admin_collection()
    admin = admins.find_one({"email": form_data.username})
    if not admin:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not verify_password(form_data.password, admin["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    # build JWT
    expire = datetime.datetime.utcnow() + datetime.timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {"sub": admin["email"], "exp": expire}
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return {"access_token": token, "token_type": "bearer"}


# ----------------------------
# JWT dependency
# ----------------------------
def get_current_admin(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=401, detail="Invalid token")
        # optional: verify admin still exists
        admins = get_admin_collection()
        if admins.find_one({"email": email}) is None:
            raise HTTPException(status_code=401, detail="Invalid admin")
        return email
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


# ----------------------------
# Chat endpoint (sync)
# ----------------------------
@app.get("/chat")
async def chat_agent(q: str = Query(...), admin: str = Depends(get_current_admin)):
    """
    Run the agent for a single admin query. The agent can call function tools and update DB.
    Memory is persisted via memory_saver (LangGraph MongoDBSaver) passed as checkpoint.
    """
    # Runner.run returns a result object containing final_output and other details
    result = await Runner.run(agent, q, checkpoint=memory_saver)
    # result.final_output may be rich - return it directly
    return {"response": getattr(result, "final_output", result)}


# ----------------------------
# Chat stream (SSE)
# ----------------------------
@app.get("/chat/stream")
async def chat_agent_stream(q: str = Query(...), admin: str = Depends(get_current_admin)):
    """
    Stream tokens as SSE using Runner.stream(...) with checkpoint=memory_saver.
    Each yielded chunk is an atomic token/content as produced by the model.
    """
    async def event_generator():
        try:
            async for token in Runner.stream(agent, q, checkpoint=memory_saver):
                # token might be dict/str depending on SDK - convert to string
                data = token if isinstance(token, str) else str(token)
                yield f"data: {data}\n\n"
        except Exception as e:
            yield f"data: [STREAM ERROR] {str(e)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ----------------------------
# Students REST (admin-protected)
# ----------------------------
@app.post("/students")
def api_add_student(payload: dict = Body(...), admin: str = Depends(get_current_admin)):
    """
    payload example:
    {
      "name":"Anas",
      "student_id": 1,
      "department":"BS SE",
      "email":"anas@gmail.com"
    }
    """
    # validate keys minimally
    for k in ("name", "student_id", "department", "email"):
        if k not in payload:
            raise HTTPException(status_code=400, detail=f"Missing field: {k}")
    result = add_student(payload["name"], int(payload["student_id"]), payload["department"], payload["email"])
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.get("/students")
def api_get_student(email: str = Query(None), student_id: str = Query(None), admin: str = Depends(get_current_admin)):
    """
    For compatibility: prefer email; if email omitted, use student_id.
    """
    if email:
        result = get_student(email)
    elif student_id:
        result = get_student(student_id)
    else:
        raise HTTPException(status_code=400, detail="Provide email or student_id")
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@app.put("/students")
def api_update_student(identifier: str = Query(...), update: dict = Body(...), admin: str = Depends(get_current_admin)):
    """
    identifier: email or student_id string
    update: {"field":"department","new_value":"BS CS"}
    """
    if "field" not in update or "new_value" not in update:
        raise HTTPException(status_code=400, detail="update must contain 'field' and 'new_value'")
    result = update_student(identifier, update["field"], update["new_value"])
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.delete("/students")
def api_delete_student(identifier: str = Query(...), admin: str = Depends(get_current_admin)):
    result = delete_student(identifier)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@app.get("/students/list")
def api_list_students(admin: str = Depends(get_current_admin)):
    return list_students()


# ----------------------------
# Analytics endpoints
# ----------------------------
@app.get("/analytics/total")
def api_total_students(admin: str = Depends(get_current_admin)):
    return get_total_students()


@app.get("/analytics/by-department")
def api_students_by_department(admin: str = Depends(get_current_admin)):
    return get_students_by_department()


@app.get("/analytics/recent")
def api_recent_students(limit: int = 5, admin: str = Depends(get_current_admin)):
    return get_recent_onboarded_students(limit)


@app.get("/analytics/active")
def api_active_last_7_days(admin: str = Depends(get_current_admin)):
    return get_active_students_last_7_days()


# ----------------------------
# FAQ & Events
# ----------------------------
@app.get("/faq/cafeteria")
def api_cafeteria(admin: str = Depends(get_current_admin)):
    return get_cafeteria_timings()


@app.get("/faq/library")
def api_library(admin: str = Depends(get_current_admin)):
    return get_library_hours()


@app.get("/faq/events")
def api_events(admin: str = Depends(get_current_admin)):
    return get_event_schedule()
@app.get("/")
def route():
    return ("Welcome to studentAPI")