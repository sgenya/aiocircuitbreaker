from unittest.mock import AsyncMock
from unittest.mock import Mock
from unittest.mock import patch

import pytest
from pytest import raises

from aiocircuitbreaker import CircuitBreaker
from aiocircuitbreaker import CircuitBreakerError
from aiocircuitbreaker import State
from aiocircuitbreaker import circuit


def test_circuitbreaker_error__str__() -> None:
    cb = CircuitBreaker(name='Foobar')
    cb._last_failure = Exception()
    error = CircuitBreakerError(cb)

    assert str(error).startswith('Circuit "Foobar" OPEN until ')
    assert str(error).endswith('(0 failures, 30 sec remaining) (last_failure: Exception())')


@pytest.mark.asyncio
async def test_circuitbreaker_should_save_last_exception_on_failure_call() -> None:
    cb = CircuitBreaker(name='Foobar')

    func = AsyncMock(side_effect=IOError)

    with raises(IOError):
        await cb.call(func)

    assert isinstance(cb.last_failure, IOError)


@pytest.mark.asyncio
async def test_circuitbreaker_should_clear_last_exception_on_success_call() -> None:
    cb = CircuitBreaker(name='Foobar')
    cb._last_failure = IOError()
    assert isinstance(cb.last_failure, IOError)

    func = AsyncMock(return_value=True)

    await cb.call(func)

    assert cb.last_failure is None


@pytest.mark.asyncio
async def test_circuitbreaker_should_call_fallback_function_if_open() -> None:
    fallback = Mock(return_value=True)

    func = AsyncMock(return_value=False)

    cb = CircuitBreaker(name='WithFallback', fallback_function=fallback)
    cb._state = State.OPEN
    decorated_func = cb.decorate(func)

    await decorated_func()
    fallback.assert_called_once_with()


@pytest.mark.asyncio
async def test_circuitbreaker_should_call_async_fallback_function_if_open() -> None:
    fallback = AsyncMock(return_value=True)

    func = AsyncMock(return_value=False)

    cb = CircuitBreaker(name='WithFallback', fallback_function=fallback)
    cb._state = State.OPEN
    decorated_func = cb.decorate(func)

    await decorated_func()
    fallback.assert_called_once_with()


@pytest.mark.asyncio
async def test_circuitbreaker_should_not_call_function_if_open() -> None:
    fallback = Mock(return_value=True)

    func = AsyncMock(return_value=False)

    cb = CircuitBreaker(name='WithFallback', fallback_function=fallback)
    cb._state = State.OPEN
    decorated_func = cb.decorate(func)

    assert await decorated_func() == fallback.return_value
    assert not func.called


@pytest.mark.asyncio
async def test_circuitbreaker_call_fallback_function_with_parameters() -> None:
    fallback = Mock(return_value=True)

    function = AsyncMock(return_value=False)

    cb = circuit(name='with_fallback', fallback_function=fallback)

    # mock opened prop to see if fallback is called with correct parameters.
    cb._state = State.OPEN  # type: ignore
    func_decorated = cb.decorate(function)  # type: ignore

    await func_decorated('test2', test='test')

    # check args and kwargs are getting correctly to fallback function

    fallback.assert_called_once_with('test2', test='test')


@pytest.mark.asyncio
async def test_circuitbreaker_call_async_fallback_function_with_parameters() -> None:
    fallback = AsyncMock(return_value=True)

    function = AsyncMock(return_value=False)

    cb = circuit(name='with_fallback', fallback_function=fallback)

    # mock opened prop to see if fallback is called with correct parameters.
    cb._state = State.OPEN  # type: ignore
    func_decorated = cb.decorate(function)  # type: ignore

    await func_decorated('test2', test='test')

    # check args and kwargs are getting correctly to fallback function

    fallback.assert_called_once_with('test2', test='test')


@patch('aiocircuitbreaker.CircuitBreaker.decorate')
def test_circuit_decorator_without_args(circuitbreaker_mock: Mock) -> None:
    function = AsyncMock(return_value=False)
    circuit(function)
    circuitbreaker_mock.assert_called_once_with(function)


@patch('aiocircuitbreaker.CircuitBreaker.__init__')
def test_circuit_decorator_with_args(circuitbreaker_mock: Mock) -> None:
    circuitbreaker_mock.return_value = None
    function_fallback = lambda: True
    circuit(10, 20, KeyError, 'foobar', function_fallback)
    circuitbreaker_mock.assert_called_once_with(
        expected_exception=KeyError,
        failure_threshold=10,
        recovery_timeout=20,
        name='foobar',
        fallback_function=function_fallback,
    )
