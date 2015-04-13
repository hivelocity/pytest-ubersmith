pytest-ubersmith
================
Mock out calls to the python-ubersmith library


Usage
-----

pytest-ubersmith makes it really easy to mock out API calls:

.. code-block:: python

    import ubersmith.client

    def test_add_client(ubermock):
        client_id = 1234
        ubermock.client.add = client_id

        assert ubersmith.client.add(login='test') == 1234

To have python-ubersmith raise a ResponseError, return an
`ubermock.ResponseError`:

.. code-block:: python

    import ubersmith.client
    import ubersmith.exceptions

    def test_unknown_client(ubermock):
        ubermock.client.get = ubermock.ResponseError('Invalid client!', 1)

        with pytest.raises(ubersmith.exceptions.ResponseError):
            ubersmith.client.get(client_id=1234)

If you need complete control over the response, you can return the whole
Ubersmith JSON response:

.. code-block:: python

    import pytest
    import ubersmith.client
    import ubersmith.exceptions

    def test_unknown_client_raw(ubermock):
        ubermock.client.get.raw_response = {
            'status': False,
            'data': '',
            'error_message': 'Invalid client',
            'error_code': 1,
        }

        with pytest.raises(ubersmith.exceptions.ResponseError):
            ubersmith.client.get(client_id=1234)

You can even pass a callable for dynamic responses:

.. code-block:: python

    import pytest
    import ubersmith.client
    import ubersmith.exceptions

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
