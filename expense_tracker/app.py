from flask import Flask, render_template, request, redirect, session
import sqlite3

app = Flask(name)
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

# AI Category
def ai_category(text):
# ===== REAL AI CATEGORY USING ML =====
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.naive_bayes import MultinomialNB

# Training data (simple but effective)
train_texts = [
    "pizza burger food", "coffee snack restaurant",
    "bus train petrol fuel uber",
    "college fees books exam course",
    "wifi recharge electricity bill",
    "movie netflix game fun",
    "amazon shopping clothes shirt"
]

train_labels = [
    "Food","Food",
    "Transport",
    "Education",
    "Utilities",
    "Entertainment",
    "Shopping"
]

vectorizer = CountVectorizer()
X = vectorizer.fit_transform(train_texts)

model = MultinomialNB()
model.fit(X, train_labels)


def ai_category(text):
    text_vec = vectorizer.transform([text.lower()])
    return model.predict(text_vec)[0]

def ai_feedback(income, expense, summary, expenses):
    if income == 0:
        return "Add income to unlock AI insights."

    p = (expense / income) * 100

    # Top category
    top_category = max(summary, key=lambda x: x[1])[0] if summary else "None"

    # Spending trend (recent behavior)
    recent = expenses[:3]  # last 3 expenses
    recent_total = sum([e[1] for e in recent]) if recent else 0

    msg = ""

    if p > 90:
        msg = "⚠ You are overspending heavily."
    elif p > 70:
        msg = "You are close to your limit."
    else:
        msg = "Spending is under control."

    msg += f" Most spending is on {top_category}."

    if recent_total > (income * 0.5):
        msg += " Recent expenses are unusually high."

    # Student advice
    advice = {
        "Food": "Try cooking or reducing outside food.",
        "Entertainment": "Limit subscriptions and outings.",
        "Shopping": "Avoid impulse buying.",
        "Transport": "Use public transport to save money."
    }

    if top_category in advice:
        msg += " " + advice[top_category]

    return msg
# LOGIN
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

# REGISTER
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

# DASHBOARD
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

    # totals
    cur.execute("SELECT SUM(amount) FROM income WHERE user_id=?",(session["user_id"],))
    income = cur.fetchone()[0] or 0

    cur.execute("SELECT SUM(amount) FROM expenses WHERE user_id=?",(session["user_id"],))
    expense = cur.fetchone()[0] or 0

    # monthly
    cur.execute("SELECT strftime('%m',date),SUM(amount) FROM expenses WHERE user_id=? GROUP BY strftime('%m',date)",
                (session["user_id"],))
    em = dict(cur.fetchall())

    cur.execute("SELECT strftime('%m',date),SUM(amount) FROM income WHERE user_id=? GROUP BY strftime('%m',date)",
                (session["user_id"],))
    im = dict(cur.fetchall())

    months = ["02","03","04","05","06","07"]
    expense_data = [em.get(m,0) for m in months]
    income_data = [im.get(m,0) for m in months]

    # donut
    cur.execute("SELECT category,SUM(amount) FROM expenses WHERE user_id=? GROUP BY category",
                (session["user_id"],))
    s = cur.fetchall()

    # table
    cur.execute("SELECT id,amount,description,category FROM expenses WHERE user_id=? ORDER BY date DESC",
    (session["user_id"],))
    expenses = cur.fetchall()

    # summary
    cur.execute("SELECT category,SUM(amount) FROM expenses WHERE user_id=? GROUP BY category",
                (session["user_id"],))
    summary = cur.fetchall()

    feedback = ai_feedback(income,expense)

    return render_template("dashboard.html",
        income=income, expense=expense,
        income_data=income_data, expense_data=expense_data,
        categories=[i[0] for i in s],
        amounts=[i[1] for i in s],
        feedback=feedback,
        expenses=expenses,
        summary=summary
    )

# ADD INCOME
@app.route("/add_income", methods=["POST"])
def add_income():
    db = get_db()
    cur = db.cursor()
    cur.execute("INSERT INTO income VALUES(NULL,?,?,CURRENT_TIMESTAMP)",
                (session["user_id"],request.form["income"]))
    db.commit()
    return redirect("/dashboard")

# DELETE
@app.route("/delete/<int:id>")
def delete(id):
    db = get_db()
    cur = db.cursor()
    cur.execute("DELETE FROM expenses WHERE id=? AND user_id=?",
                (id, session["user_id"]))
    db.commit()
    return redirect("/dashboard")

# LOGOUT
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

app.run(debug=True)
