import pytest

import ubersmith.client
import ubersmith.exceptions


def test_add_client(ubermock):
    client_id = 1234
    ubermock.client.add = client_id

    assert ubersmith.client.add(login='test') == 1234



def test_unknown_client(ubermock):
    ubermock.client.get = ubermock.ResponseError('Invalid client!', 1)

    with pytest.raises(ubersmith.exceptions.ResponseError):
        ubersmith.client.get(client_id=1234)


def test_unknown_client_raw(ubermock):
    ubermock.client.get.raw_response = {
        'status': False,
        'data': '',
        'error_message': 'Invalid client',
        'error_code': 1,
    }

    with pytest.raises(ubersmith.exceptions.ResponseError):
        ubersmith.client.get(client_id=1234)


def test_dynamic_client(ubermock):
    def get_client(method, params, request, context):
        if params['client_id'] == '1':
            return {'client_id': 1}
        else:
            raise ubermock.ResponseError('Invalid client!', 1)

    ubermock.client.get = get_client

    assert ubersmith.client.get(client_id=1) == {'client_id': 1}
    with pytest.raises(ubersmith.exceptions.ResponseError):
        ubersmith.client.get(client_id=2)


def test_calls(ubermock):
    client_resp = {
        'client_id': 123,
    }

    ubermock.client.get = client_resp
    assert not ubermock.client.get.called
    assert ubermock.client.get.call_count == 0
    assert ubermock.client.get.calls == []

    assert ubersmith.client.get(client_id=123) == client_resp

    assert ubermock.client.get.called
    assert ubermock.client.get.call_count == 1
    assert len(ubermock.client.get.calls) == 1

    record = ubermock.client.get.calls[0]
    assert record.params['client_id'] == '123'
    assert record.response == {
        'status': True,
        'error_message': '',
        'error_code': None,
        'data': client_resp,
    }
