from flask import Flask, render_template, request, redirect, session
import sqlite3

app = Flask(__name__)
app.secret_key = "expense_ai_secret"

# ---------- DATABASE ----------
def get_db():
    return sqlite3.connect("database.db")

def init_db():
    db = get_db()
    cur = db.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT,
        password TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS income(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount REAL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS expenses(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount REAL,
        description TEXT,
        category TEXT,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    db.commit()
    db.close()

init_db()

# ---------- AI CATEGORY ----------
def ai_category(text):
    text = text.lower()

    food = ["food", "pizza", "burger", "meal", "snack"]
    transport = ["bus", "train", "auto", "taxi", "petrol", "fuel", "travel"]
    education = ["book", "pen", "fees", "course", "class"]
    utilities = ["mobile", "recharge", "internet", "electricity"]

    for w in food:
        if w in text: return "Food"
    for w in transport:
        if w in text: return "Transport"
    for w in education:
        if w in text: return "Education"
    for w in utilities:
        if w in text: return "Utilities"

    return "Other"

# ---------- AI FEEDBACK ----------
def ai_feedback(income, expense):
    if income == 0:
        return "Add income to receive financial insights."

    savings = income - expense

    if savings < 0:
        return "Warning: Expenses exceed income. Reduce unnecessary spending."
    elif savings < income * 0.2:
        return "You are saving less. Try budgeting your expenses."
    else:
        return "Great job! Your spending is under control."

# ---------- ROUTES ----------
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        db = get_db()
        cur = db.cursor()
        cur.execute("SELECT * FROM users WHERE email=? AND password=?", (email, password))
        user = cur.fetchone()

        if user:
            session["user_id"] = user[0]
            return redirect("/dashboard")

    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        db = get_db()
        cur = db.cursor()
        cur.execute("INSERT INTO users(name,email,password) VALUES (?,?,?)",
                    (name, email, password))
        db.commit()
        return redirect("/")

    return render_template("register.html")

@app.route("/add_income", methods=["POST"])
def add_income():
    if "user_id" not in session:
        return redirect("/")

    amount = request.form["income"]
    db = get_db()
    cur = db.cursor()
    cur.execute("INSERT INTO income(user_id,amount) VALUES (?,?)",
                (session["user_id"], amount))
    db.commit()
    return redirect("/dashboard")

@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if "user_id" not in session:
        return redirect("/")

    db = get_db()
    cur = db.cursor()

    if request.method == "POST" and "amount" in request.form:
        amount = request.form["amount"]
        description = request.form["description"]
        category = ai_category(description)

        cur.execute(
            "INSERT INTO expenses(user_id,amount,description,category) VALUES (?,?,?,?)",
            (session["user_id"], amount, description, category)
        )
        db.commit()

    cur.execute("""
    SELECT SUM(amount) FROM expenses
    WHERE user_id=? AND strftime('%m',date)=strftime('%m','now')
    """, (session["user_id"],))
    monthly_total = cur.fetchone()[0] or 0

    cur.execute("""
    SELECT category, SUM(amount)
    FROM expenses
    WHERE user_id=?
    GROUP BY category
    """, (session["user_id"],))
    category_summary = cur.fetchall()

    cur.execute("SELECT SUM(amount) FROM income WHERE user_id=?", (session["user_id"],))
    income_total = cur.fetchone()[0] or 0

    cur.execute("SELECT amount,description,category FROM expenses WHERE user_id=?",
                (session["user_id"],))
    expenses = cur.fetchall()

    feedback = ai_feedback(income_total, monthly_total)

    return render_template(
        "dashboard.html",
        expenses=expenses,
        monthly_total=monthly_total,
        category_summary=category_summary,
        income_total=income_total,
        feedback=feedback
    )

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

import os
app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))