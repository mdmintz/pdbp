# ``pdbp`` (Pdb+)

[pdbp (Pdb+)](https://github.com/mdmintz/pdbp) is a drop-in replacement for ``pdb`` and (unmaintained) [pdbpp (Pdb++)](https://github.com/pdbpp/pdbpp).

This fixes ``pdbpp`` (pdb++) to work in all environments. Sticky ``pdbpp`` mode is the default option.

To replace ``pdb`` with it, add ``import pdbp`` to an ``__init__.py`` file. In case that doesn't work, you can just load all of ``pdbp`` into ``pdb``:

```python
import pdb
import pdbp
for key in pdbp.__dict__.keys():
    pdb.__dict__[key] = pdbp.__dict__[key]
```

If you need to customize ``pdbp`` options:

```python
if hasattr(pdb, "DefaultConfig"):
    pdb.DefaultConfig.filename_color = pdb.Color.blue
    pdb.DefaultConfig.line_number_color = pdb.Color.turquoise
    pdb.DefaultConfig.show_hidden_frames_count = False
    pdb.DefaultConfig.disable_pytest_capturing = True
    pdb.DefaultConfig.enable_hidden_frames = False
    pdb.DefaultConfig.truncate_long_lines = True
    pdb.DefaultConfig.sticky_by_default = True
```
