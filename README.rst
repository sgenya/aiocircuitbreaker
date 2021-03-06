aiocircuitbreaker
-----------------

.. image:: https://img.shields.io/pypi/v/aiocircuitbreaker.svg
    :target: https://pypi.python.org/pypi/aiocircuitbreaker

.. image:: https://img.shields.io/pypi/pyversions/aiocircuitbreaker.svg
    :target: https://pypi.python.org/pypi/aiocircuitbreaker

.. image:: https://codecov.io/gh/GenyaSol/aiocircuitbreaker/branch/main/graph/badge.svg
    :target: https://app.codecov.io/gh/GenyaSol/aiocircuitbreaker

.. image:: https://github.com/GenyaSol/aiocircuitbreaker/actions/workflows/run-test.yml/badge.svg
    :target: https://github.com/GenyaSol/aiocircuitbreaker/actions/workflows/run-test.yml

.. image:: https://img.shields.io/badge/code%20style-black-000000.svg
    :target: https://github.com/python/black

This is an async Python implementation of the `circuitbreaker`__ library.

.. _circuitbreaker: https://github.com/fabfuel/circuitbreaker

__ circuitbreaker_


Installation
------------

The project is available on PyPI. Simply run::

    $ pip install aiocircuitbreaker


Usage
-----

This is the simplest example. Just decorate a async function with the ``@circuit`` decorator::

    from aiocircuitbreaker import circuit

    @circuit
    async def external_call():
        ...


This decorator sets up a circuit breaker with the default settings. The circuit breaker:

- monitors the function execution and counts failures
- resets the failure count after every successful execution (while it is closed)
- opens and prevents further executions after 5 subsequent failures
- switches to half-open and allows one test-execution after 30 seconds recovery timeout
- closes if the test-execution succeeded
- considers all raised exceptions (based on class ``Exception``) as an expected failure
- is named "external_call" - the name of the function it decorates


What does *failure* mean?
=========================
A *failure* is a raised exception, which was not caught during the function call.
By default, the circuit breaker listens for all exceptions based on the class ``Exception``.
That means, that all exceptions raised during the function call are considered as an
"expected failure" and will increase the failure count.

Get specific about the expected failure
=======================================
It is important, to be **as specific as possible**, when defining the expected exception.
The main purpose of a circuit breaker is to protect your distributed system from a cascading failure.
That means, you probably want to open the circuit breaker only, if the integration point on the other
end is unavailable. So e.g. if there is an ``ConnectionError`` or a request ``Timeout``.

If you are e.g. using the requests library (http://docs.python-requests.org/) for making HTTP calls,
its ``RequestException`` class would be a great choice for the ``expected_exception`` parameter.

All recognized exceptions will be re-raised anyway, but the goal is, to let the circuit breaker only
recognize those exceptions which are related to the communication to your integration point.


Configuration
-------------
The following configuration options can be adjusted via decorator parameters. For example::

    from aiocircuitbreaker import circuit

    @circuit(failure_threshold=10, expected_exception=ConnectionError)
    async def external_call():
        ...



failure threshold
=================
By default, the circuit breaker opens after 5 subsequent failures. You can adjust this value with the ``failure_threshold`` parameter.

recovery timeout
================
By default, the circuit breaker stays open for 30 seconds to allow the integration point to recover.
You can adjust this value with the ``recovery_timeout`` parameter.

expected exception
==================
By default, the circuit breaker listens for all exceptions which are based on the ``Exception`` class.
You can adjust this with the ``expected_exception`` parameter. It can be either an exception class or a tuple of exception classes.

name
====
By default, the circuit breaker name is empty string. You can adjust the name with parameter ``name``.

fallback function
=================
By default, the circuit breaker will raise a ``CircuitBreaker`` exception when the circuit is opened.
You can instead specify a function (async function) to be called when the circuit is opened. This function can be specified with the
``fallback_function`` parameter and will be called with the same parameters as the decorated function would be.

Advanced Usage
--------------
If you apply circuit breakers to a couple of functions and you always set specific options other than the default values,
you can extend the ``CircuitBreaker`` class and create your own circuit breaker subclass instead::

    from aiocircuitbreaker import CircuitBreaker

    class MyCircuitBreaker(CircuitBreaker):
        FAILURE_THRESHOLD = 10
        RECOVERY_TIMEOUT = 60
        EXPECTED_EXCEPTION = RequestException


Now you have two options to apply your circuit breaker to a function. As an Object directly::

    @MyCircuitBreaker()
    async def external_call():
        ...

Please note, that the circuit breaker class has to be initialized, you have to use a class instance as decorator (``@MyCircuitBreaker()``), not the class itself (``@MyCircuitBreaker``).

Or via the decorator proxy::

    @circuit(cls=MyCircuitBreaker)
    async def external_call():
        ...

