from flask import Flask, render_template, request, redirect, session
import sqlite3, os

app = Flask(__name__)
app.secret_key = "secret123"

def get_db():
    return sqlite3.connect("database.db")

def init_db():
    db = get_db()
    cur = db.cursor()

    cur.execute("""CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, email TEXT, password TEXT)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS income(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, amount REAL)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS expenses(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, amount REAL,
        description TEXT, category TEXT,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

    db.commit()
    db.close()

init_db()

# ---------- AI CATEGORY ----------
def ai_category(text):
    text = text.lower().strip()
    categories = {
        "Food": ["food","pizza","burger","meal","coffee"],
        "Transport": ["bus","train","auto","taxi","petrol","fuel"],
        "Education": ["book","pen","fees","exam","college"],
        "Utilities": ["mobile","recharge","internet","wifi","bill"],
        "Entertainment": ["movie","game","music","netflix"],
        "Shopping": ["shirt","dress","shoes","amazon"]
    }

    for cat, words in categories.items():
        for w in words:
            if w in text:
                return cat
    return "Other"

def ai_feedback(income, expense):
    if income == 0:
        return "Add income to receive insights."
    save = income - expense
    if save < 0:
        return "Warning: You are overspending."
    elif save < income * 0.2:
        return "Try saving more."
    else:
        return "Great financial control!"

# ---------- ROUTES ----------
@app.route("/", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        pwd = request.form["password"]
        db = get_db()
        cur = db.cursor()
        cur.execute("SELECT * FROM users WHERE email=? AND password=?", (email,pwd))
        user = cur.fetchone()
        if user:
            session["user_id"] = user[0]
            return redirect("/dashboard")
    return render_template("login.html")

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        pwd = request.form["password"]
        db = get_db()
        cur = db.cursor()
        cur.execute("INSERT INTO users(name,email,password) VALUES (?,?,?)",(name,email,pwd))
        db.commit()
        return redirect("/")
    return render_template("register.html")

@app.route("/add_income", methods=["POST"])
def add_income():
    amt = request.form["income"]
    db = get_db()
    cur = db.cursor()
    cur.execute("INSERT INTO income(user_id,amount) VALUES (?,?)",(session["user_id"],amt))
    db.commit()
    return redirect("/dashboard")

@app.route("/delete/<int:id>")
def delete(id):
    db = get_db()
    cur = db.cursor()
    cur.execute("DELETE FROM expenses WHERE id=?", (id,))
    db.commit()
    return redirect("/dashboard")

@app.route("/dashboard", methods=["GET","POST"])
def dashboard():
    db = get_db()
    cur = db.cursor()

    if request.method == "POST":
        amt = request.form["amount"]
        desc = request.form["description"]
        cat = ai_category(desc)
        cur.execute("INSERT INTO expenses(user_id,amount,description,category) VALUES (?,?,?,?)",
                    (session["user_id"],amt,desc,cat))
        db.commit()

    cur.execute("SELECT SUM(amount) FROM expenses WHERE user_id=?",(session["user_id"],))
    expense = cur.fetchone()[0] or 0

    cur.execute("SELECT SUM(amount) FROM income WHERE user_id=?",(session["user_id"],))
    income = cur.fetchone()[0] or 0

    cur.execute("SELECT id,amount,description,category FROM expenses WHERE user_id=?",
                (session["user_id"],))
    expenses = cur.fetchall()

    cur.execute("SELECT category,SUM(amount) FROM expenses WHERE user_id=? GROUP BY category",
                (session["user_id"],))
    summary = cur.fetchall()

    feedback = ai_feedback(income, expense)

    return render_template("dashboard.html",
                           expenses=expenses,
                           income=income,
                           expense=expense,
                           summary=summary,
                           feedback=feedback)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5000)))
