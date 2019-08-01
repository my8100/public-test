# coding: utf-8
import glob
import os
import re
import sys


DB_APSCHEDULER = 'scrapydweb_apscheduler'
DB_TIMERTASKS = 'scrapydweb_timertasks'
DB_METADATA = 'scrapydweb_metadata'
DB_JOBS = 'scrapydweb_jobs'
DBS = [DB_APSCHEDULER, DB_TIMERTASKS, DB_METADATA, DB_JOBS]

SCRAPYDWEB_TESTMODE = os.environ.get('SCRAPYDWEB_TESTMODE', 'False').lower() == 'true'


def setup_database(DATABASE_PATH):
    DATABASE_PATH = re.sub(r'\\', '/', DATABASE_PATH)
    DATABASE_PATH = re.sub(r'/$', '', DATABASE_PATH)

    mysql_uri = os.environ.get('MYSQL_URI', '')
    postgresql_uri = os.environ.get('POSTGRESQL_URI', '')
    sqlite_uri = os.environ.get('SQLITE_URI', '')

    enable_mysql = os.environ.get('ENABLE_MYSQL', 'True').lower() == 'true'
    enable_postgresql = os.environ.get('ENABLE_POSTGRESQL', 'True').lower() == 'true'
    enable_sqlite = os.environ.get('ENABLE_SQLITE', 'True').lower() == 'true'

    uri = ''
    m_mysql = re.match(r'mysql://(.+?):(.+?)@(.+?):(\d+)', mysql_uri)
    m_postgres = re.match(r'postgres://(.+?):(.+?)@(.+?):(\d+)', postgresql_uri)
    m_sqlite = re.match(r'sqlite:///(.+)$', sqlite_uri)
    if enable_mysql and m_mysql:
        print('Found environment variable MYSQL_URI: %s' % mysql_uri)
        uri = mysql_uri
        setup_mysql(*m_mysql.groups())
    elif enable_postgresql and m_postgres:
        print('Found environment variable POSTGRESQL_URI: %s' % postgresql_uri)
        uri = postgresql_uri
        setup_postgresql(*m_postgres.groups())
    elif enable_sqlite and m_sqlite:
        print('Found environment variable SQLITE_URI: %s' % sqlite_uri)
        folder_path = re.sub(r'\\', '/', os.path.abspath(m_sqlite.group(1)))
        if not os.path.exists(folder_path):
            os.mkdir(folder_path)
        uri = 'sqlite:///%s' % folder_path
        DATABASE_PATH = folder_path
        if SCRAPYDWEB_TESTMODE:
            for file in glob.glob(os.path.join(DATABASE_PATH, '*.db')):
                os.remove(file)
                print("Removed %s" % file)
    if uri:
        uri = re.sub(r'\\', '/', uri)
        uri = re.sub(r'/$', '', uri)
        is_sqlite = uri.startswith('sqlite:///')
        APSCHEDULER_DATABASE_URI = '/'.join([uri, DB_APSCHEDULER+'.db' if is_sqlite else DB_APSCHEDULER])
        SQLALCHEMY_DATABASE_URI = '/'.join([uri, DB_TIMERTASKS+'.db' if is_sqlite else DB_TIMERTASKS])
        SQLALCHEMY_BINDS = {
            'metadata': '/'.join([uri, DB_METADATA+'.db' if is_sqlite else DB_METADATA]),
            'jobs': '/'.join([uri, DB_JOBS+'.db' if is_sqlite else DB_JOBS])
        }
    else:
        APSCHEDULER_DATABASE_URI = 'sqlite:///' + '/'.join([DATABASE_PATH, 'apscheduler.db'])
        # http://flask-sqlalchemy.pocoo.org/2.3/binds/#binds
        SQLALCHEMY_DATABASE_URI = 'sqlite:///' + '/'.join([DATABASE_PATH, 'timer_tasks.db'])
        SQLALCHEMY_BINDS = {
            'metadata': 'sqlite:///' + '/'.join([DATABASE_PATH, 'metadata.db']),
            'jobs': 'sqlite:///' + '/'.join([DATABASE_PATH, 'jobs.db'])
        }

    if SCRAPYDWEB_TESTMODE:
        print("DATABASE_PATH: %s" % DATABASE_PATH)
        print("APSCHEDULER_DATABASE_URI: %s" % APSCHEDULER_DATABASE_URI)
        print("SQLALCHEMY_DATABASE_URI: %s" % SQLALCHEMY_DATABASE_URI)
        print("SQLALCHEMY_BINDS: %s" % SQLALCHEMY_BINDS)
    return DATABASE_PATH, APSCHEDULER_DATABASE_URI, SQLALCHEMY_DATABASE_URI, SQLALCHEMY_BINDS


