import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "local-demo-key")
DB = "database.db"

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'student'
    );
    CREATE TABLE IF NOT EXISTS events(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        category TEXT NOT NULL,
        date TEXT NOT NULL,
        time TEXT NOT NULL,
        venue TEXT NOT NULL,
        organiser_id INTEGER,
        capacity INTEGER NOT NULL,
        deadline TEXT NOT NULL,
        description TEXT,
        status TEXT DEFAULT 'Upcoming',
        FOREIGN KEY(organiser_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS registrations(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        event_id INTEGER NOT NULL,
        registered_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(student_id,event_id),
        FOREIGN KEY(student_id) REFERENCES users(id),
        FOREIGN KEY(event_id) REFERENCES events(id)
    );
    CREATE TABLE IF NOT EXISTS attendance(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        registration_id INTEGER UNIQUE NOT NULL,
        present INTEGER DEFAULT 0,
        FOREIGN KEY(registration_id) REFERENCES registrations(id)
    );
    """)
    # Demo accounts
    accounts = [
        ("Admin", "admin@campus.com", os.environ.get("ADMIN_PASSWORD"), "admin"),
        ("Event Organizer", "organizer@campus.com",os.environ.get("ORGANIZER_PASSWORD"), "organizer"),
        ("Demo Student", "student@campus.com",os.environ.get("STUDENT_PASSWORD") , "student")
    ]
    for name,email,password,role in accounts: 
        if not password:
            continue 
        try:
            conn.execute("INSERT INTO users(name,email,password,role) VALUES(?,?,?,?)",
                         (name,email,generate_password_hash(password),role))
        except sqlite3.IntegrityError:
            pass

    if conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 0:
        organizer = conn.execute("SELECT id FROM users WHERE email='organizer@campus.com'").fetchone()
        org = organizer["id"] if organizer else None
        demo = [
            ("TechFest 2026","Technical","2026-10-05","10:00","Main Auditorium",org,200,"2026-10-03","Coding, innovation and technology showcase."),
            ("Cultural Night","Cultural","2026-10-12","17:00","College Ground",org,500,"2026-10-10","Music, dance and cultural performances."),
            ("Inter College Cricket","Sports","2026-10-20","09:00","Sports Ground",org,100,"2026-10-18","Campus cricket tournament.")
        ]
        conn.executemany("""INSERT INTO events
        (title,category,date,time,venue,organiser_id,capacity,deadline,description)
        VALUES(?,?,?,?,?,?,?,?,?)""", demo)
    conn.commit()
    conn.close()

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper

def role_required(*roles):
    def deco(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if session.get("role") not in roles:
                flash("You do not have permission for this page.", "danger")
                return redirect(url_for("dashboard"))
            return f(*args, **kwargs)
        return wrapper
    return deco

@app.route("/")
def index():
    conn = get_db()
    events = conn.execute("SELECT * FROM events ORDER BY date,time LIMIT 6").fetchall()
    conn.close()
    return render_template("index.html", events=events)

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        name,email,password = request.form["name"],request.form["email"],request.form["password"]
        conn = get_db()
        try:
            conn.execute("INSERT INTO users(name,email,password,role) VALUES(?,?,?,?)",
                         (name,email,generate_password_hash(password),"student"))
            conn.commit()
            flash("Account created. Please login.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Email already registered.", "danger")
        finally:
            conn.close()
    return render_template("register.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email,password = request.form["email"],request.form["password"]
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        conn.close()
        if user and check_password_hash(user["password"], password):
            session.update(user_id=user["id"], name=user["name"], role=user["role"])
            return redirect(url_for("dashboard"))
        flash("Invalid email or password.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_db()
    if session["role"] == "student":
        events = conn.execute("SELECT * FROM events ORDER BY date,time").fetchall()
        regs = conn.execute("""SELECT r.*,e.title,e.date,e.time,e.venue
            FROM registrations r JOIN events e ON e.id=r.event_id
            WHERE r.student_id=? ORDER BY e.date""",(session["user_id"],)).fetchall()
        registered = {r["event_id"] for r in regs}
        conn.close()
        return render_template("student_dashboard.html",events=events,regs=regs,registered=registered)
    elif session["role"] == "organizer":
        events = conn.execute("SELECT * FROM events WHERE organiser_id=? ORDER BY date",
                              (session["user_id"],)).fetchall()
        conn.close()
        return render_template("organizer_dashboard.html",events=events)
    else:
        users = conn.execute("SELECT id,name,email,role FROM users ORDER BY id DESC").fetchall()
        events = conn.execute("""SELECT e.*,u.name organiser,
            (SELECT COUNT(*) FROM registrations r WHERE r.event_id=e.id) participants
            FROM events e LEFT JOIN users u ON u.id=e.organiser_id ORDER BY e.date""").fetchall()
        conn.close()
        return render_template("admin_dashboard.html",users=users,events=events)

@app.route("/events")
def events():
    q=request.args.get("q","").strip()
    category=request.args.get("category","").strip()
    conn=get_db()
    sql="SELECT * FROM events WHERE 1=1"
    params=[]
    if q:
        sql += " AND (title LIKE ? OR description LIKE ? OR venue LIKE ?)"
        params += [f"%{q}%",f"%{q}%",f"%{q}%"]
    if category:
        sql += " AND category=?"; params.append(category)
    sql += " ORDER BY date,time"
    rows=conn.execute(sql,params).fetchall()
    conn.close()
    return render_template("events.html",events=rows,q=q,category=category)

@app.route("/event/<int:event_id>")
def event_detail(event_id):
    conn=get_db()
    event=conn.execute("SELECT * FROM events WHERE id=?",(event_id,)).fetchone()
    count=conn.execute("SELECT COUNT(*) c FROM registrations WHERE event_id=?",(event_id,)).fetchone()["c"]
    conn.close()
    return render_template("event_detail.html",event=event,count=count)

@app.route("/register-event/<int:event_id>", methods=["POST"])
@login_required
@role_required("student")
def register_event(event_id):
    conn=get_db()
    event=conn.execute("SELECT * FROM events WHERE id=?",(event_id,)).fetchone()
    count=conn.execute("SELECT COUNT(*) c FROM registrations WHERE event_id=?",(event_id,)).fetchone()["c"]
    if not event:
        flash("Event not found.","danger")
    elif count >= event["capacity"]:
        flash("Event capacity is full.","danger")
    else:
        try:
            conn.execute("INSERT INTO registrations(student_id,event_id) VALUES(?,?)",
                         (session["user_id"],event_id))
            conn.commit()
            flash("Registration successful!","success")
        except sqlite3.IntegrityError:
            flash("You are already registered.","warning")
    conn.close()
    return redirect(url_for("dashboard"))

@app.route("/cancel/<int:event_id>", methods=["POST"])
@login_required
@role_required("student")
def cancel(event_id):
    conn=get_db()
    conn.execute("DELETE FROM registrations WHERE student_id=? AND event_id=?",
                 (session["user_id"],event_id))
    conn.commit(); conn.close()
    flash("Registration cancelled.","success")
    return redirect(url_for("dashboard"))

@app.route("/event/create", methods=["GET","POST"])
@login_required
@role_required("organizer")
def create_event():
    if request.method=="POST":
        f=request.form
        conn=get_db()
        conn.execute("""INSERT INTO events(title,category,date,time,venue,organiser_id,capacity,deadline,description)
                        VALUES(?,?,?,?,?,?,?,?,?)""",
                     (f["title"],f["category"],f["date"],f["time"],f["venue"],session["user_id"],
                      f["capacity"],f["deadline"],f["description"]))
        conn.commit(); conn.close()
        flash("Event created successfully.","success")
        return redirect(url_for("dashboard"))
    return render_template("create_event.html",event=None)

@app.route("/event/edit/<int:event_id>", methods=["GET","POST"])
@login_required
@role_required("organizer","admin")
def edit_event(event_id):
    conn=get_db()
    event=conn.execute("SELECT * FROM events WHERE id=?",(event_id,)).fetchone()
    if not event or (session["role"]=="organizer" and event["organiser_id"]!=session["user_id"]):
        conn.close(); flash("Event not found.","danger"); return redirect(url_for("dashboard"))
    if request.method=="POST":
        f=request.form
        conn.execute("""UPDATE events SET title=?,category=?,date=?,time=?,venue=?,capacity=?,deadline=?,description=?,status=?
                        WHERE id=?""",
                     (f["title"],f["category"],f["date"],f["time"],f["venue"],f["capacity"],
                      f["deadline"],f["description"],f["status"],event_id))
        conn.commit(); conn.close()
        flash("Event updated.","success"); return redirect(url_for("dashboard"))
    conn.close()
    return render_template("create_event.html",event=event)

@app.route("/event/delete/<int:event_id>", methods=["POST"])
@login_required
@role_required("organizer","admin")
def delete_event(event_id):
    conn=get_db()
    conn.execute("DELETE FROM registrations WHERE event_id=?",(event_id,))
    conn.execute("DELETE FROM events WHERE id=?",(event_id,))
    conn.commit(); conn.close()
    flash("Event deleted.","success"); return redirect(url_for("dashboard"))

@app.route("/event/<int:event_id>/participants")
@login_required
@role_required("organizer","admin")
def participants(event_id):
    conn=get_db()
    event=conn.execute("SELECT * FROM events WHERE id=?",(event_id,)).fetchone()
    rows=conn.execute("""SELECT r.id,r.registered_at,u.name,u.email,
        COALESCE(a.present,0) present
        FROM registrations r JOIN users u ON u.id=r.student_id
        LEFT JOIN attendance a ON a.registration_id=r.id
        WHERE r.event_id=?""",(event_id,)).fetchall()
    conn.close()
    return render_template("participants.html",event=event,participants=rows)

@app.route("/attendance/<int:registration_id>", methods=["POST"])
@login_required
@role_required("organizer","admin")
def mark_attendance(registration_id):
    present=1 if request.form.get("present")=="1" else 0
    conn=get_db()
    conn.execute("""INSERT INTO attendance(registration_id,present) VALUES(?,?)
                    ON CONFLICT(registration_id) DO UPDATE SET present=excluded.present""",
                 (registration_id,present))
    conn.commit(); conn.close()
    return redirect(request.referrer or url_for("dashboard"))

@app.route("/admin/user/<int:user_id>/role", methods=["POST"])
@login_required
@role_required("admin")
def change_role(user_id):
    role=request.form["role"]
    if role not in ("student","organizer","admin"): role="student"
    conn=get_db(); conn.execute("UPDATE users SET role=? WHERE id=?",(role,user_id))
    conn.commit(); conn.close()
    flash("User role updated.","success"); return redirect(url_for("dashboard"))

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
