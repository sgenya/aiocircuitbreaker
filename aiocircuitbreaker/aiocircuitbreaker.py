import asyncio
from datetime import datetime
from datetime import timedelta
from enum import Enum
from functools import wraps
from tracemalloc import Traceback
from typing import Any
from typing import Callable
from typing import Coroutine
from typing import Literal
from typing import Optional
from typing import Type
from typing import Union


class State(Enum):
    CLOSED = 'closed'
    OPEN = 'open'
    HALF_OPEN = 'half_open'


class CircuitBreaker:
    FAILURE_THRESHOLD: int = 5
    RECOVERY_TIMEOUT: int = 30
    EXPECTED_EXCEPTION: Type[Exception] = Exception
    FALLBACK_FUNCTION: Optional[Callable[..., Any]] = None

    def __init__(
        self,
        failure_threshold: Optional[int] = None,
        recovery_timeout: Optional[int] = None,
        expected_exception: Optional[Type[Exception]] = None,
        name: str = '',
        fallback_function: Optional[Callable[..., Any]] = None,
    ):
        self._failure_threshold: int = failure_threshold or self.FAILURE_THRESHOLD
        self._recovery_timeout: int = recovery_timeout or self.RECOVERY_TIMEOUT
        self._expected_exception: Union[Exception, Type[Exception]] = expected_exception or self.EXPECTED_EXCEPTION
        self._fallback_function: Optional[Callable[..., Any]] = fallback_function or self.FALLBACK_FUNCTION
        self._name: str = name
        self._failure_count: int = 0
        self._state: State = State.CLOSED
        self._opened: datetime = datetime.utcnow()
        self._last_failure: Optional[Exception] = None

    def __call__(self, wrapped: Callable[..., Any]) -> Callable[..., Any]:
        return self.decorate(wrapped)

    def __enter__(self) -> None:
        return None

    def __exit__(
        self, exc_type: Optional[Type[Exception]], exc_value: Optional[Exception], traceback: Optional[Traceback]
    ) -> Literal[False]:
        if exc_type and issubclass(exc_type, self._expected_exception):  # type: ignore
            # exception was raised and is our concern
            self._last_failure = exc_value
            self.__call_failed()
        else:
            self.__call_succeeded()
        return False  # return False to raise exception if any

    def decorate(self, function: Callable[..., Coroutine[Any, Any, Any]]) -> Callable[..., Coroutine[Any, Any, Any]]:
        """
        Applies the circuit breaker to a function
        """
        if asyncio.iscoroutinefunction(function):

            @wraps(function)
            async def wrapper(*args: Any, **kwargs: Any) -> Any:
                if self.opened:
                    if self.fallback_function:
                        if asyncio.iscoroutinefunction(self.fallback_function):
                            return await self.fallback_function(*args, **kwargs)
                        return self.fallback_function(*args, **kwargs)
                    raise CircuitBreakerError(self)
                return await self.call(function, *args, **kwargs)

            return wrapper

        else:
            raise ValueError(f'function "{function.__name__}" is not awaitable')

    async def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """
        Calls the decorated function and applies the circuit breaker
        rules on success or failure
        :param func: Decorated async function
        """
        with self:
            return await func(*args, **kwargs)

    def __call_succeeded(self) -> None:
        """
        Close circuit after successful execution and reset failure count
        """
        self._state = State.CLOSED
        self._last_failure = None
        self._failure_count = 0

    def __call_failed(self) -> None:
        """
        Count failure and open circuit, if threshold has been reached
        """
        self._failure_count += 1
        if self._failure_count >= self._failure_threshold:
            self._state = State.OPEN
            self._opened = datetime.utcnow()

    @property
    def state(self) -> State:
        if self._state == State.OPEN and self.open_remaining <= 0:
            return State.HALF_OPEN
        return self._state

    @property
    def open_until(self) -> datetime:
        """
        The datetime, when the circuit breaker will try to recover
        :return: datetime
        """
        return self._opened + timedelta(seconds=self._recovery_timeout)

    @property
    def open_remaining(self) -> float:
        """
        Number of seconds remaining, the circuit breaker stays in OPEN state
        :return: int
        """
        return (self.open_until - datetime.utcnow()).total_seconds()

    @property
    def failure_count(self) -> int:
        return self._failure_count

    @property
    def closed(self) -> bool:
        return self._state == State.CLOSED

    @property
    def opened(self) -> bool:
        return self.state == State.OPEN

    @property
    def name(self) -> str:
        return self._name

    @property
    def last_failure(self) -> Optional[Exception]:
        return self._last_failure

    @property
    def fallback_function(self) -> Optional[Callable[..., Any]]:
        return self._fallback_function


class CircuitBreakerError(Exception):
    def __init__(self, circuit_breaker: CircuitBreaker, *args: Any):
        """
        :param circuit_breaker:
        :param args:
        :param kwargs:
        :return:
        """
        super(CircuitBreakerError, self).__init__(*args)
        self._circuit_breaker: CircuitBreaker = circuit_breaker

    def __str__(self, *args: Any, **kwargs: Any) -> str:
        return 'Circuit "{}" OPEN until {} ({} failures, {} sec remaining) (last_failure: {})'.format(
            self._circuit_breaker.name,
            self._circuit_breaker.open_until,
            self._circuit_breaker.failure_count,
            round(self._circuit_breaker.open_remaining),
            self._circuit_breaker.last_failure.__repr__(),
        )


def circuit(
    failure_threshold: Union[None, int, Callable[..., Coroutine[Any, Any, Any]]] = None,
    recovery_timeout: Optional[int] = None,
    expected_exception: Optional[Type[Exception]] = None,
    name: str = '',
    fallback_function: Optional[Callable[..., Any]] = None,
    cls: Type[CircuitBreaker] = CircuitBreaker,
) -> Union[Callable[..., Any], CircuitBreaker]:

    # if the decorator is used without parameters, the
    # wrapped function is provided as first argument
    if callable(failure_threshold):
        return cls().decorate(failure_threshold)
    else:
        return cls(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            expected_exception=expected_exception,
            name=name,
            fallback_function=fallback_function,
        )
