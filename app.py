import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, isPositiveInteger, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


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

    # Get stocks data for current user
    stocks = db.execute("SELECT stocks.shares, companies.symbol, companies.name FROM stocks INNER JOIN companies ON stocks.symbolid = companies.id WHERE stocks.userid = ? ORDER BY companies.symbol", session.get("user_id"))

    # Get cash ammount
    row = db.execute("SELECT cash FROM users WHERE id = ?", session.get("user_id"))
    cash = row[0]["cash"]

    # Sum cash and stocks value further
    totalCash = cash

    # Collect data for every stock user owns
    for stock in stocks:

        # Get current price for each stock
        quote = lookup(stock["symbol"])

        # Ensure response exists
        if quote == None:
            return apology("Can't get actual price", 500)

        # Add stock price into the list
        stock["price"] = quote["price"]

        # Sum stock value
        stock["value"] = stock["price"] * stock["shares"]

        # Add to total cash
        totalCash += stock["value"]

    # Render users stock list
    return render_template("index.html", stocks=stocks, cash=cash, totalCash=totalCash)


@app.route("/add_cash", methods=["GET", "POST"])
@login_required
def add_cash():
    """Add cash on user account"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Add cash
        db.execute("UPDATE users SET cash = ? WHERE id = ?", 10000, session.get("user_id"))

        return redirect("/")

    # User reached route via GET
    else:
        return redirect("/")


@app.route("/change_password", methods=["GET", "POST"])
@login_required
def change_password():
    """Change password of users account"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure  current password was submitted
        if not request.form.get("password"):
            return apology("must provide current password", 403)

        # Ensure new password was submitted
        elif not request.form.get("new_password") or not request.form.get("confirmation"):
            return apology("must provide new password", 403)

        # Ensure passwords input is match
        elif request.form.get("new_password") != request.form.get("confirmation"):
            return apology("new passwords do not match", 403)

        # Check current password
        password = db.execute("SELECT hash FROM users WHERE id = ?", session.get("user_id"))
        if len(password) != 1 or not check_password_hash(password[0]["hash"], request.form.get("password")):
            return apology("Invalid password", 403)

        # Check new password do not match with current one
        elif request.form.get("password") == request.form.get("new_password"):
            return apology("New password shouldn't match with old one", 403)

        # Change password in database
        db.execute("UPDATE users SET hash = ? WHERE id = ?", generate_password_hash(
            request.form.get("new_password")), session.get("user_id"))

        # Reditect user to home page
        flash("You successfully changed the password!")
        return redirect("/")

    # User reached route via GET
    else:
        return render_template("change_password.html")


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("must provide symbol", 403)

        # Ensure shares were submitted
        elif not request.form.get("shares"):
            return apology("must provide shares", 403)

        # Ensure shares is a positive integer
        if not isPositiveInteger(request.form.get("shares")):
            return apology("must provide shares as a positive integer", 403)

        # Send request to the iexpis.com to get quote
        quote = lookup(request.form.get("symbol"))

        # Ensure response exists
        if quote == None:
            return apology("Invalid symbol", 403)

        # Check amount of cash
        cash = db.execute("SELECT cash FROM users WHERE id = ?", session.get("user_id"))

        # Count total price
        totalPrice = quote["price"] * int(request.form.get("shares"))

        # Ensure user have enough cash
        if len(cash) != 1 or cash[0]["cash"] < totalPrice:
            return apology("You dont have enough cash", 403)

        # Check stock symbol
        checkSymbol = db.execute("SELECT id FROM companies WHERE symbol = ?", quote["symbol"])

        # Create new company in database if it doesnt exist
        if len(checkSymbol) != 1:
            db.execute("INSERT INTO companies (symbol, name) VALUES (?, ?)", quote["symbol"], quote["name"])
            checkSymbol = db.execute("SELECT id FROM companies WHERE symbol = ?", quote["symbol"])

        # Check ammount of shares
        checkStock = db.execute("SELECT shares FROM stocks WHERE symbolid = ? AND userid = ?",
            checkSymbol[0]["id"], session.get("user_id"))

        # Create new position in stocks if it doesnt exist for this user
        if len(checkStock) != 1:
            db.execute("INSERT INTO stocks (symbolid, shares, userid) VALUES (?, ?, ?)", checkSymbol[0]["id"], int(
                request.form.get("shares")), session.get("user_id"))

        # Add shares to the users stock
        else:
            db.execute("UPDATE stocks SET shares = ? WHERE userid = ? AND symbolid = ?", int(
                request.form.get("shares")) + checkStock[0]["shares"], session.get("user_id"), checkSymbol[0]["id"])

        # Debit a cash account
        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash[0]["cash"] - totalPrice, session.get("user_id"))

        # Add note in history
        db.execute("INSERT INTO history (symbolid, shares, price, userid) VALUES (?, ?, ?, ?)", checkSymbol[0]["id"], int(
            request.form.get("shares")), totalPrice, session.get("user_id"))

        # Redirect user to home page
        flash("You made a successful purchase!")
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    # Request database for history of operrations
    history = db.execute("SELECT history.shares, history.price, history.time, companies.symbol FROM history INNER JOIN companies ON history.symbolid = companies.id WHERE history.userid = ? ORDER BY history.time DESC", session.get("user_id"))

    # Render history of operations
    return render_template("history.html", history=history)


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

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Send request to the iexpis.com to get quote
        quote = lookup(request.form.get("symbol"))

        # Ensure response exists
        if quote == None:
            return apology("Invalid symbol", 403)

        # render response
        return render_template("quote.html", quote=quote)

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password") or not request.form.get("confirmation"):
            return apology("must provide password", 403)

        # Ensure passwords input is match
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords do not match", 403)

        # Query database for username
        rows = db.execute("SELECT username FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username didn't already exists
        if len(rows) != 0 and rows[0]["username"] == request.form.get("username"):
            return apology("username already exists", 403)

        # Add user to database
        db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", request.form.get(
            "username"), generate_password_hash(request.form.get("password")))

        # Redirect user to login page with success message
        flash("You are successfully registered!")
        return render_template("login.html")

    else:
        return render_template("/register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("must provide symbol", 403)

        # Ensure shares were submitted
        elif not request.form.get("shares"):
            return apology("must provide shares", 403)

        # Ensure shares is a positive integer
        if not isPositiveInteger(request.form.get("shares")):
            return apology("must provide shares as a positive integer", 403)

        # Send request to the iexpis.com to get quote
        quote = lookup(request.form.get("symbol"))

        # Ensure response exists
        if quote == None:
            return apology("Invalid symbol", 403)

        # Check stock symbol to ensure it exists in database
        checkSymbol = db.execute("SELECT id FROM companies WHERE symbol = ?", quote["symbol"])

        if len(checkSymbol) != 1:
            return apology("You don't own this stock")

        # Ensure user does own this stock with that many shares
        checkStock = db.execute("SELECT shares FROM stocks WHERE userid = ? AND symbolid = ?",
            session.get("user_id"), checkSymbol[0]["id"])

        if len(checkStock) != 1:
            return apology("You don't own this stock")

        elif checkStock[0]["shares"] < int(request.form.get("shares")):
            return apology("You don't own this many shares")

        # Count total price
        totalPrice = quote["price"] * int(request.form.get("shares"))

        # Check amount of cash
        cash = db.execute("SELECT cash FROM users WHERE id = ?", session.get("user_id"))

        # Remove shares from users stock
        db.execute("UPDATE stocks SET shares = ? WHERE userid = ? AND symbolid = ?", checkStock[0]["shares"] - int(
            request.form.get("shares")), session.get("user_id"), checkSymbol[0]["id"])

        # Credit a cash account
        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash[0]["cash"] + totalPrice, session.get("user_id"))

        # Add note in history
        db.execute("INSERT INTO history (symbolid, shares, price, userid) VALUES (?, ?, ?, ?)", checkSymbol[0]["id"], int(
            request.form.get("shares")) * -1, totalPrice, session.get("user_id"))

        # Redirect user to home page
        flash("You sold successfully!")
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("sell.html")
