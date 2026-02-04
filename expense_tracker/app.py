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
        user_id INTEGER,
        amount REAL,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS expenses(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount REAL,
        description TEXT,
        category TEXT,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

    db.commit()
    db.close()

init_db()

def ai_category(text):
    text = text.lower()
    rules = {
        "Food":["food","pizza","coffee"],
        "Transport":["bus","train","petrol"],
        "Education":["fees","book","college"],
        "Utilities":["wifi","recharge","bill"],
        "Entertainment":["movie","game"],
        "Shopping":["amazon","shirt"]
    }
    for c,w in rules.items():
        for i in w:
            if i in text:
                return c
    return "Other"

def ai_feedback(income, expense):
    if income == 0:
        return "Add income to unlock insights."
    p = (expense/income)*100
    if p > 90:
        return "⚠ Spending is very high this month."
    elif p > 70:
        return "You are close to your spending limit."
    return "Great control. Spending looks healthy."

@app.route("/", methods=["GET","POST"])
def login():
    if request.method == "POST":
        db = get_db()
        cur = db.cursor()
        cur.execute("SELECT * FROM users WHERE email=? AND password=?",
                    (request.form["email"],request.form["password"]))
        user = cur.fetchone()
        if user:
            session["user_id"] = user[0]
            return redirect("/dashboard")
    return render_template("login.html")

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        db = get_db()
        cur = db.cursor()
        cur.execute("INSERT INTO users VALUES(NULL,?,?,?)",
                    (request.form["name"],request.form["email"],request.form["password"]))
        db.commit()
        return redirect("/")
    return render_template("register.html")

@app.route("/dashboard", methods=["GET","POST"])
def dashboard():
    db = get_db()
    cur = db.cursor()

    if request.method == "POST":
        amt = request.form["amount"]
        desc = request.form["description"]
        cat = ai_category(desc)
        cur.execute("INSERT INTO expenses VALUES(NULL,?,?,?,?,CURRENT_TIMESTAMP)",
                    (session["user_id"],amt,desc,cat))
        db.commit()

    cur.execute("SELECT SUM(amount) FROM income WHERE user_id=?",(session["user_id"],))
    income = cur.fetchone()[0] or 0

    cur.execute("SELECT SUM(amount) FROM expenses WHERE user_id=?",(session["user_id"],))
    expense = cur.fetchone()[0] or 0

    cur.execute("""SELECT strftime('%m',date),SUM(amount)
                   FROM expenses WHERE user_id=? GROUP BY strftime('%m',date)""",
                (session["user_id"],))
    em = dict(cur.fetchall())

    cur.execute("""SELECT strftime('%m',date),SUM(amount)
                   FROM income WHERE user_id=? GROUP BY strftime('%m',date)""",
                (session["user_id"],))
    im = dict(cur.fetchall())

    months = ["02","03","04","05","06","07"]
    expense_data = [em.get(m,0) for m in months]
    income_data = [im.get(m,0) for m in months]

    cur.execute("SELECT category,SUM(amount) FROM expenses WHERE user_id=? GROUP BY category",
                (session["user_id"],))
    s = cur.fetchall()

    feedback = ai_feedback(income,expense)

    return render_template("dashboard.html",
        income=income, expense=expense,
        income_data=income_data, expense_data=expense_data,
        categories=[i[0] for i in s],
        amounts=[i[1] for i in s],
        feedback=feedback
    )

@app.route("/add_income", methods=["POST"])
def add_income():
    db = get_db()
    cur = db.cursor()
    cur.execute("INSERT INTO income VALUES(NULL,?,?,CURRENT_TIMESTAMP)",
                (session["user_id"],request.form["income"]))
    db.commit()
    return redirect("/dashboard")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

app.run(debug=True)
