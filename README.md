# pdbp (Pdb+) [![](https://img.shields.io/pypi/v/pdbp.svg)](https://pypi.python.org/pypi/pdbp)

<img width="550" alt="Pdb+" src="https://user-images.githubusercontent.com/6788579/204408641-9c221bb6-578b-4b0f-807b-8454844e42e8.png">

**[pdbp (Pdb+)](https://github.com/mdmintz/pdbp)** is a drop-in replacement for ``pdb`` that improves on the (unmaintained) [pdbpp (Pdb++)](https://github.com/pdbpp/pdbpp) package.

**pdbp (Pdb+)** makes Python debugging easier (and a lot more fun).

## Installation & Usage:

```bash
pip install pdbp
```

Then add ``import pdbp`` to an ``__init__.py`` of your project, which will automatically make **``Pdb+``** the default debugger at breakpoints:

```python
import pdbp
```

If using ``flake8`` for code-linting, you may want to add ``# noqa`` to that line:

```python
import pdbp  # noqa
```

To trigger a breakpoint in your code with ``pytest``, add ``--trace`` (to start tests with a breakpoint) or ``--pdb`` (to trigger a breakpoint if a test fails).

**``pdbp`` (Pdb+)** fixes ``pdbpp`` (pdb++) so that it works in all environments. It also includes other bug-fixes. "Sticky" mode is the default option, which shows multiple lines of code while letting you see where you're going (``n`` + ``Enter``).

If you somehow reset ``pdb`` to Python's built-in version, you can always replace ``pdb`` with **``pdbp``** again as the default debugger by running this:

```python
import pdb
import pdbp
for key in pdbp.__dict__.keys():
    pdb.__dict__[key] = pdbp.__dict__[key]
```

Here's how to customize **``pdbp``**/``pdb`` options if you don't like the default settings: (<i>Shown below are the default settings.</i>)

```python
import pdb
if hasattr(pdb, "DefaultConfig"):
    pdb.DefaultConfig.filename_color = pdb.Color.blue
    pdb.DefaultConfig.line_number_color = pdb.Color.turquoise
    pdb.DefaultConfig.show_hidden_frames_count = False
    pdb.DefaultConfig.disable_pytest_capturing = True
    pdb.DefaultConfig.enable_hidden_frames = False
    pdb.DefaultConfig.truncate_long_lines = True
    pdb.DefaultConfig.sticky_by_default = True
```

You can also trigger **``Pdb+``** activation like this:

```python
import pdbp
pdbp.set_trace()
```

### pdbp (Pdb+) commands

<img width="550" alt="Pdb+ Commands" src="https://user-images.githubusercontent.com/6788579/204386211-5fc44f73-e29f-4e87-b0ca-bb8ea69217af.png">

### More examples:

**``Pdb+``** is used by packages such as **``seleniumbase``**:

* https://pypi.org/project/seleniumbase/
* https://github.com/seleniumbase/SeleniumBase

--------

<img width="550" alt="Pdb+" src="https://user-images.githubusercontent.com/6788579/204359676-137cf541-12ef-469a-9d29-99709608ede0.png">

--------

(**Pdb+** is maintained by the [SeleniumBase Dev Team](https://github.com/seleniumbase/SeleniumBase))