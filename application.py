import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd, get_user_cash, update_user_cash

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
# API KEY: pk_b4018f3fffe6495fa6e18de64641f4f0
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    user_id = session['user_id']

    """SELECT symbol, name, SUM(shares) AS 'shares' FROM (SELECT
companies.symbol AS 'symbol',
companies.name AS 'name',
CASE
 WHEN purchases.type LIKE 'sell' THEN purchases.shares*-1
 ELSE purchases.shares
END AS 'shares',
purchases.type AS 'type'

FROM purchases JOIN companies ON purchases.symbol = companies.symbol WHERE user_id = 8)
GROUP BY symbol"""


    stocks_portf = db.execute("SELECT `c`.`symbol` AS `symbol`, `c`.`name` AS `name`, SUM( ( CASE WHEN `p`.`type` = 'sell' THEN  `p`.`shares`*-1 ELSE  `p`.`shares` END ) ) AS `total_shares`, `p`.`type` AS `type` FROM `purchases` AS `p` JOIN `companies` AS `c` ON `p`.`symbol` = `c`.`symbol`  WHERE `p`.`user_id` = :user_id GROUP BY `c`.`symbol` HAVING `total_shares` <> 0",
                        user_id=user_id)
    # add current value
    for row in stocks_portf:
        row['total_value'] = round(row['total_shares'] * lookup(row['symbol'])['price'], 4)

    # get user cash
    update_user_cash()
    user_cash = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id = user_id)
    user_cash = round(user_cash[0]['cash'], 4)

    # get total portfolio value
    total = user_cash
    for row in stocks_portf:
        total += row['total_value']

    # set default value if portfolio is empty
    return render_template("index.html", stocks_portf=stocks_portf, cash = user_cash,
                            total = round(total, 4), current_cash = get_user_cash())


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "POST":
        symbol = request.form['symbol']
        shares = request.form['shares']

     #   try:
        price = lookup(symbol)['price']
      #  except TypeError:
          #  flash("Symbol does not exist. ")
         #   return redirect("/buy")

        name = lookup(symbol)['name']

        if shares == '':
            flash("Must select number of shares. ")
            return redirect("/buy")
        elif price == '':
            flash("Symbol does not exist. ")
            return redirect("/buy")

        total_price = float(shares) * price
        user_cash = db.execute("SELECT cash FROM users WHERE id = :user_id",
                                user_id = session["user_id"])
        user_cash = float(user_cash[0]['cash'])

        if user_cash >= total_price:
            db.execute("INSERT INTO purchases (user_id, symbol, price, shares, type) VALUES (:user_id, :symbol, :price, :shares, 'buy')",
                        user_id = session["user_id"], symbol = symbol, price = price, shares = shares)

            update_user_cash()

            # Update companies table
            rows = db.execute("SELECT symbol FROM companies WHERE symbol = :symbol", symbol=symbol)
            if len(rows) < 1:
                db.execute("INSERT INTO companies(symbol, name) VALUES (:symbol, :name)", symbol=symbol, name=name)

            flash('Purchase succesfull!', 'success')
            return redirect("/")
        else:
            flash("You don't have enough cash.", 'error')
            return redirect('/buy')

    return render_template("buy.html", current_cash = get_user_cash())


@app.route("/check", methods=["GET"])
def check():
    """Return true if username available, else false, in JSON format"""
    user_db = db.execute("SELECT username FROM users WHERE username = :username",
                          username=request.args.get("username"))
    if len(user_db) != 0:
        return jsonify(user_exists='true')

    return jsonify(user_exists='false')

@app.route("/history")
@login_required
def history():

    # Get transactions from db
    transactions = db.execute("SELECT type, symbol, price, shares, create_time FROM purchases WHERE user_id=:user_id",
                user_id=session['user_id'])

    for row in transactions:
        row['amount'] = round(abs(float(row['shares']*row['price'])), 3)

    return render_template('history.html', transactions=transactions, current_cash = get_user_cash())

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
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        flash("Login succesfull!")
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
    """Quote stock price"""
    if request.method =="GET":
        return render_template("quote.html", current_cash = get_user_cash())

    elif request.method =="POST":
        stock_quote = lookup(request.form['symbol'])
        return render_template("quoted.html", stock_quote=stock_quote, current_cash = get_user_cash())


@app.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    if request.method =="POST":
        deposit = request.form['deposit']
        if float(deposit) > 10000:
            flash('Amount exceeds the limit.', 'error')
            return redirect('/deposit')
        else:
            db.execute("INSERT INTO purchases('user_id', 'symbol', 'price', 'shares', 'type') VALUES (:user_id, 'deposit', :deposit, '1', 'd')",
                        user_id=session['user_id'], deposit=deposit)
        flash('Deposit succesfull.', 'success')
        return redirect('/deposit')

    elif request.method=="GET":
        return render_template('deposit.html', current_cash = get_user_cash())


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        username = request.form['username']
        password = request.form['password']
        confirmation = request.form['confirmation']

        # Check for validity
        if username == '' or password == '' or confirmation == '':
            return apology("all fields are required", 403)
        elif confirmation != password:
            return apology("Passwords don't match", 403)

        # Access database
        """user_db = db.execute("SELECT username FROM users WHERE username = :username",
                          username=request.form.get("username"))
        if len(user_db) != 0:
            return apology(" User with this username already exists", 403)"""

        # Generate password hash
        pass_hash = generate_password_hash(password)

        # Insert user into db
        db.execute("INSERT INTO 'users' ('username','hash') VALUES (:username, :pass_hash)", username=username, pass_hash=pass_hash)

        flash("Account created!", 'success')

        return render_template("login.html")

    return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    # Get user's stocks
    stocks = db.execute("SELECT `c`.`symbol` AS `symbol`, `c`.`name` AS `name`, SUM( ( CASE WHEN `p`.`type` = 'sell' THEN  `p`.`shares`*-1 ELSE  `p`.`shares` END ) ) AS `total_shares`, `p`.`type` AS `type` FROM `purchases` AS `p` JOIN `companies` AS `c` ON `p`.`symbol` = `c`.`symbol`  WHERE `p`.`user_id` = :user_id GROUP BY `c`.`symbol` HAVING `total_shares` <> 0",
                        user_id=session['user_id'])


    if request.method == "POST":
        symbol = request.form['symbol'].split(' ')[0]
        shares = int(request.form['shares'])
        if shares <= 0:
            flash('Enter positive value. ', 'error')
            return render_template("sell.html")
        print(request.form['symbol'])
        price = lookup(symbol)['price']


        #check if user has that many stocks
        for i in stocks:
            if i['symbol'] == symbol:
                if i['total_shares'] < shares:
                    flash('You dont have that many stocks.', 'error')
                    return render_template("sell.html", stocks=stocks, current_cash = get_user_cash())

        # Insert sell transaction into db
        db.execute("INSERT INTO purchases (user_id, symbol, price, shares, type) VALUES (:username, :symbol, :price, :shares, 'sell')",
                    username=session['user_id'], symbol=symbol, price=price, shares=shares*1)

        # update user cash
        update_user_cash()
        #db.execute("UPDATE users SET cash = (SELECT cash FROM users WHERE id = :user_id) + :sell_sum WHERE id = :user_id",
        #           user_id=session['user_id'], sell_sum = shares*price)

        flash('Stock has been sold!', 'success')
        return redirect("/")

    return render_template("sell.html", stocks=stocks, current_cash = get_user_cash())


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)


if __name__ == '__main__':
    app.debug = True
    port = int(os.environ.get('PORT', 5000))
    app.run(host='127.0.0.1', port=port)