## 1. Wording correction

- [x] 1.1 Make the ctypes attempts version-precise. Evidence: `BoundaryTest` passes on Python 3.12.13 and 3.14.4. The pre-resolved call is refused on 3.14 and the new lookup is refused on both, while the unguarded control reaches the listener by every path on both.
- [x] 1.2 Narrow the spec and the development guide to that behavior, and rerun the Python and workflow checks.
