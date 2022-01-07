from time import sleep
from typing import Literal
from unittest.mock import Mock
from unittest.mock import patch

import pytest
from pytest import raises

from aiocircuitbreaker import CircuitBreaker
from aiocircuitbreaker import CircuitBreakerError
from aiocircuitbreaker import State


async def pseudo_remote_call() -> Literal[True]:
    return True


circuitbreaker_success = CircuitBreaker()


@circuitbreaker_success
async def circuit_success() -> Literal[True]:
    return await pseudo_remote_call()


circuitbreaker_failure = CircuitBreaker(failure_threshold=1, name="circuit_failure")


@circuitbreaker_failure
async def circuit_failure() -> None:
    raise IOError()


circuitbreaker_threshold_1 = CircuitBreaker(failure_threshold=1, name="threshold_1")


@circuitbreaker_threshold_1
async def circuit_threshold_1() -> Literal[True]:
    return await pseudo_remote_call()


circuitbreaker_threshold_2 = CircuitBreaker(failure_threshold=2, recovery_timeout=1, name="threshold_2")


@circuitbreaker_threshold_2
async def circuit_threshold_2_timeout_1() -> Literal[True]:
    return await pseudo_remote_call()


circuitbreaker_threshold_3 = CircuitBreaker(failure_threshold=3, recovery_timeout=1, name="threshold_3")


@circuitbreaker_threshold_3
async def circuit_threshold_3_timeout_1() -> Literal[True]:
    return await pseudo_remote_call()


@pytest.mark.asyncio
async def test_circuit_pass_through() -> None:
    assert await circuit_success() is True


@patch('tests.test_functional.pseudo_remote_call', return_value=True)
@pytest.mark.asyncio
async def test_threshold_hit_prevents_consequent_calls(mock_remote: Mock) -> None:
    mock_remote.side_effect = IOError('Connection refused')

    assert circuitbreaker_threshold_1.closed

    with raises(IOError):
        await circuit_threshold_1()

    assert circuitbreaker_threshold_1.opened

    with raises(CircuitBreakerError):
        await circuit_threshold_1()

    mock_remote.assert_called_once_with()


@patch('tests.test_functional.pseudo_remote_call', return_value=True)
@pytest.mark.asyncio
async def test_circuitbreaker_recover_half_open(mock_remote: Mock) -> None:
    circuitbreaker = circuitbreaker_threshold_3

    # initial state: closed
    assert circuitbreaker.closed
    assert circuitbreaker.state == State.CLOSED

    # no exception -> success
    assert await circuit_threshold_3_timeout_1()

    # from now all subsequent calls will fail
    mock_remote.side_effect = IOError('Connection refused')

    # 1. failed call -> original exception
    with raises(IOError):
        await circuit_threshold_3_timeout_1()
    assert circuitbreaker.closed
    assert circuitbreaker.failure_count == 1

    # 2. failed call -> original exception
    with raises(IOError):
        await circuit_threshold_3_timeout_1()
    assert circuitbreaker.closed
    assert circuitbreaker.failure_count == 2

    # 3. failed call -> original exception
    with raises(IOError):
        await circuit_threshold_3_timeout_1()

    # Circuit breaker opens, threshold has been reached
    assert circuitbreaker.opened
    assert circuitbreaker.state == State.OPEN
    assert circuitbreaker.failure_count == 3
    assert 0 < circuitbreaker.open_remaining <= 1

    # 4. failed call -> not passed to function -> CircuitBreakerError
    with raises(CircuitBreakerError):
        await circuit_threshold_3_timeout_1()
    assert circuitbreaker.opened
    assert circuitbreaker.failure_count == 3
    assert 0 < circuitbreaker.open_remaining <= 1

    # 5. failed call -> not passed to function -> CircuitBreakerError
    with raises(CircuitBreakerError):
        await circuit_threshold_3_timeout_1()
    assert circuitbreaker.opened
    assert circuitbreaker.failure_count == 3
    assert 0 < circuitbreaker.open_remaining <= 1

    # wait for 1 second (recover timeout)
    sleep(1)

    # circuit half-open -> next call will be passed through
    assert not circuitbreaker.closed
    assert circuitbreaker.open_remaining < 0
    assert circuitbreaker.state == State.HALF_OPEN

    # State half-open -> function is executed -> original exception
    with raises(IOError):
        await circuit_threshold_3_timeout_1()
    assert circuitbreaker.opened
    assert circuitbreaker.failure_count == 4
    assert 0 < circuitbreaker.open_remaining <= 1

    # State open > not passed to function -> CircuitBreakerError
    with raises(CircuitBreakerError):
        await circuit_threshold_3_timeout_1()


@patch('tests.test_functional.pseudo_remote_call', return_value=True)
@pytest.mark.asyncio
async def test_circuitbreaker_reopens_after_successful_calls(mock_remote: Mock) -> None:
    circuitbreaker = circuitbreaker_threshold_2

    # initial state: closed
    assert circuitbreaker.closed
    assert circuitbreaker.state == State.CLOSED
    assert circuitbreaker.failure_count == 0

    # successful call -> no exception
    assert await circuit_threshold_2_timeout_1()

    # from now all subsequent calls will fail
    mock_remote.side_effect = IOError('Connection refused')

    # 1. failed call -> original exception
    with raises(IOError):
        await circuit_threshold_2_timeout_1()
    assert circuitbreaker.closed
    assert circuitbreaker.failure_count == 1

    # 2. failed call -> original exception
    with raises(IOError):
        await circuit_threshold_2_timeout_1()

    # Circuit breaker opens, threshold has been reached
    assert circuitbreaker.opened
    assert circuitbreaker.state == State.OPEN
    assert circuitbreaker.failure_count == 2
    assert 0 < circuitbreaker.open_remaining <= 1

    # 4. failed call -> not passed to function -> CircuitBreakerError
    with raises(CircuitBreakerError):
        await circuit_threshold_2_timeout_1()
    assert circuitbreaker.opened
    assert circuitbreaker.failure_count == 2
    assert 0 < circuitbreaker.open_remaining <= 1

    # from now all subsequent calls will succeed
    mock_remote.side_effect = None

    # but recover timeout has not been reached -> still open
    # 5. failed call -> not passed to function -> CircuitBreakerError
    with raises(CircuitBreakerError):
        await circuit_threshold_2_timeout_1()
    assert circuitbreaker.opened
    assert circuitbreaker.failure_count == 2
    assert 0 < circuitbreaker.open_remaining <= 1

    # wait for 1 second (recover timeout)
    sleep(1)

    # circuit half-open -> next call will be passed through
    assert not circuitbreaker.closed
    assert circuitbreaker.failure_count == 2
    assert circuitbreaker.open_remaining < 0
    assert circuitbreaker.state == State.HALF_OPEN

    # successful call
    assert await circuit_threshold_2_timeout_1()

    # circuit closed and reset'ed
    assert circuitbreaker.closed
    assert circuitbreaker.state == State.CLOSED
    assert circuitbreaker.failure_count == 0

    # some another successful calls
    assert await circuit_threshold_2_timeout_1()
    assert await circuit_threshold_2_timeout_1()
    assert await circuit_threshold_2_timeout_1()
