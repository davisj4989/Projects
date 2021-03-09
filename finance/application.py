import json
import os
import requests
from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")

@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    #check method
    if request.method == "GET":
        #load cash on hand from user
        users = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=session["user_id"])
        cash = users[0]['cash']
        #load stocks owned by user
        stocks = db.execute("SELECT symbol, name, SUM(qty) AS totalshares FROM transactions WHERE id = :user_id GROUP BY symbol HAVING totalshares > 0", user_id=session["user_id"])
        print(stocks)
        quotes = {}
        total_stock = 0
        #loop data for portfolio
        for i in stocks:
            quotes[i["symbol"]] = lookup(i["symbol"])
            total_stock = total_stock + (float(quotes[i["symbol"]]["price"]) * i['totalshares'])
        total_cash = total_stock + cash
        return render_template("portfolio.html", cash=cash, stocks=stocks, quotes=quotes, total_cash=total_cash)
    else:
        #add cash // check that qty was entered and greater than 0
        if request.form.get("qty") == "":
            return apology("Must enter amount", 400)
        qty = int(request.form.get("qty"))
        if qty < 0:
            return apology("Amount must be greater than 0", 400)
        #get user cash and update it with new total
        cash = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=session["user_id"])
        coh = cash[0]['cash']
        cashbal = coh + qty
        symbol = "CASH"
        #update user and transactions table // load date to refresh portfolio
        db.execute("UPDATE users SET cash = :cashbal WHERE id = :user_id", cashbal=cashbal, user_id=session["user_id"])
        db.execute("INSERT INTO transactions (id, symbol, total) VALUES (:user_id, :symbol, :total)", user_id=session["user_id"], symbol=symbol, total=qty)
        stocks = db.execute("SELECT symbol, name, SUM(qty) AS totalshares FROM transactions WHERE id = :user_id GROUP BY symbol HAVING totalshares > 0", user_id=session["user_id"])
        quotes = {}
        total_stock = 0
        for i in stocks:
            quotes[i["symbol"]] = lookup(i["symbol"])
            total_stock = total_stock + (float(quotes[i["symbol"]]["price"]) * i["totalshares"])
        total_cash = total_stock + cashbal
        return render_template("portfolio.html", cash=cashbal, stocks=stocks, quotes=quotes, total_cash=total_cash)

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "POST":
        #Form must be entered
        symbol = request.form.get("stock")
        if symbol == None or symbol == "":
            return apology("Must enter stock symbol", 400)
        if request.form.get("qty") == "":
            return apology("Must Enter Qty", 400)
        #qty must be greater than 1
        qty = int(request.form.get("qty"))
        if qty < 1:
            return apology("Quantity must be greater than 0", 400)
        #lookup symbol and check that it exists
        quote = lookup(symbol)
        if quote == None:
            return apology("Symbol does not exist", 400)
        #store name
        name = quote['name']
        #get exteneded cost
        total_cost = qty * float(quote["price"])
        #check cash on hand and make sure there is suffecient funds for transaction
        cash = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=session["user_id"])
        coh = cash[0]['cash']
        if coh < total_cost:
            return apology("Funds not Available", 400)
        else:
            #reduce cashbalance and update cash on hand
            cashbal = coh - total_cost
            db.execute("UPDATE users SET cash = :cashbal WHERE id = :user_id", cashbal=cashbal, user_id=session["user_id"])
            #insert transaction into transactions table
            db.execute("INSERT INTO transactions (id, symbol, name, qty, price, total) VALUES (:user_id, :symbol, :name, :qty, :price, :total)", user_id=session["user_id"], symbol=symbol, name=name, qty=qty, price=quote['price'], total=total_cost)
        #load data to open portfolio
        stocks = db.execute("SELECT symbol, name, SUM(qty) AS totalshares FROM transactions WHERE id = :user_id GROUP BY symbol HAVING totalshares > 0", user_id=session["user_id"])
        quotes = {}
        total_stock = 0
        for i in stocks:
            quotes[i["symbol"]] = lookup(i["symbol"])
            total_stock = total_stock + (float(quotes[i["symbol"]]["price"]) * i["totalshares"])
        total_cash = total_stock + cashbal
        return render_template("portfolio.html", cash=cashbal, stocks=stocks, quotes=quotes, total_cash=total_cash)
    else:
        return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    #return all transactons from userid
    history = db.execute("SELECT * FROM transactions WHERE id = :user_id ORDER BY date DESC", user_id=session["user_id"])
    return render_template("history.html", history=history)

