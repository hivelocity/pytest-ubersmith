import urlparse

import pytest
import requests_mock

import ubersmith
import ubersmith.api
from ubersmith.utils import to_nested_php_args


_unset_value = object()


class MockResponseError(Exception):
    def __init__(self, error_message='Error!', error_code=-1, status=False,
                 data=''):
        self.error_message = error_message
        self.error_code = error_code
        self.status = status
        self.data = data

    def to_response(self):
        return {
            'error_message': self.error_message,
            'error_code': self.error_code,
            'status': self.status,
            'data': self.data,
        }


class CallRecord(object):
    def __init__(self, mock, method, params, request, context, resp_obj):
        self.mock = mock
        self.method = method
        self.params = params
        self.request = request
        self.context = context

        if isinstance(resp_obj, MockResponseError):
            self.raw_response = resp_obj.to_response()
            self.response = resp_obj
        else:
            self.response = resp_obj['data']
            self.raw_response = resp_obj

    ################################################
    # Public interface and important magic methods #
    ################################################

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    def __contains__(self, item):
        return item in self.params

    def was_successful(self):
        # This may be a MockResponseError, but that, too, has a status attr
        return self.response.status

    def assert_called_with(self, **params):
        """Must have been called with *at least* params. Extra values okay."""
        missing = []
        incorrect = []
        for key, value in self._sanitize_params(params).items():
            if key not in self.params:
                missing.append(key)
            elif self.params[key] != value:
                incorrect.append((key, value, self.params[key]))

        if missing or incorrect:
            parts = []
            if missing:
                parts.append('missing parameters %s' % ', '.join(
                    repr(p) for p in missing))
            for key, expected, found in incorrect:
                parts.append('expected value %r for key %r, found %r' % (
                    expected, key, found))
            raise AssertionError('; '.join(parts).capitalize())
        else:
            return True  # Allow assert call.assert_called_with

    def assert_called_with_exactly(self, **params):
        """Must have exactly params, no more, no less."""
        assert self._sanitize_params(params) == self.params
        return True  # assert call.assert_called_with_exactly

    ###############################
    # Private methods and helpers #
    ###############################

    def _sanitize_params(self, params):
        return {k: str(v) for k, v in to_nested_php_args(params).items()}


@pytest.yield_fixture
def reqmock():
    """Allows patching of HTTP requests"""

    with requests_mock.Mocker() as mock:
        mock.ANY = requests_mock.ANY
        yield mock