def drop_database(cur, dbname):
    sql = "DROP DATABASE %s" % dbname
    print(sql)
    try:
        cur.execute(sql)
    except Exception as err:
        print(err)


def setup_mysql(username, password, host, port):
    """
    ModuleNotFoundError: No module named 'MySQLdb'
    pip install mysqlclient
    Python 2: pip install mysqlclient -> MySQLdb/_mysql.c(29) : fatal error C1083: Cannot open include file: 'mysql.h': No such file or directory
    https://stackoverflow.com/questions/51294268/pip-install-mysqlclient-returns-fatal-error-c1083-cannot-open-file-mysql-h
    https://www.lfd.uci.edu/~gohlke/pythonlibs/#mysqlclient
    pip install "path to the downloaded mysqlclient.whl file"
    """
    require_version = '0.9.3'  # Dec 18, 2018
    install_command = "pip install --upgrade pymysql>=%s" % require_version
    try:
        import pymysql  # 0.9.3 Dec 18, 2018
        assert pymysql.__version__ >= require_version, install_command
    except (ImportError, AssertionError):
        sys.exit("Run command: %s" % install_command)
    else:
        # Run scrapydweb: ModuleNotFoundError: No module named 'MySQLdb'
        pymysql.install_as_MySQLdb()
    print(username, password, host, port)
    conn = pymysql.connect(host=host, port=int(port), user=username, password=password,
                           charset='utf8', cursorclass=pymysql.cursors.DictCursor)
    cur = conn.cursor()
    print(cur)
    for dbname in DBS:
        if SCRAPYDWEB_TESTMODE:
            drop_database(cur, dbname)
        # pymysql.err.ProgrammingError: (1007, "Can't create database 'scrapydweb_apscheduler'; database exists")
        # cur.execute("CREATE DATABASE IF NOT EXISTS %s CHARACTER SET 'utf8' COLLATE 'utf8_general_ci'" % dbname)
        try:
            cur.execute("CREATE DATABASE %s CHARACTER SET 'utf8' COLLATE 'utf8_general_ci'" % dbname)
        except Exception as err:
            if 'exists' in str(err):
                pass
            else:
                raise
    cur.close()
    conn.close()


def setup_postgresql(username, password, host, port):
    """
    https://github.com/my8100/notes/blob/master/back_end/the-flask-mega-tutorial.md
    When working with database servers such as MySQL and PostgreSQL,
    you have to create the database in the database server before running upgrade.
    """
    require_version = '2.7.7'  # Jan 23, 2019
    install_command = "pip install --upgrade psycopg2>=%s" % require_version
    try:
        import psycopg2
        assert psycopg2.__version__ >= require_version, install_command
    except (ImportError, AssertionError):
        sys.exit("Run command: %s" % install_command)
    print(username, password, host, port)
    conn = psycopg2.connect(host=host, port=int(port), user=username, password=password)
    # conn = psycopg2.connect(host=host, port=int(port), user=username, password=None)
    # conn = psycopg2.connect(host=host, port=int(port), user=username, password=password, dbname='scrapydweb_apscheduler')
    conn.set_isolation_level(0)  # https://wiki.postgresql.org/wiki/Psycopg2_Tutorial
    cur = conn.cursor()
    print(cur)
    for dbname in DBS:
        if SCRAPYDWEB_TESTMODE:
            # database "scrapydweb_apscheduler" is being accessed by other users
            # DETAIL:  There is 1 other session using the database.
            # To restart postgres server on Windonws -> win+R: services.msc
            drop_database(cur, dbname)

        # https://www.postgresql.org/docs/9.0/sql-createdatabase.html
        # https://stackoverflow.com/questions/9961795/
        # utf8-postgresql-create-database-like-mysql-including-character-set-encoding-a

        # psycopg2.ProgrammingError: invalid locale name: "en_US.UTF-8"
        # https://stackoverflow.com/questions/40673339/
        # creating-utf-8-database-in-postgresql-on-windows10

        # cur.execute("CREATE DATABASE %s ENCODING 'UTF8' LC_COLLATE 'en-US' LC_CTYPE 'en-US'" % dbname)
        # psycopg2.DataError: new collation (en-US) is incompatible with the collation of the template database (Chinese (Simplified)_People's Republic of China.936)
        # HINT:  Use the same collation as in the template database, or use template0 as template.
        try:
            cur.execute("CREATE DATABASE %s ENCODING 'UTF8' LC_COLLATE 'en_US.UTF-8' LC_CTYPE 'en_US.UTF-8'" % dbname)
        except:
            try:
                cur.execute("CREATE DATABASE %s" % dbname)
            except Exception as err:
                # psycopg2.ProgrammingError: database "scrapydweb_apscheduler" already exists
                if 'exists' in str(err):
                    pass
                else:
                    raise
    cur.close()
    conn.close()
