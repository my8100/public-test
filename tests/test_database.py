# coding: utf-8
import os

from scrapydweb.vars import DATABASE_PATH


def test_sqlalchemy_database_uri(app):
    database_url = os.environ.get('DATABASE_URL', DATABASE_PATH)
    assert app.config['SQLALCHEMY_DATABASE_URI'].startswith(database_url)