@pytest.fixture
def ubermock(reqmock, monkeypatch):
    """Offers easy mocking of ubersmith responses at the HTTP and data level"""
    # All UberMocks by their key, including modules (like 'client' or 'uber')
    mocks = {}
    # Only valid calls (like 'client.add' and 'uber.user_exists')
    calls = {}

    def ubermock_call(request, context):
        # qs is MultiDict
        method = request.qs['method'][0]
        if method not in calls:
            root_mock = mocks[None]
            if root_mock.ignore_missing:
                return {}
            else:
                raise Exception(
                    'Unpatched Ubersmith API method %s called! Please patch '
                    'it to remove this exception.' % method)

        # Most methods will want to return JSON
        context.headers['Content-Type'] = 'application/json'

        mock = calls[method]
        params = urlparse.parse_qs(request.text or '',
                                   keep_blank_values=True)

        # parse_qs returns a MultiDict. Since python-ubersmith breaks out lists
        # into p[0] ... p[n], we have no need for this.
        params = {k: v[0] for k, v in params.items()}

        try:
            resp = mock(method, params, request, context)
            if isinstance(resp, MockResponseError):
                raise resp
        except MockResponseError as e:
            return e.to_response()
        else:
            return resp

    mock_url = 'mock://ubersmith/api/2.0/'
    reqmock.request(reqmock.ANY, mock_url, json=ubermock_call)

    # Ensure the ubersmith library uses our custom URL
    monkeypatch.setattr(ubersmith.api, '_DEFAULT_REQUEST_HANDLER',
                        ubersmith.api.RequestHandler(mock_url))

    class UberMock(object):
        ResponseError = MockResponseError
        url = mock_url

        def __init__(self, key=None):
            # We override __setattr__, so this is just easier
            self.__dict__.update({
                # The full dotted path of this mock/call
                'key': key,

                # Whether to ignore calls which don't have a response setup.
                # This is on every UberMock, but only the root one matters.
                'ignore_missing': False,

                # Holds the 'data' part of the response, if we're a call
                # May be a callable
                'response': _unset_value,
                # The entire response as returned by Ubersmith, if needed
                'raw_response': _unset_value,

                # Bookkeeping
                'called': False,
                'call_count': 0,
                'calls': [],
            })

            # Register ourself
            mocks[self.key] = self
            if self._is_valid_call(self.key):
                calls[self.key] = self

        ################################################
        # Public interface and important magic methods #
        ################################################

        def __setattr__(self, key, value):
            if key in self.__dict__:
                if key in {'response', 'raw_response'} and \
                        not self._is_valid_call(self.key):
                    raise Exception('%s is not a valid Ubersmith API call' %
                                    self.key)
                self.__dict__[key] = value
            else:
                full_key = self._get_fq_key(key)
                call = self._get_call(full_key)
                call.response = value

        def __getattr__(self, key):
            full_key = self._get_fq_key(key)
            return self._get_mock(full_key)

        def __call__(self, method, params, request, context):
            try:
                resp = self._build_response(method, params, request, context)
            except MockResponseError as resp:
                pass

            self._record_call(method, params, request, context, resp)
            return resp

        @property
        def last_call(self):
            return self.calls[-1]

        @property
        def first_call(self):
            return self.calls[0]

        def assert_called_once_with(self, **params):
            for record in self.calls:
                try:
                    return record.assert_called_with(**params)
                except AssertionError:
                    continue
            else:
                raise AssertionError(
                    '%s was never called with params %r' % (self.key, params))

        def assert_called_once_with_exactly(self, **params):
            for record in self.calls:
                try:
                    return record.assert_called_with_exactly(**params)
                except AssertionError:
                    continue
            else:
                raise AssertionError(
                    '%s was never called with exactly the params %r' % (
                        self.key, params))

        ###############################
        # Private methods and helpers #
        ###############################

        def _get_fq_key(self, *key_parts):
            parts = []
            if self.key:
                parts.append(self.key)
            parts += list(key_parts)
            return '.'.join(parts)

        @staticmethod
        def _is_valid_call(key):
            return key in ubersmith.api.METHODS

        @classmethod
        def _validate_call(cls, key):
            if not cls._is_valid_call(key):
                raise KeyError('%s is not a valid Ubersmith API call' % key)

        def _get_mock(self, key):
            if key not in mocks:
                return UberMock(key)
            return mocks[key]

        def _get_call(self, key):
            self._validate_call(key)
            return self._get_mock(key)

        def _wrap_response(self, response):
            def _response_method(method, params, request, context):
                data = response
                if callable(response):
                    data = response(method, params, request, context)
                if isinstance(data, MockResponseError):
                    raise data
                return {
                    'status': True,
                    'error_code': None,
                    'error_message': '',
                    'data': data,
                }
            return _response_method

        def _get_response_method(self):
            if self.raw_response is not _unset_value:
                if callable(self.raw_response):
                    return self.raw_response
                else:
                    return lambda *a: self.raw_response

            elif self.response is not _unset_value:
                return self._wrap_response(self.response)

        def _build_response(self, method, params, request, context):
            meth = self._get_response_method()
            if meth is None:
                raise Exception('No response setup for API call %s' % self.key)
            return meth(method, params, request, context)

        def _record_call(self, method, params, request, context, resp_obj):
                self.called = True
                self.call_count += 1
                self.calls.append(CallRecord(
                    self, method, params, request, context, resp_obj))

    return UberMock()
