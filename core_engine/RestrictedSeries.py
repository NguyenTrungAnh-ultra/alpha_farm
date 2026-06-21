"""
RestrictedSeries
================
A custom wrapper around pandas.Series designed to emulate XNOQuant Sandbox AST restrictions.

This class blocks direct calls to standard pandas Series methods (like `.mean()`, `.rolling()`, `.iloc`) 
and throws Attribute/Type errors, while whitelisting safe operations (like `.shift()`, `.diff()`, 
`.fillna()`) and supporting arithmetic/boolean operator overloading.
"""

import pandas as pd
import numpy as np
import logging

logger = logging.getLogger("core_engine.RestrictedSeries")

class RestrictedSeries:
    """
    A protected wrapper around pandas.Series.
    
    Prevents unauthorized pandas attribute/method access or direct physical indexing 
    within strategy algorithms, simulating sandbox restrictions. Allows basic math, 
    logical operations, and select causal methods (e.g. shift, diff, fillna).
    """
    def __init__(self, data):
        """
        Initialize the RestrictedSeries.

        Parameters
        ----------
        data : RestrictedSeries, pd.Series, or array-like
            The underlying data series to wrap.
        """
        if isinstance(data, RestrictedSeries):
            self._data = data._data.copy()
        elif isinstance(data, pd.Series):
            self._data = data.copy()
        else:
            self._data = pd.Series(data)

    # Whitelist of allowed direct pandas methods in XNO Sandbox
    def fillna(self, *args, **kwargs):
        if kwargs.get('method') == 'bfill' or (len(args) > 1 and args[1] == 'bfill'):
            raise ValueError("XNO Operator Error: Backfill (bfill) is rejected for causal safety.")
        return self._wrap(self._data.fillna(*args, **kwargs))

    def ffill(self, *args, **kwargs):
        return self._wrap(self._data.ffill(*args, **kwargs))

    def where(self, *args, **kwargs):
        unwrapped_args = [self._unwrap(a) for a in args]
        unwrapped_kwargs = {k: self._unwrap(v) for k, v in kwargs.items()}
        return self._wrap(self._data.where(*unwrapped_args, **unwrapped_kwargs))

    def pct_change(self, *args, **kwargs):
        return self._wrap(self._data.pct_change(*args, **kwargs))

    def shift(self, *args, **kwargs):
        return self._wrap(self._data.shift(*args, **kwargs))

    def diff(self, *args, **kwargs):
        return self._wrap(self._data.diff(*args, **kwargs))

    def astype(self, *args, **kwargs):
        return self._wrap(self._data.astype(*args, **kwargs))

    @property
    def index(self):
        return self._data.index

    def __getattr__(self, name):
        """
        Intercept attribute and method access to block unapproved pandas methods.
        
        Permits access to local private/protected members (starting with '_').
        Any other method or attribute access throws an AttributeError, directing
        the user to utilize FeatureEngine or OperatorEngine wrappers.

        Parameters
        ----------
        name : str
            The accessed attribute or method name.

        Raises
        ------
        AttributeError
            Always raised for non-private, non-whitelisted attributes.
        """
        # Allow access to protected/private members locally
        if name.startswith('_'):
            return self.__dict__[name]

        # Block any other method call (this throws Error 10 & 11)
        logger.error(f"XNO Sandbox Block: attempt to access pandas attribute/method '{name}'")
        raise AttributeError(
            f"XNO Sandbox Error: pandas Series attribute/method '{name}' is not allowed in __algorithm__. "
            f"Use self.feat or self.op wrappers instead."
        )

    def __getitem__(self, key):
        """
        Intercept indexing to block direct element/bar access.

        Raises
        ------
        TypeError
            Always raised to prohibit physical indexing (e.g., series[idx]).
        """
        logger.error(f"XNO Sandbox Block: attempt to use physical indexing with key '{key}'")
        raise TypeError("XNO Sandbox Error: Physical indexing (e.g. series[idx]) is not allowed. Use boolean masks and numpy where/ffill logic.")

    # --- Operator Overloading ---
    def _wrap(self, result):
        if isinstance(result, pd.Series):
            return RestrictedSeries(result)
        return result

    def _unwrap(self, other):
        if isinstance(other, RestrictedSeries):
            return other._data
        return other

    def __add__(self, other): return self._wrap(self._data + self._unwrap(other))
    def __radd__(self, other): return self._wrap(self._unwrap(other) + self._data)
    
    def __sub__(self, other): return self._wrap(self._data - self._unwrap(other))
    def __rsub__(self, other): return self._wrap(self._unwrap(other) - self._data)
    
    def __mul__(self, other): return self._wrap(self._data * self._unwrap(other))
    def __rmul__(self, other): return self._wrap(self._unwrap(other) * self._data)
    
    def __truediv__(self, other): return self._wrap(self._data / self._unwrap(other))
    def __rtruediv__(self, other): return self._wrap(self._unwrap(other) / self._data)
    
    def __pow__(self, other): return self._wrap(self._data ** self._unwrap(other))
    def __rpow__(self, other): return self._wrap(self._unwrap(other) ** self._data)

    # Boolean operators
    def __gt__(self, other): return self._wrap(self._data > self._unwrap(other))
    def __lt__(self, other): return self._wrap(self._data < self._unwrap(other))
    def __ge__(self, other): return self._wrap(self._data >= self._unwrap(other))
    def __le__(self, other): return self._wrap(self._data <= self._unwrap(other))
    def __eq__(self, other): return self._wrap(self._data == self._unwrap(other))
    def __ne__(self, other): return self._wrap(self._data != self._unwrap(other))
    
    def __and__(self, other): return self._wrap(self._data & self._unwrap(other))
    def __rand__(self, other): return self._wrap(self._unwrap(other) & self._data)
    
    def __or__(self, other): return self._wrap(self._data | self._unwrap(other))
    def __ror__(self, other): return self._wrap(self._unwrap(other) | self._data)
    
    def __invert__(self): return self._wrap(~self._data)
    
    # Mathematical
    def __abs__(self): return self._wrap(abs(self._data))
    def __neg__(self): return self._wrap(-self._data)
    def __pos__(self): return self._wrap(+self._data)

    def copy(self):
        return RestrictedSeries(self._data.copy())

    def __repr__(self):
        return "RestrictedSeries: \n" + repr(self._data)
