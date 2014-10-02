import falcon
import falcon.status_codes as status


class HTTPInternalServerError(falcon.HTTPInternalServerError):

    """Wraps falcon.HTTPServiceUnavailable"""

    TITLE = u'Service temporarily unavailable'

    def __init__(self, description, **kwargs):
        super(HTTPInternalServerError, self).__init__(
            self.TITLE, description=description, **kwargs)


class HTTPBadGateway(falcon.HTTPBadGateway):

    """Wraps falcon.HTTPServiceUnavailable"""

    TITLE = u'Bad Gateway'

    def __init__(self, description):
        super(HTTPBadGateway, self).__init__(
            self.TITLE, description=description)


class HTTPBadRequestAPI(falcon.HTTPBadRequest):

    """Wraps falcon.HTTPBadRequest with a contextual title."""

    TITLE = u'Invalid API request'

    def __init__(self, description):
        super(HTTPBadRequestAPI, self).__init__(self.TITLE, description)


class HTTPBadRequestBody(falcon.HTTPBadRequest):

    """Wraps falcon.HTTPBadRequest with a contextual title."""

    TITLE = u'Invalid request body'

    def __init__(self, description):
        super(HTTPBadRequestBody, self).__init__(self.TITLE, description)


class HTTPPreconditionFailed(falcon.HTTPPreconditionFailed):

    """Wraps HTTPPreconditionFailed with a contextual title."""

    TITLE = u'Precondition Failure'

    def __init__(self, description):
        super(HTTPPreconditionFailed, self).__init__(self.TITLE, description)


class HTTPNotFound(falcon.HTTPNotFound):

    """Wraps falcon.HTTPNotFound"""

    def __init__(self):
        super(HTTPNotFound, self).__init__()


class HTTPNotImplemented(falcon.HTTPError):

    """Derives NotImplemented from falcon.HTTPError"""

    TITLE = u'Not Implemented'

    def __init__(self, description):
        super(HTTPNotImplemented, self).__init__(status.HTTP_501,
                                                 self.TITLE,
                                                 description,
                                                 code=501)


class HTTPMethodNotAllowed(falcon.HTTPMethodNotAllowed):

    """Wraps falcon.HTTPMethodNotAllowed"""

    TITLE = u'Method Not Allowed'

    def __init__(self, allowed_method, description):
        super(HTTPMethodNotAllowed, self).__init__(allowed_method,
                                                   description=description)
