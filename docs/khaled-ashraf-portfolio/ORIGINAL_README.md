# Student Email Gate Login

This project checks whether the typed email exists in `kbc_users_data`.
If email exists, login is accepted. Otherwise it returns:
`???? ??????? ????? ? aptem`

## Setup

1. Create venv and install deps:
   python -m venv .venv
   .\.venv\Scripts\activate
   pip install -r requirements.txt

2. Keep your `.env` file in project root (already present).

3. Run server:
   python manage.py runserver

4. Open:
   http://127.0.0.1:8000/

## API

POST `/api/auth/student-login/`
Body:
{
  "email": "student@example.com"
}