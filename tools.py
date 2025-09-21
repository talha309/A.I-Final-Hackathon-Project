# tools.py
from agents import function_tool
from db import get_student_collection, get_admin_collection, hash_password, verify_password
from typing import Dict, Any, List
import uuid
import datetime

students = get_student_collection()
admins = get_admin_collection()

# ----------------------------
# Student Management (Admin-managed)
# ----------------------------
@function_tool
def add_student(name: str, student_id: int, department: str, email: str) -> Dict[str, Any]:
    """
    Add student (email must be unique). Returns inserted student doc or error.
    Signature matches your requested: add_student(name, id, department, email)
    """
    email = email.lower().strip()
    if students.find_one({"email": email}):
        return {"error": f"Student with email {email} already exists"}
    student = {
        "name": name,
        "student_id": student_id,
        "department": department,
        "email": email,
        "created_at": datetime.datetime.utcnow()
    }
    result = students.insert_one(student)
    student["_id"] = str(result.inserted_id)
    return {"message": "Student added successfully", "student": student}


@function_tool
def get_student(identifier: str) -> Dict[str, Any]:
    """
    Get student by email OR by student_id (identifier passed as string).
    The agent can call get_student('anas@gmail.com') or get_student('123').
    """
    # first try email
    identifier = identifier.strip()
    student = students.find_one({"email": identifier.lower()})
    if not student:
        # try numeric student_id
        try:
            sid = int(identifier)
            student = students.find_one({"student_id": sid})
        except Exception:
            student = None
    if not student:
        return {"error": "Student not found"}
    student["_id"] = str(student["_id"])
    return student


@function_tool
def update_student(identifier: str, field: str, new_value: str) -> Dict[str, Any]:
    """
    Update student by email or student_id.
    field allowed: name, department, email, student_id
    If field == 'email', ensure new email doesn't already exist.
    """
    identifier = identifier.strip()
    # resolve query
    query = {"email": identifier.lower()}
    if students.find_one(query) is None:
        # try student_id
        try:
            sid = int(identifier)
            query = {"student_id": sid}
        except Exception:
            pass

    if field not in ["name", "department", "email", "student_id"]:
        return {"error": "Invalid field"}

    if field == "email":
        new_email = new_value.lower().strip()
        if students.find_one({"email": new_email}):
            return {"error": f"Student with email {new_email} already exists"}

    if field == "student_id":
        try:
            new_value = int(new_value)
        except Exception:
            return {"error": "student_id must be an integer"}

    result = students.update_one(query, {"$set": {field: new_value}})
    if result.matched_count == 0:
        return {"error": "Student not found"}
    student = students.find_one(query if field != "email" else {"email": new_value if field == "email" else query.get("email")})
    student["_id"] = str(student["_id"])
    return {"message": "Student updated successfully", "student": student}


@function_tool
def delete_student(identifier: str) -> Dict[str, Any]:
    """
    Delete student by email or student_id.
    """
    identifier = identifier.strip()
    query = {"email": identifier.lower()}
    if students.find_one(query) is None:
        try:
            sid = int(identifier)
            query = {"student_id": sid}
        except Exception:
            pass

    result = students.delete_one(query)
    if result.deleted_count == 0:
        return {"error": "Student not found"}
    return {"message": f"Student deleted successfully"}


@function_tool
def list_students() -> Dict[str, Any]:
    result = list(students.find().sort("created_at", -1))
    out = []
    for s in result:
        s["_id"] = str(s["_id"])
        out.append(s)
    return {"students": out}


# ----------------------------
# Analytics
# ----------------------------
@function_tool
def get_total_students() -> Dict[str, Any]:
    return {"total_students": students.count_documents({})}


@function_tool
def get_students_by_department() -> Dict[str, Any]:
    pipeline = [{"$group": {"_id": "$department", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}]
    return {"students_by_department": list(students.aggregate(pipeline))}


@function_tool
def get_recent_onboarded_students(limit: int = 5) -> Dict[str, Any]:
    limit = int(limit)
    cursor = students.find().sort("created_at", -1).limit(limit)
    out = []
    for s in cursor:
        s["_id"] = str(s["_id"])
        out.append(s)
    return {"recent_students": out}


@function_tool
def get_active_students_last_7_days() -> Dict[str, Any]:
    """
    Mocked active list. You can integrate real activity logs and query them here.
    """
    cursor = students.find().limit(3)
    out = []
    for s in cursor:
        s["_id"] = str(s["_id"])
        out.append(s)
    return {"active_last_7_days": out}


# ----------------------------
# FAQ / Events
# ----------------------------
@function_tool
def get_cafeteria_timings() -> Dict[str, Any]:
    return {"cafeteria_timings": "Mon-Fri 8am-8pm, Sat-Sun 9am-5pm"}


@function_tool
def get_library_hours() -> Dict[str, Any]:
    return {"library_hours": "Mon-Fri 9am-10pm, Sat 9am-6pm, Sun Closed"}


@function_tool
def get_event_schedule() -> Dict[str, Any]:
    return {
        "events": [
            {"title": "Orientation", "date": "Sept 25"},
            {"title": "Tech Talk", "date": "Oct 5"},
            {"title": "Sports Day", "date": "Oct 15"},
        ]
    }


# ----------------------------
# Notifications (mock)
# ----------------------------
@function_tool
def send_email(student_identifier: str, message: str) -> Dict[str, Any]:
    # resolve student
    student = None
    student_identifier = student_identifier.strip()
    student = students.find_one({"email": student_identifier.lower()})
    if not student:
        try:
            sid = int(student_identifier)
            student = students.find_one({"student_id": sid})
        except Exception:
            pass

    if not student:
        return {"error": "Student not found"}
    # mock send
    print(f"[EMAIL MOCK] to={student['email']} message={message}")
    return {"message": f"Email mock sent to {student['email']}"}
