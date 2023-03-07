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
    return apology("TODO")


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("must provide symbol", 403)

        # Ensure shares were submitted as a positive integer
        elif not request.form.get("shares") or int(request.form.get("shares")) <= 0:
            return apology("must provide shares as a positive integer", 403)

        # Send request to the iexpis.com to get quote
        quote = lookup(request.form.get("symbol"))

        #Ensure response exists
        if quote == None:
            return apology("Invalid symbol", 403)

        # Check amount of cash
        cash = db.execute("SELECT cash FROM users WHERE id = ?", session.get("user_id"))

        #Count total price
        totalPrice = quote["price"] * int(request.form.get("shares"))

        # Ensure user have enough cash
        if len(cash) != 1 or cash[0]["cash"] < totalPrice:
            return apology("You dont have enough cash", 403)

        # Check stock symbol and ammount of shares
        checkSymbol = db.execute("SELECT id FROM companies WHERE symbol = ?", quote["symbol"])
        checkStock = db.execute("SELECT shares FROM stocks WHERE symbolid = ? AND userid = ?", checkSymbol[0]["id"], session.get("user_id"))

        # Create new position if it doesnt exist
        if len(checkSymbol) != 1:
            db.execute("INSERT INTO companies (symbol, name) VALUES (?, ?)", quote["symbol"], quote["name"])
            checkSymbol = db.execute("SELECT id FROM companies WHERE symbol = ?", quote["symbol"])

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
        db.execute("INSERT INTO history (symbolid, shares, price, userid) VALUES (?, ?, ?, ?)", checkSymbol[0]["id"], str(
            "+" + request.form.get("shares")), quote["price"], session.get("user_id"))

        # Redirect user to home page
        flash("You've successfully purchased!")
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    return apology("TODO")


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

        #Ensure response exists
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
    return apology("TODO")
