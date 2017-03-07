from datetime import datetime
from datetime import timedelta
import logging
import time
import unittest

from garminexport.retryer import (
    Retryer,
    NoDelayStrategy, FixedDelayStrategy, ExponentialBackoffDelayStrategy,
    SuppressAllErrorStrategy,
    NeverStopStrategy
)

class Counter(object):
    """An object whose `next_value` method returns increasing values."""

    def __init__(self, start_at=0):
        self.nextval = start_at

    def next_value(self):
        current = self.nextval
        self.nextval += 1
        return current


class FailNTimesThenReturn(object):
    """An object whose `next_value` method fails N times and then, on the Nth
    attempt, returns a value."""

    def __init__(self, calls_until_success, returnval):
        self.called = 0
        self.calls_until_success = calls_until_success
        self.returnval = returnval

    def next_value(self):
        self.called += 1
        if self.called < self.calls_until_success:
            raise RuntimeError("boom!")
        return self.returnval    


    
class TestRetryer(unittest.TestCase):
    """Exercise `Retryer`."""


    def test_with_defaults(self):
        """Default `Retryer` behavior is to keep trying until a(ny) value is
        returned."""
        failing_client = FailNTimesThenReturn(10, "success!")
        returnval = Retryer().call(failing_client.next_value)
        self.assertEqual(returnval, "success!")
        self.assertEqual(failing_client.called, 10)
        

    def test_with_returnval_predicate(self):
        """`Retryer` should only return when the returnval_predicate says so."""
        retryer = Retryer(returnval_predicate=lambda r: r == 20)
        self.assertEqual(retryer.call(Counter().next_value), 20)
   
    def test_function_with_positional_args(self):
        """`Retryer` should be able to call a function with positional args."""
        # TODO
        pass

    def test_function_with_positional_and_kw_args(self):
        """`Retryer` should be able to call a function with keyword args."""
        # TODO
        pass
    
    
    def test_bla(self):
        retryer = Retryer()
        func = lambda : int(time.time())
        
        returnval = retryer.call(func)
        print returnval
        

class TestFixedDelayStrategy(unittest.TestCase):
    """Exercise `FixedDelayStrategy`."""

    def setUp(self):
        # object under test
        self.strategy = FixedDelayStrategy(timedelta(seconds=10))
    
    def test_calculate_delay(self):
        """`FixedDelayStrategy` should always return the same delay."""
        self.assertEqual(self.strategy.next_delay(0), timedelta(seconds=10))
        self.assertEqual(self.strategy.next_delay(1), timedelta(seconds=10))
        self.assertEqual(self.strategy.next_delay(2), timedelta(seconds=10))
        self.assertEqual(self.strategy.next_delay(3), timedelta(seconds=10))
        self.assertEqual(self.strategy.next_delay(10), timedelta(seconds=10))
        self.assertEqual(self.strategy.next_delay(100), timedelta(seconds=10))


class TestNoDelayStrategy(unittest.TestCase):
    """Exercise `NoDelayStrategy`."""

    def setUp(self):
        # object under test
        self.strategy = NoDelayStrategy()
    
    def test_calculate_delay(self):
        """`NoDelayStrategy` should always return no delay."""
        self.assertEqual(self.strategy.next_delay(0), timedelta(seconds=0))
        self.assertEqual(self.strategy.next_delay(1), timedelta(seconds=0))
        self.assertEqual(self.strategy.next_delay(2), timedelta(seconds=0))
        self.assertEqual(self.strategy.next_delay(3), timedelta(seconds=0))
        self.assertEqual(self.strategy.next_delay(10), timedelta(seconds=0))
        self.assertEqual(self.strategy.next_delay(100), timedelta(seconds=0))

        
class TestExponentialBackoffDelayStrategy(unittest.TestCase):
    """Exercise `ExponentialBackoffDelayStrategy`."""

    def setUp(self):
        # object under test
        self.strategy = ExponentialBackoffDelayStrategy(timedelta(seconds=1))
    
    def test_calculate_delay(self):
        """`ExponentialBackoffDelayStrategy` should return exponentially increasing delay."""
        self.assertEqual(self.strategy.next_delay(0), timedelta(seconds=0))
        self.assertEqual(self.strategy.next_delay(1), timedelta(seconds=1))
        self.assertEqual(self.strategy.next_delay(2), timedelta(seconds=2))
        self.assertEqual(self.strategy.next_delay(3), timedelta(seconds=4))
        self.assertEqual(self.strategy.next_delay(4), timedelta(seconds=8))
        self.assertEqual(self.strategy.next_delay(5), timedelta(seconds=16))
        self.assertEqual(self.strategy.next_delay(10), timedelta(seconds=512))

    def test_initial_delay(self):
        """The initial delay is used to scale the series of delays."""
        self.strategy = ExponentialBackoffDelayStrategy(timedelta(seconds=2))
        self.assertEqual(self.strategy.next_delay(0), timedelta(seconds=0))
        self.assertEqual(self.strategy.next_delay(1), timedelta(seconds=2*1))
        self.assertEqual(self.strategy.next_delay(2), timedelta(seconds=2*2))
        self.assertEqual(self.strategy.next_delay(3), timedelta(seconds=2*4))
        self.assertEqual(self.strategy.next_delay(4), timedelta(seconds=2*8))
        self.assertEqual(self.strategy.next_delay(5), timedelta(seconds=2*16))
        self.assertEqual(self.strategy.next_delay(10), timedelta(seconds=2*512))
        
        
class TestSuppressAllErrorStrategy(unittest.TestCase):
    """Exercise `SuppressAllErrorStrategy`."""

    def setUp(self):
        # object under test
        self.strategy = SuppressAllErrorStrategy()
    
    def test_suppress(self):
        """`SuppressAllErrorStrategy` should always suppress."""
        self.assertTrue(self.strategy.should_suppress(RuntimeError("boom!")))
        self.assertTrue(self.strategy.should_suppress(Exception("boom!")))
        # non-exception error
        self.assertTrue(self.strategy.should_suppress("boom!"))
        self.assertTrue(self.strategy.should_suppress(None))

        
class TestNeverStopStrategy(unittest.TestCase):
    """Exercise `NeverStopStrategy`"""

    def setUp(self):
        # object under test
        self.strategy = NeverStopStrategy()
    
    def test_suppress(self):
        """`SuppressAllErrorStrategy` should always suppress."""
        self.assertTrue(self.strategy.should_continue(1, timedelta(seconds=1)))
        self.assertTrue(self.strategy.should_continue(2, timedelta(seconds=4)))
        self.assertTrue(self.strategy.should_continue(3, timedelta(seconds=4)))
        self.assertTrue(self.strategy.should_continue(4, timedelta(seconds=5)))
        self.assertTrue(self.strategy.should_continue(400, timedelta(hours=1)))
        self.assertTrue(self.strategy.should_continue(4000, timedelta(hours=8)))
    
if __name__ == '__main__':
    logging.basicConfig(format="%(asctime)s %(message)s", level=logging.DEBUG)
    
    unittest.main()
