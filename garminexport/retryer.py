import abc
import logging
import time
from datetime import datetime
from datetime import timedelta

log = logging.getLogger(__name__)


class GaveUpError(Exception):
    """Raised by a :class:`Retryer` that has exceeded its maximum number of retries."""
    pass


class DelayStrategy(object):
    """Used by a :class:`Retryer` to determines how long to wait after an
    attempt before the next retry. """
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def next_delay(self, attempts):
        """Returns the time to wait before the next attempt.

        :param attempts: The total number of (failed) attempts performed thus far.
        :type attempts: int

        :return: The delay before the next attempt.
        :rtype: `timedelta`
        """
        pass


class FixedDelayStrategy(DelayStrategy):
    """A retry :class:`DelayStrategy` that produces a fixed delay between attempts."""

    def __init__(self, delay):
        """
        :param delay: Attempt delay.
        :type delay: `timedelta`
        """
        self.delay = delay

    def next_delay(self, attempts):
        return self.delay


class ExponentialBackoffDelayStrategy(DelayStrategy):
    """A retry :class:`DelayStrategy` that produces exponentially longer
    delay between every attempt. The first attempt will be followed
    by a `<initial-delay> * 2**0` delay. The following delays will be
    `<initial-delay> * 2**1`, `<initial-delay> * 2**2`, and so on ...
    """

    def __init__(self, initial_delay):
        """
        :param initial_delay: Initial delay.
        :type initial_delay: `timedelta`
        """
        self.initial_delay = initial_delay

    def next_delay(self, attempts):
        if attempts <= 0:
            return timedelta(seconds=0)
        delay_seconds = self.initial_delay.total_seconds() * 2 ** (attempts - 1)
        return timedelta(seconds=delay_seconds)


class NoDelayStrategy(FixedDelayStrategy):
    """A retry :class:`DelayStrategy` that doesn't introduce any delay between attempts."""

    def __init__(self):
        super(NoDelayStrategy, self).__init__(timedelta(seconds=0))


class ErrorStrategy(object):
    """Used by a :class:`Retryer` to determine which errors are to be
    suppressed and which errors are to be re-raised and thereby end the (re)trying."""
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def should_suppress(self, error):
        """Called after an attempt that raised an exception to determine if
        that error should be suppressed (continue retrying) or be re-raised (and end the retrying).

        :param error: Error that was raised from an attempt.
        """
        pass


class SuppressAllErrorStrategy(ErrorStrategy):
    """An :class:`ErrorStrategy` that suppresses all types of errors raised
    on attempts to perform the call."""

    def should_suppress(self, error):
        return True


class StopStrategy(object):
    """Determines for how long a :class:`Retryer` should keep (re)trying."""
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def should_continue(self, attempts, elapsed_time):
        """Called after a failed attempt to determine if we should keep trying.

        :param attempts: Total number of (failed) attempts thus far.
        :type attempts: int
        :param elapsed_time: Total elapsed time since first attempt.
        :type elapsed_time: timedelta

        :return: `True` if the `Retryer` should keep trying, `False` otherwise.
        :rtype: bool
        """
        pass


class NeverStopStrategy(StopStrategy):
    """A :class:`StopStrategy` that never gives up."""

    def should_continue(self, attempts, elapsed_time):
        return True


class MaxRetriesStopStrategy(StopStrategy):
    """A :class:`StopStrategy` that gives up after a certain number of retries."""

    def __init__(self, max_retries):
        self.max_retries = max_retries

    def should_continue(self, attempts, elapsed_time):
        return attempts <= self.max_retries


class Retryer(object):
    """A :class:`Retryer` makes repeated calls to a function until either
    the return value satisfies a certain condition (`returnval_predicate`)
    or until a stop strategy (`stop_strategy`) determines that enough
    attempts have been made (or a too long time has elapsed). Should the
    `stop_strategy` decide to abort, a :class:`GaveUpError` is raised.

    The delay between attempts is controlled by a `delay_strategy`.

    Should the attempted call raise an Exception, an `error_strategy` gets
    to decide if the error should be suppressed or re-raised (in which case
    the retrying ends with that error).
    """

    def __init__(
            self,
            returnval_predicate=lambda returnval: True,
            delay_strategy=NoDelayStrategy(),
            stop_strategy=NeverStopStrategy(),
            error_strategy=SuppressAllErrorStrategy()):
        """Creates a new :class:`Retryer` set up to use a given set of
        strategies to control its behavior.

        With only default values, the retryer will keep retrying
        indefinitely until a value (any value) is returned by
        the called function. Any raised errors will be suppressed.

        :param returnval_predicate: predicate that determines if a return
          value is considered successful. When the predicate evaluates to
          `True`, the `call` function will return with that return value.
        :type returnval_predicate: `function(returnvalue) => bool`
        :param delay_strategy: determines the time delay to introduce between
          attempts.
        :type delay_strategy: :class:`DelayStrategy`
        :param stop_strategy: determines when we are to stop retrying.
        :type stop_strategy: :class:`StopStrategy`
        :param error_strategy: determines which errors (if any) to suppress
          when raised by the called function (`None` to stop on any error).
        :type error_strategy: :class:`ErrorStrategy`
        """
        self.returnval_predicate = returnval_predicate
        self.delay_strategy = delay_strategy
        self.stop_strategy = stop_strategy
        self.error_strategy = error_strategy

    def call(self, function, *args, **kw):
        """Calls the given `function`, with the given arguments, repeatedly
        until either (1) a satisfactory result is obtained (as indicated by
        the `returnval_predicate`), or (2) until the `stop_strategy`
        determines that no more attempts are to be made (results in a
        `GaveUpException`), or (3) until the called function raises an error
        that is not suppressed by the `error_strategy` (the call will raise
        that error).

        :param function: A `callable`.
        :param args: Any positional arguments to call `function` with.
        :param kw: Any keyword arguments to call `function` with.
        """
        name = function.__name__
        start = datetime.now()
        attempts = 0
        while True:
            try:
                attempts += 1
                log.info('{%s}: attempt %d ...', name, attempts)
                returnval = function(*args, **kw)
                if self.returnval_predicate(returnval):
                    # return value satisfies predicate, we're done!
                    log.debug('{%s}: success: "%s"', name, returnval)
                    return returnval
                log.debug('{%s}: failed: return value: %s', name, returnval)
            except Exception as e:
                if self.error_strategy is None or not self.error_strategy.should_suppress(e):
                    log.debug(f'not suppressing: {e} ({type(e)})')
                    raise e
                log.debug('{%s}: failed: error: %s', name, e)
            elapsed_time = datetime.now() - start
            # should we make another attempt?
            if not self.stop_strategy.should_continue(attempts, elapsed_time):
                raise GaveUpError('{{}}: gave up after {} failed attempt(s)'.format(name, attempts))
            delay = self.delay_strategy.next_delay(attempts)
            log.info('{%s}: waiting %d seconds for next attempt', name, delay.total_seconds())
            time.sleep(delay.total_seconds())
