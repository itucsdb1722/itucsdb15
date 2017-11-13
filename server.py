import datetime
import json
import os
import psycopg2 as dbapi2
import re
import random

from random import randint
from flask import Flask
from flask import redirect
from flask import render_template
from flask import request
from flask import session
from flask import flash
from functools import wraps
from flask.helpers import url_for


app = Flask(__name__)

app.secret_key = "secret"


def login_check(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'logged_in' in session:
            return f(*args, **kwargs)
        else:
            flash("You need to login first.")
            return redirect(url_for('login'))
    return wrap


def get_elephantsql_dsn(vcap_services):
    """Returns the data source name for ElephantSQL."""
    parsed = json.loads(vcap_services)
    uri = parsed["elephantsql"][0]["credentials"]["uri"]
    match = re.match('postgres://(.*?):(.*?)@(.*?)(:(\d+))?/(.*)', uri)
    user, password, host, _, port, dbname = match.groups()
    dsn = """user='{}' password='{}' host='{}' port={}
             dbname='{}'""".format(user, password, host, port, dbname)
    return dsn


@app.route('/intro')
def intro():
    return "Welcome to IBDB"


@app.route('/')
def home_page():

    with dbapi2.connect(app.config['dsn']) as connection:
            cursor = connection.cursor()
            query = "SELECT max(id) from books"
            cursor.execute(query)
            maxid = cursor.fetchone()
            max = maxid[0]
            names = [] * 0
            writers = [] * 0
            isbns = [] * 0
            for i in range(0, 4):
                rand = randint(1, max)
                statement = "Select name, writer, isbn from books where id=" + str(rand)+";"
                cursor.execute(statement)
                for name, writer, isbn in cursor:
                    names.append(name)
                    writers.append(writer)
                    isbns.append(isbn)

    booklink1 = "http://covers.openlibrary.org/b/isbn/" + isbns[0] + "-M.jpg"
    booklink2 = "http://covers.openlibrary.org/b/isbn/" + isbns[1] + "-M.jpg"
    booklink3 = "http://covers.openlibrary.org/b/isbn/" + isbns[2] + "-M.jpg"


    now = datetime.datetime.now()
    return render_template('home.html', current_time=now.ctime(), maxid=max, name=names, writer=writers, isbn=isbns, booklink1=booklink1, booklink2=booklink2, booklink3=booklink3)


@app.route('/initdb')
def initialize_database():
    with dbapi2.connect(app.config['dsn']) as connection:
        cursor = connection.cursor()
        query = """DROP TABLE IF EXISTS USERS"""
        cursor.execute(query)
        statement = """CREATE TABLE USERS (USERNAME VARCHAR(10) PRIMARY KEY, PASSWORD VARCHAR(10) )"""
        cursor.execute(statement)
        query = """DROP TABLE IF EXISTS BOOKS"""
        cursor.execute(query)
        statement = """CREATE TABLE BOOKS (ID SERIAL PRIMARY KEY, NAME VARCHAR(20), WRITER VARCHAR(20),
        CATEGORY VARCHAR(10), ISBN VARCHAR(10), YEAR INTEGER, SCORE INTEGER, VOTES INTEGER )"""
        cursor.execute(statement)
        statement = """INSERT INTO BOOKS(NAME,WRITER,CATEGORY,ISBN,YEAR, SCORE, VOTES )
        VALUES('1984', 'GEORGE ORWELL','distopia','0451524934','1984',0,0 )"""
        cursor.execute(statement)
        connection.commit()
    return redirect(url_for('home_page'))


@app.route('/admin', methods=['GET', 'POST'])
def admin():
    with dbapi2.connect(app.config['dsn']) as connection:
        cursor = connection.cursor()
        error = None
        if request.method == 'POST':
            name = request.form['name']
            writer = request.form['writer']
            category = request.form['category']
            isbn = request.form['isbn']
            year = request.form['year']
            if 'submit' in request.form:
                statement = "INSERT INTO BOOKS(NAME,WRITER,CATEGORY,ISBN, YEAR, SCORE, VOTES ) VALUES(' " + name + "','"+writer+"','"+category+"','"+isbn+"','"+year+"',0,0 )"
                cursor.execute(statement)
                connection.commit()
                return redirect(url_for('admin'))

    return render_template('admin.html', error=error)


@app.route('/login', methods=['GET', 'POST'])
def login():
    with dbapi2.connect(app.config['dsn']) as connection:
        cursor = connection.cursor()
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if 'login' in request.form:
            statement = "SELECT * from Users where Username='" + username + "' and Password='" + password + "'"
            cursor.execute(statement)
            user = cursor.fetchone()
            if user:
                session['logged_in'] = True
                flash('You are logged in')
                return redirect(url_for('home_page'))
            else:
                error = 'Invalid username or password, try again.'
    return render_template('login.html', error=error)


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    with dbapi2.connect(app.config['dsn']) as connection:
        cursor = connection.cursor()
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        statement = "SELECT * from Users where Username='" + username + "'"
        cursor.execute(statement)
        test = cursor.fetchone()
        if test:
            error = 'Username already in use, try again'
        else:
            query = "insert into users values (%s,%s)"
            cursor.execute(query, (username, password))
            connection.commit()
            return redirect(url_for('login'))

    return render_template('signup.html', error=error)


@app.route('/logout')
@login_check
def logout():
    session.pop('logged_in', None)
    flash('You are logged out')
    return redirect(url_for('intro'))


@app.route('/count')
def counter_page():
    with dbapi2.connect(app.config['dsn']) as connection:
        cursor = connection.cursor()

        query = "UPDATE COUNTER SET N = N + 1"
        cursor.execute(query)
        connection.commit()

        query = "SELECT N FROM COUNTER"
        cursor.execute(query)
        count = cursor.fetchone()[0]
    return render_template("count.html", counter=count)


if __name__ == '__main__':
    VCAP_APP_PORT = os.getenv('VCAP_APP_PORT')
    if VCAP_APP_PORT is not None:
        port, debug = int(VCAP_APP_PORT), False
    else:
        port, debug = 5000, True

    VCAP_SERVICES = os.getenv('VCAP_SERVICES')
    if VCAP_SERVICES is not None:
        app.config['dsn'] = get_elephantsql_dsn(VCAP_SERVICES)
    else:
        app.config['dsn'] = """user='vagrant' password='vagrant'
                               host='localhost' port=5432 dbname='postgres'"""

    app.run(host='0.0.0.0', port=port, debug=debug)
