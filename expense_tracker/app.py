from flask import Flask, render_template, request, redirect, session
import sqlite3
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from apscheduler.schedulers.background import BackgroundScheduler

# ML
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.naive_bayes import MultinomialNB

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

# ===================== AI MODEL =====================
train_texts = [
    "food pizza burger meal snack coffee tea",
    "restaurant lunch dinner breakfast",
    "bus train petrol fuel uber auto taxi",
    "travel taxi fuel petrol","bike petrol fuel ride",
    "medicine drug hospital doctor",
    "college fees book books exam course study",
    "education tuition class book notebook",
    "wifi recharge electricity bill data mobile",
    "mobile recharge internet bill",
    "movie netflix game fun entertainment",
    "cinema gaming subscription",
    "amazon shopping clothes shirt buy",
    "flipkart purchase shopping clothes"
]

train_labels = [
    "Food","Food",
    "Transport","Transport","Transport",
    "Medical",
    "Education","Education",
    "Utilities","Utilities",
    "Entertainment","Entertainment",
    "Shopping","Shopping"
]

vectorizer = CountVectorizer()
X = vectorizer.fit_transform(train_texts)
model = MultinomialNB()
model.fit(X, train_labels)

def ai_category(text):
    text = text.lower().strip()
    # RULE-BASED CATEGORIES
    if any(x in text for x in ["book","pen","notebook","study","fees","exam","college"]):
        return "Education"
    if any(x in text for x in ["petrol","fuel","bus","train","uber","auto","bike","travel"]):
        return "Transport"
    if any(x in text for x in ["food","pizza","burger","coffee","eat","meal"]):
        return "Food"
    if any(x in text for x in ["movie","netflix","game","fun"]):
        return "Entertainment"
    if any(x in text for x in ["amazon","shopping","shirt","clothes","buy"]):
        return "Shopping"
    if any(x in text for x in ["recharge","wifi","bill","electricity","data"]):
        return "Utilities"
    if any(x in text for x in ["medicine","drug","hospital","doctor","tablet"]):
        return "Medical"

    # ML fallback
    text_vec = vectorizer.transform([text])
    probs = model.predict_proba(text_vec)[0]
    if max(probs) < 0.5:
        return "Other"
    return model.classes_[probs.argmax()]

# ===================== AI FEEDBACK =====================
def ai_feedback(income, expense, summary, expenses):
    if income == 0:
        return "Add income to unlock AI insights."
    p = (expense / income) * 100
    top_category = max(summary, key=lambda x: x[1])[0] if summary else "None"
    msg = ""
    if p > 90:
        msg = "⚠ You are overspending heavily."
    elif p > 70:
        msg = "You are close to your limit."
    else:
        msg = "Spending is under control."
    msg += f" Most spending is on {top_category}."
    return msg

# ===================== SMART ALERTS =====================
def check_alerts(user_id):
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT SUM(amount) FROM income WHERE user_id=?", (user_id,))
    income = cur.fetchone()[0] or 0
    cur.execute("SELECT SUM(amount) FROM expenses WHERE user_id=?", (user_id,))
    expense = cur.fetchone()[0] or 0

    alerts = []
    if income > 0 and expense / income > 0.8:
        alerts.append("⚠ Your expenses are above 80% of your income!")

    # Last 7 days category spike
    cur.execute("""
        SELECT category, SUM(amount)
        FROM expenses
        WHERE user_id=? AND date >= date('now','-7 days')
        GROUP BY category
    """, (user_id,))
    last_week = cur.fetchall()
    for cat, amt in last_week:
        if amt > 1000:  # example threshold
            alerts.append(f"⚠ High spending in {cat} this week: {amt}")
    db.close()
    return alerts

# ===================== REPORT GENERATION =====================
def generate_report(user_id, period='week'):
    db = get_db()
    cur = db.cursor()
    if period == 'week':
        date_filter = "date >= date('now','-7 days')"
    elif period == 'month':
        date_filter = "date >= date('now','start of month')"
    else:
        return ""
    cur.execute(f"SELECT SUM(amount) FROM income WHERE user_id=? AND {date_filter}", (user_id,))
    income = cur.fetchone()[0] or 0
    cur.execute(f"SELECT SUM(amount) FROM expenses WHERE user_id=? AND {date_filter}", (user_id,))
    expense = cur.fetchone()[0] or 0
    cur.execute(f"""
        SELECT category, SUM(amount)
        FROM expenses
        WHERE user_id=? AND {date_filter}
        GROUP BY category
    """, (user_id,))
    summary = cur.fetchall()
    report = f"Report ({period})\nIncome: {income}\nExpenses: {expense}\nCategory-wise spending:\n"
    for cat, amt in summary:
        report += f"- {cat}: {amt}\n"
    return report

