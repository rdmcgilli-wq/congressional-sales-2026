"""Raw data adapters. Every adapter returns a typed polars DataFrame and
writes through storage.write() -- never touches the warehouse directly
from outside this package."""
