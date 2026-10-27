# Smart Campus Event Management Portal

Academic mini project based on the supplied synopsis.

## Technology
- Python 3
- Flask
- SQLite
- HTML5, CSS3, JavaScript-ready frontend

## Run in VS Code

1. Extract this ZIP.
2. Open the project folder in VS Code.
3. Open Terminal.
4. Create a virtual environment (optional but recommended):

   `python -m venv venv`

5. Activate it on Windows:

   `venv\Scripts\activate`

6. Install dependencies:

   `pip install -r requirements.txt`

7. Start the application:

   `python app.py`

8. Open:

   `http://127.0.0.1:5000`

The SQLite database is created automatically on first run.

## Demo accounts

Student:
student@campus.com / student123

Organizer:
organizer@campus.com / org123

Admin:
admin@campus.com / admin123

## Main workflow

Student -> Login -> Browse events -> Register -> View registrations

Organizer -> Login -> Create event -> Edit event -> View participants -> Mark attendance

Admin -> Login -> Manage users -> Manage events -> View participants
