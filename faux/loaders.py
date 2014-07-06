import abc
import os
import logging

logger = logging.getLogger(__name__)

try:
  import simplejson as json
except ImportError:
  import json

try:
  import yaml
except ImportError:
  # If PyYAML isn't installed, we create a dummy yaml object with a load
  # method that simply raises an exception and notifies the user that they
  # must have PyYAML installed if they wish to use YAML as their data
  # serialization format. This basically just allows us to keep all imports at
  # the top of this module without the nasty side effect of alerting the user
  # of missing libraries that they don't plan on using. Instead, we only alert
  # them of a missing library at the point that they try to use it.
  def load(self, filename):
    raise RuntimeException("Could not load fixture '%s'. Make sure you have PyYAML installed." % filename)
  yaml = type('FakeYaml', (object,), {
    'load': load
  })()


class FixtureLoader(object):
  """An ABC for implementing loaders for different data serialization formats.

  All fixture loader classes must inherit from this base class and provide a
  _load method that takes a filename and returns a python object, and an
  extensions attribute that holds an iterable of strings, each representing a
  file extension that the loader handles.

  The main reason for this class is to enforce a contract for subclasses, but
  more importantly, this class is aware of all of its subclasses. This makes
  it possible for this class to provide a simple interface for loading
  fixtures and for determining which file extensions (i.e., data serialization
  formats) are supported.

  """
  __metaclass__ = abc.ABCMeta

  @abc.abstractmethod
  def _load(self, filename):
    pass

  @classmethod
  def supported_extensions(cls):
    """Returns a list of supported file extensions.

    Gathers all of the subclasses and compiles a list of the file extensions
    supported by each.

    """
    return [ext for c in cls.__subclasses__() for ext in c.extensions]

  @classmethod
  def load(cls, filename):
    """Loads the fixtures within the given file.
    """
    if not os.path.isfile(filename):
      raise IOError("No such file: '%s'" % filename)

    name, extension = os.path.splitext(filename)

    for c in cls.__subclasses__():
      # If a loader class has no extenions, log a warning so the developer knows
      # that it will never be used anyhwhere
      if not hasattr(c, 'extensions'):
        logger.warn('%s does not contain an extensions attribute; it will not be used.' % c.__name__)
        continue

      # Otherwise, check if the file's extension matches a loader extension
      for ext in c.extensions:
        if extension == ext:
          return c()._load(filename)

    # None of the loaders matched, so raise an exception
    raise RuntimeException("Could not load fixture '%s'. Unsupported file format." % filename)


class JSONLoader(FixtureLoader):

  extensions = ('.json', '.js')

  def _load(self, filename):
    with open(filename) as fin:
      return json.load(fin)


class YAMLLoader(FixtureLoader):

  extensions = ('.yaml', '.yml')

  def _load(self, filename):
    with open(filename) as fin:
      return yaml.load(fin)
