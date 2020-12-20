import os
import requests
import urllib.parse

from flask import redirect, render_template, request, session
from functools import wraps
from cs50 import SQL


def apology(message, code=400):
    """Render message as an apology to user."""
    def escape(s):
        """
        Escape special characters.

        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [("-", "--"), (" ", "-"), ("_", "__"), ("?", "~q"),
                         ("%", "~p"), ("#", "~h"), ("/", "~s"), ("\"", "''")]:
            s = s.replace(old, new)
        return s
    return render_template("apology.html", top=code, bottom=escape(message)), code


def login_required(f):
    """
    Decorate routes to require login.

    http://flask.pocoo.org/docs/1.0/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


def lookup(symbol):
    """Look up quote for symbol."""

    # Contact API
    try:
        api_key = os.environ.get("API_KEY")
        response = requests.get(f"https://cloud-sse.iexapis.com/stable/stock/{urllib.parse.quote_plus(symbol)}/quote?token={api_key}")
        response.raise_for_status()
    except requests.RequestException:
        return {}

    # Parse response
    try:
        quote = response.json()
        return {
            "name": quote["companyName"],
            "price": float(quote["latestPrice"]),
            "symbol": quote["symbol"]
        }
    except (KeyError, TypeError, ValueError):
        return {}


db = SQL("sqlite:///finance.db")


def get_user_cash():
    update_user_cash()
    user_cash = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id = session['user_id'])
    user_cash = round(user_cash[0]['cash'], 4)
    return user_cash

def update_user_cash():
    transactions = db.execute("SELECT shares, price, type FROM purchases WHERE user_id = :user_id", user_id=session["user_id"])
    updated_cash = 0
    print(transactions)
    for row in transactions:
        if row['type'] == 'buy':
            updated_cash -= int(row['shares'])*row['price']
        elif row['type'] == 'sell' or row['type'] == 'd':
            updated_cash += int(row['shares'])*row['price']
    print(updated_cash)
    db.execute("UPDATE users SET cash = :updated_cash", updated_cash=updated_cash)
    return

def usd(value):
    """Format value as USD."""
    return f"${value:,.2f}"