@app.route("/login", methods=["GET", "POST"])
def login():

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
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))
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
     #if user clicks quote link
    if request.method == "GET":
        return render_template("quote.html")
    #if user submits request for quote
    else:
        #get symbol from user and lookup through helpers.py
        symbol = request.form.get("stock")
        quote = lookup(symbol)
        #check if symbol exists
        if quote == None:
            return apology("Invalid Symbol", 400)
        #load quoted with quote information
        return render_template("quoted.html", quote=quote)

@app.route("/register", methods=["GET", "POST"])
def register():
    #if user clicks to register
    if request.method == "GET":
        return render_template("register.html")
    #after user submits data on register page
    else:
        #check if username and pasword are filled in
        if not request.form.get("username"):
            return apology("must provide username", 403)
        elif not request.form.get("password1"):
            return apology("must enter password", 403)
        #confirm that the passwords match
        elif request.form.get("password2") != request.form.get("password1"):
            return apology("passwords do not match", 403)
        username = request.form.get("username")
        password = generate_password_hash(request.form.get("password1"))
        #See if username is already in DB
        rows = db.execute("SELECT username FROM users WHERE username = :username", username=username)
        if len(rows) == 1:
            #if in db return apoloty
            return apology("username taken", 403)
        else:
            #insert new user/password into users table
            db.execute("INSERT INTO users (username, hash) VALUES (:username, :password)", username=username, password=password)
            #get userid and insert cash transaction info into transaction table
            userid = db.execute("SELECT id FROM users WHERE username = :username", username=username)
            db.execute("INSERT INTO transactions (id, symbol, total) VALUES (:userid, :cash, :total)", userid=userid[0]['id'], cash="CASH", total=10000)
            #goto login
            return render_template("login.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method == "POST":
        #confirm form is entered
        symbol = request.form.get("stock")
        if symbol == None or symbol == "":
            return apology("Must enter stock symbol", 400)
        if request.form.get("qty") == "":
            return apology("Must enter quantity", 400)
        #confirm positive int in qty form
        qty = int(request.form.get("qty"))
        if qty < 1:
            return apology("Quantity must be greater than 0", 400)
        #confirm symbol is real
        quote = lookup(symbol)
        if quote == None:
            return apology("Symbol does not Exist", 400)
        #store stock name
        name = quote['name']
        #get extended cost for transaction
        total_cost = qty * float(quote["price"])
        #turn qty negative to show sold
        qty = qty * -1
        #get currecnt cash from user and add the extended sell price to balance
        cash = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=session["user_id"])
        coh = cash[0]['cash']
        cashbal = coh + total_cost
        #update cash balance with new total
        db.execute("UPDATE users SET cash = :cashbal WHERE id = :user_id", cashbal=cashbal, user_id=session["user_id"])
        #insert transaction into transactions table
        db.execute("INSERT INTO transactions (id, symbol, name, qty, price, total) VALUES (:user_id, :symbol, :name, :qty, :price, :total)", user_id=session["user_id"], symbol=symbol, name=name, qty=qty, price=quote['price'], total=total_cost)
        #load data to open portfolio
        stocks = db.execute("SELECT symbol, name, SUM(qty) AS totalshares FROM transactions WHERE id = :user_id GROUP BY symbol HAVING totalshares > 0", user_id=session["user_id"])
        quotes = {}
        total_stock = 0
        for i in stocks:
            quotes[i["symbol"]] = lookup(i["symbol"])
            total_stock = total_stock + (float(quotes[i["symbol"]]["price"]) * i["totalshares"])
        total_cash = total_stock + cashbal
        return render_template("portfolio.html", cash=cashbal, stocks=stocks, quotes=quotes, total_cash=total_cash)
    else:
        return render_template("sell.html")

def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)

# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
