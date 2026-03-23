from flask import Flask, render_template, request, redirect, session
import sqlite3
import smtplib
from email.mime.text import MIMEText
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)
app.secret_key = "secret123"

# ===================== DATABASE =====================
def get_db():
    return sqlite3.connect("database.db")

def init_db():
    db = get_db()
    cur = db.cursor()

    cur.execute("""CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT,
        password TEXT)""")

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

# ===================== AI CATEGORY =====================
def ai_category(text):
    text = text.lower()

    if any(x in text for x in ["book","study","fees","exam","college"]):
        return "Education"
    if any(x in text for x in ["petrol","fuel","bus","train","uber","auto","bike"]):
        return "Transport"
    if any(x in text for x in ["food","pizza","burger","coffee","meal"]):
        return "Food"
    if any(x in text for x in ["movie","netflix","game"]):
        return "Entertainment"
    if any(x in text for x in ["shopping","amazon","clothes"]):
        return "Shopping"
    if any(x in text for x in ["recharge","wifi","bill","electricity"]):
        return "Utilities"
    if any(x in text for x in ["medicine","hospital","doctor"]):
        return "Medical"

    return "Other"

# ===================== EMAIL =====================
def send_email(to_email, subject, body):
    from_email = "ai.expense.tracker11@gmail.com"
    password = "ccfi suek bpzv genw"

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = from_email
    msg['To'] = to_email

    server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
    server.login(from_email, password)
    server.sendmail(from_email, [to_email], msg.as_string())
    server.quit()

def generate_report(user_id):
    db = get_db()
    cur = db.cursor()

    cur.execute("SELECT SUM(amount) FROM income WHERE user_id=?", (user_id,))
    income = cur.fetchone()[0] or 0

    cur.execute("SELECT SUM(amount) FROM expenses WHERE user_id=?", (user_id,))
    expense = cur.fetchone()[0] or 0

    cur.execute("""
        SELECT category, SUM(amount)
        FROM expenses
        WHERE user_id=?
        GROUP BY category
    """, (user_id,))
    summary = cur.fetchall()

    report = f"Weekly Report\n\nIncome: {income}\nExpense: {expense}\n\nCategory:\n"
    for cat, amt in summary:
        report += f"{cat}: {amt}\n"

    db.close()
    return report

def weekly_email():
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id,email FROM users")
    users = cur.fetchall()

    for uid, email in users:
        report = generate_report(uid)
        send_email(email, "Weekly Expense Report", report)

    db.close()

# Scheduler (testing every 2 mins)
scheduler = BackgroundScheduler()
scheduler.add_job(weekly_email, 'interval', minutes=2)
scheduler.start()

# ===================== ROUTES =====================

@app.route("/", methods=["GET","POST"])
def login():
    if request.method == "POST":
        db = get_db()
        cur = db.cursor()

        cur.execute("SELECT * FROM users WHERE email=? AND password=?",
                    (request.form["email"], request.form["password"]))
        user = cur.fetchone()

        db.close()

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
                    (request.form["name"], request.form["email"], request.form["password"]))

        db.commit()
        db.close()

        return redirect("/")

    return render_template("register.html")


@app.route("/dashboard", methods=["GET","POST"])
def dashboard():
    if "user_id" not in session:
        return redirect("/")

    db = get_db()
    cur = db.cursor()

    # ADD EXPENSE
    if request.method == "POST":
        amt = request.form["amount"]
        desc = request.form["description"]
        cat = ai_category(desc)

        cur.execute("INSERT INTO expenses VALUES(NULL,?,?,?,?,CURRENT_TIMESTAMP)",
                    (session["user_id"], amt, desc, cat))
        db.commit()

    # TOTALS
    cur.execute("SELECT SUM(amount) FROM income WHERE user_id=?", (session["user_id"],))
    income = cur.fetchone()[0] or 0

    cur.execute("SELECT SUM(amount) FROM expenses WHERE user_id=?", (session["user_id"],))
    expense = cur.fetchone()[0] or 0

    # MONTHLY DATA
    cur.execute("SELECT strftime('%m',date),SUM(amount) FROM expenses WHERE user_id=? GROUP BY strftime('%m',date)",
                (session["user_id"],))
    em = dict(cur.fetchall())

    cur.execute("SELECT strftime('%m',date),SUM(amount) FROM income WHERE user_id=? GROUP BY strftime('%m',date)",
                (session["user_id"],))
    im = dict(cur.fetchall())

    months = ["01","02","03","04","05","06","07","08","09","10","11","12"]

    expense_data = [em.get(m,0) for m in months]
    income_data = [im.get(m,0) for m in months]

    # CATEGORY SUMMARY
    cur.execute("SELECT category,SUM(amount) FROM expenses WHERE user_id=? GROUP BY category",
                (session["user_id"],))
    summary = cur.fetchall()

    # TABLE DATA
    cur.execute("SELECT id,amount,description,category FROM expenses WHERE user_id=? ORDER BY date DESC",
                (session["user_id"],))
    expenses = cur.fetchall()

    cur.execute("SELECT id,amount FROM income WHERE user_id=? ORDER BY date DESC",
                (session["user_id"],))
    income_list = cur.fetchall()

    db.close()

    feedback = "Spending looks good" if expense < income else "You are overspending!"

    return render_template("dashboard.html",
                           income=income,
                           expense=expense,
                           income_data=income_data,
                           expense_data=expense_data,
                           summary=summary,
                           expenses=expenses,
                           income_list=income_list,
                           feedback=feedback,
                           alerts=[])


@app.route("/add_income", methods=["POST"])
def add_income():
    if "user_id" not in session:
        return redirect("/")

    db = get_db()
    cur = db.cursor()

    cur.execute("INSERT INTO income VALUES(NULL,?,?,CURRENT_TIMESTAMP)",
                (session["user_id"], request.form["income"]))

    db.commit()
    db.close()

    return redirect("/dashboard")


@app.route("/delete/<int:id>")
def delete(id):
    db = get_db()
    cur = db.cursor()

    cur.execute("DELETE FROM expenses WHERE id=? AND user_id=?",
                (id, session["user_id"]))

    db.commit()
    db.close()

    return redirect("/dashboard")


@app.route("/delete_income/<int:id>")
def delete_income(id):
    db = get_db()
    cur = db.cursor()

    cur.execute("DELETE FROM income WHERE id=? AND user_id=?",
                (id, session["user_id"]))

    db.commit()
    db.close()

    return redirect("/dashboard")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


if __name__ == "__main__":
    app.run(debug=True)
