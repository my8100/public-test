# coding: utf-8
import os

from scrapydweb.vars import APSCHEDULER_DATABASE_URI, DATA_PATH, DATABASE_PATH, ROOT_DIR


def test_option_data_path(app):
    data_path = os.environ.get('DATA_PATH', '')
    if data_path and os.environ.get('TEST_ON_CIRCLECI', 'False').lower() == 'true':
        assert not os.path.exists(os.path.join(ROOT_DIR, 'data'))
    assert os.path.exists(data_path or DATA_PATH)


def test_option_database_url(app):
    database_url = os.environ.get('DATABASE_URL', 'sqlite:///' + DATABASE_PATH)
    assert APSCHEDULER_DATABASE_URI.startswith(database_url)
    assert app.config['SQLALCHEMY_DATABASE_URI'].startswith(database_url)
    for value in app.config['SQLALCHEMY_BINDS'].values():
        assert value.startswith(database_url)
