import falcon
from falcon import api_helpers
import msgpack
import six
import json
from six.moves.urllib.parse import urlparse, parse_qs
from deuce.util import set_qs
from deuce.model import Vault
# import deuce.transport.wsgi.errors as wsgi_errors
import deuce.util.log as logging
from deuce.transport.validation import *
from deuce.util.filecat import FileCat
import deuce
logger = logging.getLogger(__name__)


class Resource(object):

    def on_get(self, req, resp):
        # TODO(TheSriram): Must return a home document
        resp.status = falcon.HTTP_200
        resp.body = json.dumps({})