# ===================== EMAIL =====================
def send_email(to_email, subject, body):
    from_email = "ai.expense.tracker11@gmail.com"
    password = "ccfi suek bpzv genw"  # Use app password for Gmail
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = from_email
    msg['To'] = to_email
    server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
    server.login(from_email, password)
    server.sendmail(from_email, [to_email], msg.as_string())
    server.quit()

def send_weekly_reports():
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id, email FROM users")
    users = cur.fetchall()
    for user_id, email in users:
        report = generate_report(user_id, 'week')
        send_email(email, "Weekly Expense Report", report)
    db.close()

def send_monthly_reports():
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id, email FROM users")
    users = cur.fetchall()
    for user_id, email in users:
        report = generate_report(user_id, 'month')
        send_email(email, "Monthly Expense Report", report)
    db.close()

# ===================== SCHEDULER =====================
scheduler = BackgroundScheduler()
scheduler.add_job(send_weekly_reports, 'cron', day_of_week='mon', hour=8)   # every Monday 8 AM
scheduler.add_job(send_monthly_reports, 'cron', day=1, hour=8)               # every 1st of month 8 AM
scheduler.start()

# ===================== FLASK ROUTES =====================
@app.route("/", methods=["GET","POST"])
def login():
    if request.method == "POST":
        db = get_db()
        cur = db.cursor()
        cur.execute("SELECT * FROM users WHERE email=? AND password=?",
                    (request.form["email"],request.form["password"]))
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
                    (request.form["name"],request.form["email"],request.form["password"]))
        db.commit()
        db.close()
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

    # totals
    cur.execute("SELECT SUM(amount) FROM income WHERE user_id=?",(session["user_id"],))
    income = cur.fetchone()[0] or 0
    cur.execute("SELECT SUM(amount) FROM expenses WHERE user_id=?",(session["user_id"],))
    expense = cur.fetchone()[0] or 0

    # monthly data
    cur.execute("SELECT strftime('%m',date),SUM(amount) FROM expenses WHERE user_id=? GROUP BY strftime('%m',date)",
                (session["user_id"],))
    em = dict(cur.fetchall())
    cur.execute("SELECT strftime('%m',date),SUM(amount) FROM income WHERE user_id=? GROUP BY strftime('%m',date)",
                (session["user_id"],))
    im = dict(cur.fetchall())
    months = ["01","02","03","04","05","06","07","08","09","10","11","12"]
    expense_data = [em.get(m,0) for m in months]
    income_data = [im.get(m,0) for m in months]

    # summary
    cur.execute("SELECT category,SUM(amount) FROM expenses WHERE user_id=? GROUP BY category",
                (session["user_id"],))
    summary = cur.fetchall()

    # expenses table
    cur.execute("SELECT id,amount,description,category FROM expenses WHERE user_id=? ORDER BY date DESC",
                (session["user_id"],))
    expenses = cur.fetchall()

    # income list
    cur.execute("SELECT id,amount FROM income WHERE user_id=? ORDER BY date DESC",
                (session["user_id"],))
    income_list = cur.fetchall()
    db.close()

    feedback = ai_feedback(income, expense, summary, expenses)
    alerts = check_alerts(session["user_id"])

    return render_template("dashboard.html",
        income=income,
        expense=expense,
        income_data=income_data,
        expense_data=expense_data,
        summary=summary,
        expenses=expenses,
        income_list=income_list,
        feedback=feedback,
        alerts=alerts
    )

@app.route("/add_income", methods=["POST"])
def add_income():
    db = get_db()
    cur = db.cursor()
    cur.execute("INSERT INTO income VALUES(NULL,?,?,CURRENT_TIMESTAMP)",
                (session["user_id"],request.form["income"]))
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
    app.run(host="0.0.0.0", port=5000, debug=True)
