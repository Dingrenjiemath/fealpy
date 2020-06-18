"""
Notes
-----

References
[1] https://github.com/maciejkula/dynarray.git
"""
import numpy as np

class DynamicArray(object):
    MAGIC_METHODS = ('__radd__',
                     '__add__',
                     '__sub__',
                     '__rsub__',
                     '__mul__',
                     '__rmul__',
                     '__div__',
                     '__rdiv__',
                     '__pow__',
                     '__rpow__',
                     '__eq__',
                     '__len__')

    class __metaclass__(type):
        def __init__(cls, name, parents, attrs):
            def make_delegate(name):
                def delegate(self, *args, **kwargs):
                    return getattr(self.data[:self.size], name)
                return delegate
            type.__init__(cls, name, parents, attrs)
            for method_name in cls.MAGIC_METHODS:
                setattr(cls, method_name, property(make_delegate(method_name)))

    def __init__(self, data, dtype=None, capacity=1000):

        if isinstance(data, int): 
            self.shape = (data, )
            self.dtype = dtype or np.int_
            self.size = data 
            self.capacity = max(self.size, capacity)
            self.ndim = len(self.shape)
            self.data = np.empty((self.capacity,) + self._get_trailing_dimensions(),
                                  dtype=self.dtype)
        elif isinstance(data, tuple):
            self.shape = data 
            self.dtype = dtype or np.int_
            self.size = data[0] 
            self.capacity = max(self.size, capacity)
            self.ndim = len(self.shape)
            self.data = np.empty((self.capacity,) + self._get_trailing_dimensions(),
                                  dtype=self.dtype)
        elif isinstance(data, list):
            self.shape = (len(data), len(data[0])) if hasattr(data[0], '__len__') else (len(data), )
            self.dtype = dtype or np.int_
            self.size = len(data) 
            self.capacity = max(self.size, capacity)
            self.ndim = len(self.shape)
            self.data = np.empty((self.capacity,) + self._get_trailing_dimensions(),
                                  dtype=self.dtype)
            self.data[:self.size] = data

        elif isinstance(data, np.ndarray):
            self.shape = data.shape
            self.dtype = dtype or data.dtype
            self.size = self.shape[0]
            self.capacity = max(self.size, capacity)
            self.ndim = len(self.shape)
            self.data = np.empty((self.capacity,) + self._get_trailing_dimensions(),
                                  dtype=self.dtype)
            self.data[:self.size] = data

    def _get_trailing_dimensions(self):
        return self.shape[1:]

    def __getitem__(self, idx):
        return self.data[:self.size][idx]

    def __setitem__(self, idx, value):
        self.data[:self.size][idx] = value

    def resize(self, new_size):
        self.data = np.resize(self.data, (new_size,) + self._get_trailing_dimensions())
        self.capacity = new_size

    def _as_dtype(self, value):
        if hasattr(value, 'dtype') and value.dtype == self.dtype:
            return value
        else:
            return np.array(value, dtype=self.dtype)

    def increase_size(self, s):
        """

        Notes
        -----
            增加存储, 并返回增加部分的数组, 这里返回的是数组的视图.
        """
        required_size = self.size + s 
        if required_size >= self.capacity:
            self.resize(max(2*self.capacity, required_size))

        data = self.data[self.size:required_size]
        self.size = required_size
        return data 

    def decrease_size(self, s):
        """

        Notes
        -----
            减少存储, 并返回减少部分的数组, 这里返回的是数组的视图.
            TODO: 引入缩减内存的机制.
        """
        assert s <= self.size
        required_size = self.size - s
        data = self.data[required_size:self.size]
        self.size = required_size
        return data

    def extend(self, values):
        """

        Notes
        -----
        """
        values = self._as_dtype(values)

        required_size = self.size + values.shape[0]

        if required_size >= self.capacity:
            self.resize(max(2*self.capacity, required_size))

        self.data[self.size:required_size] = values
        self.size = required_size

    def shrink(self):
        """
        Reduce the array's capacity to its size.
        """
        self.resize(self.size)

    def __len__(self):
        return self.shape[0]

    def __repr__(self):
        return (self.data[:self.size].__repr__()
                .replace('array',
                         'DynamicArray(size={}, capacity={})'
                         .format(self.size, self.capacity)))