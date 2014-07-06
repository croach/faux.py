from __future__ import print_function

import abc
import functools
import glob
import importlib
import inspect
import logging
import os
import sys

import sqlalchemy as sa

from .loaders import FixtureLoader

try:
    import simplejson as json
except ImportError:
    import json

__version__ = '0.1.0'

formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logger = logging.getLogger()
logger.addHandler(handler)


DEFAULT_CLASS_SETUP_NAME = 'setUpClass'
DEFAULT_CLASS_TEARDOWN_NAME = 'tearDownClass'
CLASS_SETUP_NAMES = ('setup_class', 'setup_all', 'setupClass', 'setupAll',
    'setUpClass', 'setUpAll')
CLASS_TEARDOWN_NAMES = ('teardown_class', 'teardown_all', 'teardownClass',
    'teardownAll', 'tearDownClass', 'tearDownAll')
TEST_SETUP_NAMES = ('setUp',)
TEST_TEARDOWN_NAMES = ('tearDown',)


class Fixtures(object):
    def __init__(self, metadata, fixtures_dirs=None):
        self._metadata = metadata
        self._engine = sa.create_engine('sqlite:///:memory:')
        self._session_class = sa.orm.sessionmaker(bind=self._engine)
        if fixtures_dirs is not None:
            self.fixtures_dirs = [os.path.abspath(d) for d in fixtures_dirs]
        else:
            fixtures_dirs = []

        # # TODO: What if the user has a python module that ties together a bunch of
        # # tests from modules that are in lower level packages? Will the following
        # # still work, or do we need to do something a bit different?
        # default_fixtures_dir = os.path.dirname(os.path.realpath(__file__))
        # self.fixtures_dirs = [default_fixtures_dir]
        # if fixtures_dirs is not None:
        #     self.fixtures_dirs += fixtures_dirs


    def setup(self, fixtures):
        logger.info("setting up fixtures...")
        # Setup the database
        self._metadata.create_all(self._engine)
        # # TODO why do we call this?
        # self.db.session.rollback()

        # Load all of the fixtures
        for filepath in fixtures:
            self.load_fixtures(FixtureLoader.load(filepath))

    def teardown(self):
        logger.info("tearing down fixtures...")
        # self.db.session.expunge_all()
        self._metadata.drop_all(self._engine)

    def load_fixtures(self, fixtures):
        """Loads the given fixtures into the database.
        """
        conn = self._engine.connect()
        metadata = self._metadata

        for fixture in fixtures:
            if 'model' in fixture:
                module_name, class_name = fixture['model'].rsplit('.', 1)
                module = importlib.import_module(module_name)
                model = getattr(module, class_name)
                session = self._session_class()
                for fields in fixture['records']:
                    obj = model(**fields)
                    session.add(obj)
                session.commit()
            elif 'table' in fixture:
                table = sa.Table(fixture['table'], metadata)
                conn.execute(table.insert(), fixture['records'])
            else:
                raise ValueError("Fixture missing a 'model' or 'table' field: %s" % json.dumps(fixture))

    def find_fixtures(self, obj, fixtures):
        """Returns the absolute filepaths of all fixtures for the given object.

        This function returns a list of files that contain fixtures. It does
        so by first finding any files that match the given set of names within
        the given set of fixtures directories (setup at instance creation). If
        no fixtures files were passed in, it tries to find files within the
        same directory as the test file that match the test file's name but
        has an extension that matches one of the supported file extensions.

        """
        _fixtures = []

        # Get the full (absolute) path of the test file and its directory
        test_file_path = os.path.abspath(sys.modules[obj.__module__].__file__)
        test_file_dir = os.path.dirname(test_file_path)

        # Create set of fixtures directories to search starting with the
        # directory of the current test file
        fixtures_dirs = [test_file_dir] + self.fixtures_dirs

        # If a list of fixtures were passed in, find those instead of looking
        # for the default fixture file (i.e., the file matching the test file)
        if fixtures is not None and len(fixtures) > 0:
            for filename in fixtures:
                # If the given file name is an absolute path, add it to the
                # list as is---absolute paths are always supported.
                if os.path.isabs(filename):
                    _fixtures.append(filename)
                    continue

                # Otherwise, we need to find the full path of the given file
                for fixtures_dir in fixtures_dirs:
                    candidate_filepath = os.path.join(fixtures_dir, filename)
                    # If the fixtures file exists, and it is in one of the
                    # supported formats, include it in the returned list
                    if os.path.isfile(candidate_filepath) and \
                        os.path.splitext(candidate_filepath)[1] in FixtureLoader.supported_extensions():
                        _fixtures.append(candidate_filepath)
        else:
            # Search in the same directory as the test file for a file with the
            # same name but with a supported format's file extension.
            filepath, ext = os.path.splitext(test_file_path)
            for candidate_filepath in glob.glob("%s.*" % filepath):
                if os.path.splitext(candidate_filepath)[1] in FixtureLoader.supported_extensions():
                    _fixtures.append(candidate_filepath)

        # if fixtures are still empty, raise an exception
        if len(_fixtures) == 0:
            raise Exception("Could not find fixtures for '%s'" % test_file_path)

        return _fixtures

    def wrap_method(self, method, fixtures):
        """Wraps a method in a set of fixtures setup/teardown functions.
        """
        # Find all fixtures for the given method
        fixtures = self.find_fixtures(method, fixtures)

        def wrapper(_self, *args, **kwargs):
            self.setup(fixtures)
            _self.__class__.session = self._session_class()
            try:
                method(_self, *args, **kwargs)
            finally:
                self.teardown()
        functools.update_wrapper(wrapper, method)
        return wrapper

    def wrap_class(self, cls, fixtures):
        """Adds fixtures setup/teardown methods at the class level.

        This decorator piggybacks on the setUpClass, tearDownClass methods that
        the unittest/unittest2/nose packages call upon class creation and after
        all tests in the class have finished running.

        """
        def wrap_method(cls, fixtures_fn, names, default_name):
            methods = filter(None, [getattr(cls, name, None) for name in names])
            if len(methods) > 1:
                raise RuntimeError("Cannot have more than one setup/teardown method, found %s" %
                    ', '.join(fn.__name__ for fn in methods))
            elif len(methods) == 1:
                wrapped_method = methods[0]
                def wrapper(cls, *args, **kwargs):
                    fixtures_fn()
                    cls.session = self._session_class()
                    wrapped_method(*args, **kwargs)
                functools.update_wrapper(wrapper, wrapped_method)
                setattr(cls, wrapper.__name__, classmethod(wrapper))
            else:
                def wrapper(cls, *args, **kwargs):
                    fixtures_fn()
                setattr(cls, default_name, classmethod(wrapper))

        # Find all fixtures for the given class
        fixtures = self.find_fixtures(cls, fixtures)

        wrap_method(cls, lambda: self.setup(fixtures), CLASS_SETUP_NAMES, DEFAULT_CLASS_SETUP_NAME)
        wrap_method(cls, lambda: self.teardown(), CLASS_TEARDOWN_NAMES, DEFAULT_CLASS_TEARDOWN_NAME)

        return cls

    def __call__(self, *fixtures):
        # The object being decorated/wrapped
        wrapped_obj = None

        # If the decorator was called without parentheses, the fixtures
        # parameter will be a list containing the object being decorated
        # rather than a list of fixtures to install. In that case, we set the
        # fixtures variable to None and the wrapped_obj variable to the object
        # being decorated so we can call the decorator on it later.
        if len(fixtures) == 1 and not isinstance(fixtures[0], basestring):
            wrapped_obj, fixtures = fixtures[0], fixtures[1:]

        # Create the decorator function
        def decorator(obj):
            if inspect.isfunction(obj):
                return self.wrap_method(obj, fixtures)
            elif inspect.isclass(obj):
                return self.wrap_class(obj, fixtures)
            else:
                raise TypeError("received an object of type '%s' expected 'function' or 'classobj'" % type(obj))

        # If we were passed the object to decorate, go ahead and call the
        # decorator on it and pass back the result, otherwise, return the
        # decorator
        if wrapped_obj is not None:
            return decorator(wrapped_obj)
        else:
            return decorator
