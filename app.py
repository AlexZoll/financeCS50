import os

from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, check_password, login_required, lookup, usd
from models import *

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure sqlalchemy to use
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///finance.db"
db.init_app(app)

with app.app_context():
    db.create_all()

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
    stocks = Stocks.query.filter_by(userid=session.get("user_id")).all()

    # Get cash ammount
    cash = Users.query.filter_by(id=session.get("user_id")).scalar()
    if cash is None:
        return apology("Couldn't find a data", 403)

    # Sum cash and stocks value further
    totalCash = float(cash.cash)

    # Collect data for every stock user owns
    for stock in stocks:

        # Get current price for each stock
        quote = lookup(stock.company.symbol)

        # Ensure response exists
        if quote is None:
            return apology("Can't get actual price", 500)

        # Add stock price and value into the list
        stock.price = quote["price"]
        stock.value = quote["price"] * stock.shares

        # Add to total cash
        totalCash += stock.value

    # Render users stock list
    return render_template("index.html",  cash=cash.cash, stocks=stocks, totalCash=totalCash)


@app.route("/add_cash", methods=["GET", "POST"])
@login_required
def add_cash():
    """Add cash on user account"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Add cash
        cash = Users.query.filter(Users.id == session.get("user_id")).scalar()
        if cash is None:
            return apology("Can't add cash", 403)

        cash.cash = 10000
        db.session.add(cash)
        db.session.commit()

        return redirect("/")

    # User reached route via GET
    else:
        return redirect("/")


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
        if not (request.form.get("shares")).isdigit() or int(request.form.get("shares")) == 0:
            return apology("must provide shares as a positive integer", 403)

        # Send request to the iexpis.com to get quote
        quote = lookup(request.form.get("symbol"))

        # Ensure response exists
        if quote is None:
            return apology("Invalid symbol", 403)

        # Check amount of cash
        cash = Users.query.filter_by(id=session.get("user_id")).scalar()

        # Count total price
        price = quote["price"] * int(request.form.get("shares"))

        # Ensure user have enough cash
        if cash is None or float(cash.cash) < price:
            return apology("You dont have enough cash", 403)

        # Check stock symbol
        symbol = Companies.query.filter_by(symbol=quote["symbol"]).scalar()

        # Create new company in database if it doesnt exist
        if symbol is None:
            newCompany = Companies(symbol=quote["symbol"], name=quote["name"])
            db.session.add(newCompany)
            db.session.flush()

            # Check stock symbol again after adding in database
            symbol = Companies.query.filter_by(symbol=quote["symbol"]).scalar()

        # Check ammount of shares
        stock = Stocks.query.filter_by(userid=session.get("user_id"), symbolid=symbol.id).scalar()

        # Create new position in stocks if it doesnt exist for this user
        if stock is None:
            db.session.add(Stocks(symbol.id, request.form.get("shares"), session.get("user_id")))

        # Add shares to the users stock
        else:
            stock.shares = int(request.form.get("shares")) + stock.shares

        # Debit a cash account
        cash.cash = float(cash.cash) - price

        # Add note in history
        transaction = History(symbolid=symbol.id, shares=request.form.get("shares"), price=price, userid=session.get("user_id"))
        db.session.add(transaction)

        # Apply changes and redirect user to home page
        db.session.commit()
        flash("You made a successful purchase!")
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")


@app.route("/change_password", methods=["GET", "POST"])
@login_required
def change_password():
    """Change password of the users account"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure  current password was submitted
        if not request.form.get("password"):
            return apology("must provide current password", 403)

        # Ensure new password was submitted
        elif not request.form.get("new_password") or not request.form.get("confirmation"):
            return apology("must provide new password", 403)

        # Ensure password has all requires
        elif not check_password(request.form.get("new_password")):
            return apology("password must be from 8 to 16 characters long and consists of at least one digit, "
                "one lowercase and uppercase letter and one of special symbols @#$%&-_/")

        # Ensure passwords input is match
        elif request.form.get("new_password") != request.form.get("confirmation"):
            return apology("new passwords do not match", 403)

        # Check current password
        row = Users.query.filter(Users.id == session.get("user_id")).scalar()
        if row is None or not check_password_hash(row.hash, request.form.get("password")):
            return apology("Invalid password", 403)

        # Check new password do not match with current one
        elif request.form.get("password") == request.form.get("new_password"):
            return apology("New password shouldn't match with old one", 403)

        # Change password in database
        row.hash = generate_password_hash(request.form.get("new_password"))
        db.session.commit()

        # Reditect user to home page
        flash("You successfully changed the password!")
        return render_template("login.html")

    # User reached route via GET
    else:
        return render_template("change_password.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    # Request database for history of operrations
    history = History.query.order_by(History.time.desc()).filter_by(userid=session.get("user_id")).all()

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
        user = Users.query.filter_by(username=request.form.get("username")).scalar()

        # Ensure username exists and password is correct
        if user is None or not check_password_hash(user.hash, request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = user.id

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
        if quote is None:
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

        # Ensure password has all requires
        elif not check_password(request.form.get("password")):
            return apology("password must be from 8 to 16 characters long and consists of at least one digit, "
                "one lowercase and uppercase letter and one of special symbols @#$%&-_/")

        # Ensure passwords input is match
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords do not match", 403)

        # Query database for username
        row = Users.query.filter(Users.username == request.form.get("username")).scalar()

        # Ensure username didn't already exists
        if row:
            return apology("username already exists", 403)

        # Add user to database
        db.session.add(Users(username=request.form.get("username"), hash=generate_password_hash(request.form.get("password"))))
        db.session.commit()

        # Redirect user to login page with success message
        flash("You are successfully registered!")
        return redirect("/login")

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
        if not request.form.get("shares").isdigit() or int(request.form.get("shares")) == 0:
            return apology("must provide shares as a positive integer", 403)

        # Send request to the iexpis.com to get quote
        quote = lookup(request.form.get("symbol"))

        # Ensure response exists
        if quote is None:
            return apology("Invalid symbol", 403)

        # Check stock symbol to ensure it exists in database
        symbol = Companies.query.filter_by(symbol=quote["symbol"]).scalar()

        if symbol is None:
            return apology("You don't own this stock")

        # Ensure user does own this stock with that many shares
        stock = Stocks.query.filter_by(userid=session.get("user_id"), symbolid=symbol.id).scalar()

        if stock is None:
            return apology("You don't own this stock")

        elif stock.shares < int(request.form.get("shares")):
            return apology("You don't own this many shares")

        # Count total price
        price = quote["price"] * int(request.form.get("shares"))

        # Check amount of cash
        cash = Users.query.filter_by(id=session.get("user_id")).scalar()
        if cash is None:
            return apology("You dont have enough cash", 403)

        # Delete row in database if all shares sold
        if stock.shares == int(request.form.get("shares")):
            db.session.delete(stock)

        # Or update shares
        else:
            stock.shares = stock.shares - int(request.form.get("shares"))

        # Credit a cash account
        cash.cash = float(cash.cash) + price

        # Add note in history
        transaction = History(symbolid=symbol.id, shares=int(request.form.get("shares"))
            * -1, price=price, userid=session.get("user_id"))
        db.session.add(transaction)

        # Apply changes and redirect user to home page
        db.session.commit()
        flash("You sold successfully!")
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("sell.html")
