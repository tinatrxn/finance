import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Connect to PostgreSQL database
uri = os.getenv("DATABASE_URL")
if uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://")
db = SQL(uri)


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    if session.get('logged_in') == False:
        return redirect("/login")

    index = []
    profile = {}
    cash = 0
    total = 0

    # symbol | name | shares | current price | total
    #                                        | cash remaining
    #                                        | total (stocks + cash)

    cash_sql = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
    cash = cash_sql[0]["cash"]
    total = cash

    rows = db.execute("SELECT stock, SUM(shares) FROM profiles WHERE user_id = ? GROUP BY stock", session["user_id"])

    for i in rows:
        # make a dictionary for each stock, put into index
        profile["symbol"] = i["stock"]
        profile["shares"] = i["SUM(shares)"]

        quote_dic = lookup(profile["symbol"])
        profile["name"] = quote_dic["name"]
        profile["price"] = float(quote_dic["price"])

        profile["total"] = (float(profile["price"]) * float(profile["shares"]))
        total = float(total) + float(profile["total"])

        index.append(profile.copy())

    return render_template("index.html", index=index, cash=cash, total=total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # User reached route via POST (submit a form via POST)
    if request.method == "POST":

        quote_dic = lookup(request.form.get("symbol"))

        # Ensure symbol is valid
        if quote_dic == None:
            return apology("Provide a valid symbol", 400)

        # Ensure positive integer of stocks
        elif not request.form.get("shares"):
            return apology("Invalid number of shares", 403)

        # Ensure user can afford to purchase stocks
        price = quote_dic["price"]
        rows = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        cash = rows[0]["cash"]

        if (float(price) * float(request.form.get("shares"))) > cash:
            return apology("Insufficient funds bitch", 403)

        # Purchase stocks
        cash = cash - (float(price) * float(request.form.get("shares")))
        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash, session["user_id"])

        db.execute("INSERT INTO profiles (user_id, stock, shares, price, date) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)", session["user_id"], request.form.get("symbol").upper(), request.form.get("shares"), price)
        db.execute("INSERT INTO history (user_id, stock, shares, price, date) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)", session["user_id"], request.form.get("symbol").upper(), request.form.get("shares"), price)

        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")



@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    rows = db.execute("SELECT stock, shares, price, date FROM history WHERE user_id = ? ORDER BY date DESC", session["user_id"])

    return render_template("history.html", rows=rows)



@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    # User reached route via POST (submit a form via POST)
    if request.method == "POST":

        if not request.form.get("symbol"):
            return apology("provide a symbol", 400)

        quote_dic = lookup(request.form.get("symbol"))

        if quote_dic == None:
            return apology("Provide a valid symbol", 400)

        symbol = request.form.get("symbol")

        return render_template("quoted.html", name=quote_dic)

    # User reached route via GET (click link or via redirect)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # User reached route via POST (submit a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        elif not request.form.get("confirmation"):
            return apology("must confirm password", 400)

        # Query database for possible already existing username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username doesn't exist
        if len(rows) != 0:
            return apology("Username exists", 400)

        # Check matching passwords
        if request.form.get("password") != request.form.get("confirmation"):
            return apology("Passwords do not match")

        # INSERT new user into database
        username = request.form.get("username")
        password = generate_password_hash(request.form.get("password"))

        db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, password)

        # Sign user in
        rows2 = db.execute("SELECT * FROM users WHERE username = ?", username)
        session["user_id"] = rows2[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (click link/redirect)
    else:
        return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    # user reached route via POST (submit a form via POST)
    if request.method == "POST":

        quote_dic = lookup(request.form.get("symbol"))

        # Ensure symbol is valid
        if quote_dic == None:
            return apology("Provide a valid symbol", 403)

        # Ensure positive integer of stocks
        elif not request.form.get("shares"):
            return apology("Invalid number of shares", 403)

        # Ensure user has stock + amount of stock in profile
        rows = db.execute("SELECT stock, SUM(shares) FROM profiles WHERE user_id = ? GROUP BY stock", session["user_id"])

        stock_valid = 0
        stocks = 0

        for i in rows:
            if i["stock"] == request.form.get("symbol").upper():
                stock_valid = 1
                stocks = i["SUM(shares)"]

        if stock_valid == 0:
            return apology("You don't own this stock", 403)

        elif int(request.form.get("shares")) > stocks:
            return apology("You don't own that many stocks", 403)

        # Update earnings
        rows2 = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        cash = rows2[0]["cash"] + (float(quote_dic["price"]) * float(stocks))

        # Selling stock
        db.execute("INSERT INTO history (user_id, stock, shares, price, date) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)", session["user_id"], request.form.get("symbol").upper(), -abs(int(request.form.get("shares"))), quote_dic["price"])
        db.execute("DELETE FROM profiles WHERE user_id = ? AND stock = ? LIMIT ?", session["user_id"], request.form.get("symbol").upper(), int(request.form.get("shares")))
        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash, session["user_id"])

        return redirect("/")

    # User reached route via GET (click link/redirect)
    else:
        return render_template("sell.html")
