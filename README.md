# pdbp (Pdb+) [![](https://img.shields.io/pypi/v/pdbp.svg)](https://pypi.python.org/pypi/pdbp)

<img width="600" alt="Pdb+ Advanced Python Console Debugger" src="https://user-images.githubusercontent.com/6788579/207774790-fb63af65-5f98-4d92-afe3-12c2733d4db6.png">

--------

**[pdbp (Pdb+)](https://github.com/mdmintz/pdbp)** is an advanced console debugger for Python. It can be used as a drop-in replacement for ``pdb`` and [pdbpp](https://github.com/pdbpp/pdbpp).

<p><b>pdbp (Pdb+)</b> makes Python debugging a lot easier (and more fun!)</p>

--------

<img width="600" alt="Pdb+" src="https://user-images.githubusercontent.com/6788579/204408641-9c221bb6-578b-4b0f-807b-8454844e42e8.png">


## Installation & Usage:

```bash
pip install pdbp
```

Then add ``import pdbp`` to an ``__init__.py`` of your project, which will automatically make **``Pdb+``** the default debugger at breakpoints:

```python
import pdbp
```

(If using ``flake8`` for code-linting, you may want to add ``# noqa`` to that line):

```python
import pdbp  # noqa
```

To trigger a breakpoint in your code with ``pytest``, add ``--trace`` (to start tests with a breakpoint) or ``--pdb`` (to trigger a breakpoint if a test fails).

Basic **``Pdb+``** console commands: ``n``, ``c``, ``s`` => ``next``, ``continue``, ``step``.

(To learn more **Pdb+** console commands, type ``help`` in the **Pdb+** console and press ``Enter/Return``.)

--------

**``pdbp`` (Pdb+)** makes improvements to ``pdbpp`` so that it works in all environments. It also includes other bug-fixes. "Sticky" mode is the default option, which shows multiple lines of code while letting you see where you're going (while typing ``n`` + ``Enter``).

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


### pdbp (Pdb+) commands:

<img width="550" alt="Pdb+ Commands" src="https://user-images.githubusercontent.com/6788579/204386211-5fc44f73-e29f-4e87-b0ca-bb8ea69217af.png">


### Sticky Mode vs Non-Sticky Mode:

The default mode (``sticky``) lets you see a lot more lines of code from the debugger when active. In Non-Sticky mode, only one line of code is shown at a time. You can switch between the two modes by typing ``sticky`` in the **Pdb+** console prompt and pressing ``Enter/Return``.

> **Sticky Mode:**

<img width="550" alt="Pdb+ Stick Mode" src="https://user-images.githubusercontent.com/6788579/204890148-53d2567b-9a56-4243-a7d7-66100a284312.png">

> **Non-Sticky Mode:**

<img width="550" alt="Pdb+ Non-Sticky Mode" src="https://user-images.githubusercontent.com/6788579/204890164-8465bc22-0f20-43f1-8ab7-b4316718a4c6.png">


### More examples:

**``Pdb+``** is used by packages such as **``seleniumbase``**:

* https://pypi.org/project/seleniumbase/
* https://github.com/seleniumbase/SeleniumBase

--------

<img width="550" alt="Pdb+ Advanced Python Console Debugger" src="https://user-images.githubusercontent.com/6788579/204896775-38d8551b-1d3c-4e95-9f5c-0e03c9de13da.png">

--------

<img width="550" alt="Pdb+" src="https://user-images.githubusercontent.com/6788579/204359676-137cf541-12ef-469a-9d29-99709608ede0.png">

--------

(**Pdb+** is maintained by the [SeleniumBase Dev Team](https://github.com/seleniumbase/SeleniumBase))
