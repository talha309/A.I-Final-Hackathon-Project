🏫 Campus Admin Agent

An AI-powered Campus Management System built with FastAPI, LangGraph, and MongoDB, enabling admins to manage students, view analytics, and interact with the system via natural language queries using Gemini (Google Generative AI).

🚀 Features
🔑 Authentication

Admin signup/login with JWT-based authentication.

Token-protected APIs for all admin actions.

👨‍🎓 Student Management

add_student(name, email, department)

get_student(email)

update_student(email, field, new_value)

delete_student(email)

list_students()

📊 Campus Analytics

get_total_students()

get_students_by_department()

get_recent_onboarded_students(limit=5)

get_active_students_last_7_days()

📌 Campus FAQ

get_cafeteria_timings()

get_library_hours()

get_event_schedule()

📢 Notifications

send_email(email, message) → Mock email sending

💬 AI Chat Agent

Natural language queries handled by LangGraph + Gemini.

Memory stored in MongoDB (thread-by-thread).

Streaming responses (/chat/stream).

📈 Optional Frontend (Next.js)

Dark mode login/signup page.

Dashboard showing:

Total students

Students by department (pie chart)

Recent onboardings

Activity heatmap

📂 Project Structure
campus-admin-agent/
│── backend/
│   ├── main.py        # FastAPI entrypoint
│   ├── agent.py       # LLM + LangGraph
│   ├── tools.py       # CRUD, analytics, FAQ tools
│   ├── db.py          # MongoDB connection
│   └── requirements.txt
│
│── frontend/ (optional)
│   ├── pages/login.tsx
│   ├── pages/signup.tsx
│   ├── pages/dashboard.tsx
│   └── styles/globals.css
│
│── CampusAgent.postman_collection.json
│── CampusAgent.postman_environment.json
│── README.md

⚡ Setup Instructions
Backend
cd backend
poetry install
poetry run uvicorn main:app --reload

Environment Variables (.env)
OPENAI_API_KEY=your-key
GOOGLE_API_KEY=your-key
MONGODB_URI=mongodb://localhost:27017/campus
SECRET_KEY=your-secret

Frontend (optional)
cd frontend
npm install
npm run dev

📬 API Endpoints
Authentication

POST /admin/signup

POST /admin/login

Students

POST /students

GET /students

PUT /students/{email}

DELETE /students/{email}

Analytics

GET /analytics

Chat

POST /chat

GET /chat/stream

🧪 Postman Collection

Import CampusAgent.postman_collection.json and CampusAgent.postman_environment.json into Postman.

Run Admin Login → token auto-saved → all endpoints work.

🖼️ Dashboard Preview

(Optional Next.js Frontend)

Login/Signup page with dark mode.

Analytics dashboard with Recharts.

📌 Tech Stack

Backend: FastAPI, LangGraph, MongoDB, JWT

LLM: Gemini (Google Generative AI)

Frontend: Next.js, Recharts (optional)

Auth: OAuth2 Password Flow + JWT

Dev Tools: Postman, Poetry

🔥 With this project, admins can chat with AI to manage students and view real-time campus insights in a clean dashboard.