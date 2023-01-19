"""
pdbp (Pdb+): A drop-in replacement for pdb and pdbpp.
=====================================================
"""
from __future__ import print_function
import code
import codecs
import inspect
import os.path
import pprint
import re
import signal
import subprocess
import sys
import traceback
import types
from collections import OrderedDict
from tabcompleter import Completer, ConfigurableClass, Color
import tabcompleter

__url__ = "https://github.com/mdmintz/pdbp"
__version__ = tabcompleter.LazyVersion("pdbp")

try:
    from inspect import signature  # Python >= 3.3
except ImportError:
    try:
        from funcsigs import signature
    except ImportError:
        def signature(obj):
            return " [pip install funcsigs to show the signature]"

# Digits, Letters, [], or Dots
side_effects_free = re.compile(r"^ *[_0-9a-zA-Z\[\].]* *$")

if sys.version_info < (3, ):
    from io import BytesIO as StringIO
else:
    from io import StringIO


def import_from_stdlib(name):
    result = types.ModuleType(name)
    stdlibdir, _ = os.path.split(code.__file__)
    pyfile = os.path.join(stdlibdir, name + ".py")
    with open(pyfile) as f:
        src = f.read()
    co_module = compile(src, pyfile, "exec", dont_inherit=True)
    exec(co_module, result.__dict__)
    return result


pdb = import_from_stdlib("pdb")


def rebind_globals(func, newglobals):
    newfunc = types.FunctionType(func.__code__, newglobals, func.__name__,
                                 func.__defaults__, func.__closure__)
    return newfunc


def is_char_wide(char):
    # Returns True if the char is Chinese, Japanese, Korean, or another double.
    if sys.version_info < (3, ):
        return False  # Python 2.7 can't handle that
    special_c_r = [
        {"from": ord("\u4e00"), "to": ord("\u9FFF")},
        {"from": ord("\u3040"), "to": ord("\u30ff")},
        {"from": ord("\uac00"), "to": ord("\ud7a3")},
        {"from": ord("\uff01"), "to": ord("\uff60")},
    ]
    sc = any(
        [range["from"] <= ord(char) <= range["to"] for range in special_c_r]
    )
    return sc


def get_width(line):
    # Return the true width of the line. Not the same as line length.
    # Chinese/Japanese/Korean characters take up two spaces of width.
    line_length = len(line)
    for char in line:
        if is_char_wide(char):
            line_length += 1
    return line_length


def set_line_width(line, width):
    """Trim line if too long. Fill line if too short. Return line."""
    line_width = get_width(line)
    new_line = ""
    width = int(width)
    if width <= 0:
        return new_line
    elif line_width == width:
        return line
    elif line_width < width:
        new_line = line
    else:
        for char in line:
            updated_line = "%s%s" % (new_line, char)
            if get_width(updated_line) > width:
                break
            new_line = updated_line
    extra_spaces = " " * (width - get_width(new_line))
    return "%s%s" % (new_line, extra_spaces)


class DefaultConfig(object):
    prompt = "(Pdb+) "
    highlight = True
    sticky_by_default = True
    bg = "dark"
    use_pygments = True
    colorscheme = None
    use_terminal256formatter = None  # Defaults to `"256color" in $TERM`.
    editor = "${EDITOR:-vi}"  # Use $EDITOR if set; else default to vi.
    stdin_paste = None
    exec_if_unfocused = None  # This option was removed!
    truncate_long_lines = True
    disable_pytest_capturing = True
    enable_hidden_frames = False
    show_hidden_frames_count = False
    encodings = ("utf-8", "latin-1")
    filename_color = Color.fuchsia
    line_number_color = Color.turquoise
    regular_stack_color = Color.yellow
    pm_stack_color = Color.red
    stack_color = regular_stack_color
    # https://en.wikipedia.org/wiki/ANSI_escape_code#3-bit_and_4-bit
    return_value_color = "90;1"  # Gray
    pm_return_value_color = "31;1"  # Red (Post Mortem failure)
    num_return_value_color = "95;1"  # Bright Magenta (numbers)
    true_return_value_color = "32;1"  # Green
    false_return_value_color = "33;1"  # Yellow (red was taken)
    none_return_value_color = "33;1"  # Yellow (same as False)
    regular_line_color = "97;44;1"  # White on Blue (Old: "39;49;7")
    pm_cur_line_color = "97;41;1"  # White on Red (Post Mortem Color)
    exc_line_color = "31;103;1"  # Red on Yellow (Exception-handling)
    current_line_color = regular_line_color
    exception_caught = False
    last_return_color = None
    show_traceback_on_error = True
    show_traceback_on_error_limit = None
    default_pdb_kwargs = {
    }

    def setup(self, pdb):
        pass

    def before_interaction_hook(self, pdb):
        pass


def setbgcolor(line, color):
    # Add a bgcolor attribute to all escape sequences found.
    setbg = "\x1b[%sm" % color
    regexbg = "\\1;%sm" % color
    result = setbg + re.sub("(\x1b\\[.*?)m", regexbg, line) + "\x1b[00m"
    if os.environ.get("TERM") == "eterm-color":
        result = result.replace(setbg, "\x1b[37;%dm" % color)
        result = result.replace("\x1b[00;%dm" % color, "\x1b[37;%dm" % color)
        result = result.replace("\x1b[39;49;00;", "\x1b[37;")
    return result


CLEARSCREEN = "\033[2J\033[1;1H"


def lasti2lineno(code, lasti):
    import dis
    linestarts = list(dis.findlinestarts(code))
    linestarts.reverse()
    for i, lineno in linestarts:
        if lasti >= i:
            return lineno
    return 0


class Undefined:
    def __repr__(self):
        return "<undefined>"


undefined = Undefined()


class Pdb(pdb.Pdb, ConfigurableClass, object):
    DefaultConfig = DefaultConfig
    config_filename = ".pdbrc.py"

    def __init__(self, *args, **kwds):
        self.ConfigFactory = kwds.pop("Config", None)
        self.start_lineno = kwds.pop("start_lineno", None)
        self.start_filename = kwds.pop("start_filename", None)
        self.config = self.get_config(self.ConfigFactory)
        self.config.setup(self)
        if self.config.disable_pytest_capturing:
            self._disable_pytest_capture_maybe()
        kwargs = self.config.default_pdb_kwargs.copy()
        kwargs.update(**kwds)
        super(Pdb, self).__init__(*args, **kwargs)
        self.prompt = self.config.prompt
        self.display_list = {}  # frame --> (name --> last seen value)
        self.sticky = self.config.sticky_by_default
        self.first_time_sticky = self.sticky
        self.ok_to_clear = False
        self.has_traceback = False
        self.sticky_ranges = {}  # frame --> (start, end)
        self.tb_lineno = {}  # frame --> lineno where the exception was raised
        self.history = []
        self.show_hidden_frames = False
        self._hidden_frames = []
        self.stdout = self.ensure_file_can_write_unicode(self.stdout)

    def ensure_file_can_write_unicode(self, f):
        # Wrap with an encoder, but only if not already wrapped.
        if (not hasattr(f, "stream")
                and getattr(f, "encoding", False)
                and f.encoding.lower() != "utf-8"):
            f = codecs.getwriter("utf-8")(getattr(f, "buffer", f))

        return f

    def _disable_pytest_capture_maybe(self):
        try:
            import py.test
            # Force raising of ImportError if pytest is not installed.
            py.test.config
        except (ImportError, AttributeError):
            return
        try:
            capman = py.test.config.pluginmanager.getplugin("capturemanager")
            capman.suspendcapture()
        except KeyError:
            pass
        except AttributeError:
            pass

    def interaction(self, frame, traceback):
        # Restore the previous signal handler at the Pdb+ prompt.
        if getattr(pdb.Pdb, "_previous_sigint_handler", None):
            try:
                signal.signal(signal.SIGINT, pdb.Pdb._previous_sigint_handler)
            except ValueError:  # ValueError: signal only works in main thread
                pass
            else:
                pdb.Pdb._previous_sigint_handler = None
        ret = self.setup(frame, traceback)
        if ret:
            self.forget()
            return
        if self.config.exec_if_unfocused:
            pass  # This option was removed!
        if (
            self.has_traceback
            and not traceback
            and self.config.exception_caught
        ):
            # The exception was caught, so no post mortem debug mode.
            self.has_traceback = False
            self.config.stack_color = self.config.regular_stack_color
            self.config.current_line_color = self.config.regular_line_color
        if traceback or not self.sticky or self.first_time_sticky:
            if traceback:
                self.has_traceback = True
                self.config.stack_color = self.config.pm_stack_color
                self.config.current_line_color = self.config.pm_cur_line_color
            if not self.sticky:
                print(file=self.stdout)
            if not self.first_time_sticky:
                self.print_stack_entry(self.stack[self.curindex])
                self.print_hidden_frames_count()
            if self.sticky:
                if not traceback:
                    self.stdout.write(CLEARSCREEN)
            else:
                print(file=self.stdout, end="\n\033[F")
        completer = tabcompleter.setup()
        completer.config.readline.set_completer(self.complete)
        self.config.before_interaction_hook(self)
        # Use _cmdloop on Python3, which catches KeyboardInterrupt.
        if hasattr(self, "_cmdloop"):
            self._cmdloop()
        else:
            self.cmdloop()
        self.forget()

    def print_hidden_frames_count(self):
        n = len(self._hidden_frames)
        if n and self.config.show_hidden_frames_count:
            plural = n > 1 and "s" or ""
            print(
                '   %d frame%s hidden (Use "u" and "d" to travel)'
                % (n, plural),
                file=self.stdout,
            )

    def setup(self, frame, tb):
        ret = super(Pdb, self).setup(frame, tb)
        if not ret:
            while tb:
                lineno = lasti2lineno(tb.tb_frame.f_code, tb.tb_lasti)
                self.tb_lineno[tb.tb_frame] = lineno
                tb = tb.tb_next
        return ret

    def _is_hidden(self, frame):
        if not self.config.enable_hidden_frames:
            return False
        # Decorated code is always considered to be hidden.
        consts = frame.f_code.co_consts
        if consts and consts[-1] is _HIDE_FRAME:
            return True
        # Don't hide if this frame contains the initial set_trace.
        if frame is getattr(self, "_via_set_trace_frame", None):
            return False
        if frame.f_globals.get("__unittest"):
            return True
        if (
            frame.f_locals.get("__tracebackhide__")
            or frame.f_globals.get("__tracebackhide__")
        ):
            return True

    def get_stack(self, f, t):
        # Show all the frames except ones that should be hidden.
        fullstack, idx = super(Pdb, self).get_stack(f, t)
        self.fullstack = fullstack
        return self.compute_stack(fullstack, idx)

    def compute_stack(self, fullstack, idx=None):
        if idx is None:
            idx = len(fullstack) - 1
        if self.show_hidden_frames:
            return fullstack, idx
        self._hidden_frames = []
        newstack = []
        for frame, lineno in fullstack:
            if self._is_hidden(frame):
                self._hidden_frames.append((frame, lineno))
            else:
                newstack.append((frame, lineno))
        newidx = idx - len(self._hidden_frames)
        return newstack, newidx

    def refresh_stack(self):
        self.stack, _ = self.compute_stack(self.fullstack)
        # Find the current frame in the new stack.
        for i, (frame, _) in enumerate(self.stack):
            if frame is self.curframe:
                self.curindex = i
                break
        else:
            self.curindex = len(self.stack) - 1
            self.curframe = self.stack[-1][0]
            self.print_current_stack_entry()

    def forget(self):
        if not hasattr(self, "lineno"):
            # Only forget if not used with recursive set_trace.
            super(Pdb, self).forget()
        self.raise_lineno = {}

    @classmethod
    def _get_all_completions(cls, complete, text):
        r = []
        i = 0
        while True:
            comp = complete(text, i)
            if comp is None:
                break
            i += 1
            r.append(comp)
        return r

    def complete(self, text, state):
        """Handle completions from tabcompleter and the original pdb."""
        if state == 0:
            if GLOBAL_PDB:
                GLOBAL_PDB._pdbp_completing = True
            mydict = self.curframe.f_globals.copy()
            mydict.update(self.curframe.f_locals)
            completer = Completer(mydict)
            self._completions = self._get_all_completions(
                completer.complete, text
            )
            real_pdb = super(Pdb, self)
            for x in self._get_all_completions(real_pdb.complete, text):
                if x not in self._completions:
                    self._completions.append(x)
            if GLOBAL_PDB:
                del GLOBAL_PDB._pdbp_completing
            # Remove "\t" from tabcompleter if there are pdb completions.
            if len(self._completions) > 1 and self._completions[0] == "\t":
                self._completions.pop(0)
        try:
            return self._completions[state]
        except IndexError:
            return None

    def _init_pygments(self):
        if not self.config.use_pygments:
            return False
        if hasattr(self, "_fmt"):
            return True
        try:
            from pygments.lexers import PythonLexer
            from pygments.formatters import TerminalFormatter
            from pygments.formatters import Terminal256Formatter
        except ImportError:
            return False
        if hasattr(self.config, "formatter"):
            self._fmt = self.config.formatter
        else:
            if (self.config.use_terminal256formatter
                    or (self.config.use_terminal256formatter is None
                        and "256color" in os.environ.get("TERM", ""))):
                Formatter = Terminal256Formatter
            else:
                Formatter = TerminalFormatter
            self._fmt = Formatter(bg=self.config.bg,
                                  colorscheme=self.config.colorscheme)
        self._lexer = PythonLexer()
        return True

    stack_entry_regexp = re.compile(r"(.*?)\(([0-9]+?)\)(.*)", re.DOTALL)

    def format_stack_entry(self, frame_lineno, lprefix=": "):
        entry = super(Pdb, self).format_stack_entry(frame_lineno, lprefix)
        entry = self.try_to_decode(entry)
        if self.config.highlight:
            match = self.stack_entry_regexp.match(entry)
            if match:
                filename, lineno, other = match.groups()
                filename = Color.set(self.config.filename_color, filename)
                lineno = Color.set(self.config.line_number_color, lineno)
                entry = "%s(%s)%s" % (filename, lineno, other)
        return entry

    def try_to_decode(self, s):
        for encoding in self.config.encodings:
            try:
                return s.decode(encoding)
            except (UnicodeDecodeError, AttributeError):
                pass
        return s

    def format_source(self, src):
        if not self._init_pygments():
            return src
        from pygments import highlight
        src = self.try_to_decode(src)
        return highlight(src, self._lexer, self._fmt)

    def format_line(self, lineno, marker, line):
        lineno = "%4d" % lineno
        if self.config.highlight:
            lineno = Color.set(self.config.line_number_color, lineno)
        line = "%s  %2s %s" % (lineno, marker, line)
        if self.config.highlight and marker == "->":
            if self.config.current_line_color:
                line = setbgcolor(line, self.config.current_line_color)
        elif self.config.highlight and marker == ">>":
            if self.config.exc_line_color:
                line = setbgcolor(line, self.config.exc_line_color)
        return line

    def parseline(self, line):
        if line.startswith("!!"):
            line = line[2:]
            return super(Pdb, self).parseline(line)
        cmd, arg, newline = super(Pdb, self).parseline(line)
        if arg and arg.endswith("?"):
            if hasattr(self, "do_" + cmd):
                cmd, arg = ("help", cmd)
            elif arg.endswith("??"):
                arg = cmd + arg.split("?")[0]
                cmd = "source"
                self.do_inspect(arg)
                self.stdout.write("%-28s\n" % Color.set(Color.red, "Source:"))
            else:
                arg = cmd + arg.split("?")[0]
                cmd = "inspect"
                return cmd, arg, newline
        if (
            cmd == "f"
            and len(newline) > 1
            and (newline[1] == "'" or newline[1] == '"')
        ):
            return super(Pdb, self).parseline("!" + line)

        if (
            cmd
            and hasattr(self, "do_" + cmd)
            and (
                cmd in self.curframe.f_globals
                or cmd in self.curframe.f_locals
                or arg.startswith("=")
            )
        ):
            return super(Pdb, self).parseline("!" + line)

        if cmd == "list" and arg.startswith("("):
            line = "!" + line
            return super(Pdb, self).parseline(line)

        return cmd, arg, newline

    def do_inspect(self, arg):
        obj = self._getval(arg)
        data = OrderedDict()
        data["Type"] = type(obj).__name__
        data["String Form"] = str(obj).strip()
        try:
            data["Length"] = len(obj)
        except TypeError:
            pass
        try:
            data["File"] = inspect.getabsfile(obj)
        except TypeError:
            pass
        if (isinstance(obj, type)
                and hasattr(obj, "__init__")
                and getattr(obj, "__module__") != "__builtin__"):
            data["Docstring"] = obj.__doc__
            data["Constructor information"] = ""
            try:
                data[" Definition"] = "%s%s" % (arg, signature(obj))
            except ValueError:
                pass
            data[" Docstring"] = obj.__init__.__doc__
        else:
            try:
                data["Definition"] = "%s%s" % (arg, signature(obj))
            except (TypeError, ValueError):
                pass
            data["Docstring"] = obj.__doc__
        for key, value in data.items():
            formatted_key = Color.set(Color.red, key + ":")
            self.stdout.write("%-28s %s\n" % (formatted_key, value))

    def default(self, line):
        self.history.append(line)
        return super(Pdb, self).default(line)

    def do_help(self, arg):
        try:
            return super(Pdb, self).do_help(arg)
        except AttributeError:
            print("*** No help for '{command}'".format(command=arg),
                  file=self.stdout)
    do_help.__doc__ = pdb.Pdb.do_help.__doc__

    def help_hidden_frames(self):
        print('Use "u" and "d" to travel through the stack.', file=self.stdout)

    def do_hf_unhide(self, arg):
        self.show_hidden_frames = True
        self.refresh_stack()

    def do_hf_hide(self, arg):
        self.show_hidden_frames = False
        self.refresh_stack()

    def do_hf_list(self, arg):
        for frame_lineno in self._hidden_frames:
            print(self.format_stack_entry(frame_lineno, pdb.line_prefix),
                  file=self.stdout)

    def do_longlist(self, arg):
        self.lastcmd = "longlist"
        self._printlonglist()

    def _printlonglist(self, linerange=None, fnln=None):
        try:
            if self.curframe.f_code.co_name == "<module>":
                lines, _ = inspect.findsource(self.curframe)
                lineno = 1
            else:
                try:
                    lines, lineno = inspect.getsourcelines(self.curframe)
                except Exception:
                    print(file=self.stdout)
                    self.sticky = False
                    self.print_stack_entry(self.stack[self.curindex])
                    self.sticky = True
                    print(file=self.stdout, end="\n\033[F")
                    return
        except IOError as e:
            print("** Error: %s **" % e, file=self.stdout)
            return
        if linerange:
            start, end = linerange
            start = max(start, lineno)
            end = min(end, lineno + len(lines))
            lines = lines[start - lineno:end - lineno]
            lineno = start
        self._print_lines_pdbp(lines, lineno, fnln=fnln)

    def _print_lines_pdbp(self, lines, lineno, print_markers=True, fnln=None):
        dots = "..."
        offset = 0
        try:
            lineno_int = int(lineno)
        except Exception:
            lineno = 1
            lineno_int = 1
        if lineno_int == 1:
            dots = ""
        elif lineno_int > 99999:
            dots = "......"
        elif lineno_int > 9999:
            dots = "....."
        elif lineno_int > 999:
            dots = "...."
        elif lineno_int > 99:
            dots = " ..."
        elif lineno_int > 9:
            dots = "  .."
        else:
            dots = "   ."
        max_line = int(lineno) + len(lines) - 1
        if max_line > 9999:
            offset = 1
        if max_line > 99999:
            offset = 2
        exc_lineno = self.tb_lineno.get(self.curframe, None)
        lines = [line[:-1] for line in lines]  # remove the trailing "\n"
        lines = [line.replace("\t", "    ")
                 for line in lines]  # force tabs to 4 spaces
        width, height = self.get_terminal_size()
        width = width - offset
        height = height - 1
        if self.config.truncate_long_lines:
            maxlength = max(width - 9, 16)
            lines = [set_line_width(line, maxlength) for line in lines]
        else:
            maxlength = max(map(len, lines))
        if self.config.highlight:
            # Fill line with spaces. This is important when a bg color is
            # is used for highlighting the current line (via setbgcolor).
            lines = [set_line_width(line, maxlength) for line in lines]
            src = self.format_source("\n".join(lines))
            lines = src.splitlines()
        if height >= 6:
            last_marker_line = max(
                self.curframe.f_lineno,
                exc_lineno if exc_lineno else 0
            ) - lineno
            if last_marker_line >= 0:
                maxlines = last_marker_line + height * 2 // 3
                if len(lines) > maxlines:
                    lines = lines[:maxlines]
                    lines.append(Color.set("39;49;1", "..."))
        self.config.exception_caught = False
        for i, line in enumerate(lines):
            marker = ""
            if lineno == self.curframe.f_lineno and print_markers:
                marker = "->"
            elif lineno == exc_lineno and print_markers:
                marker = ">>"
                self.config.exception_caught = True
            lines[i] = self.format_line(lineno, marker, line)
            lineno += 1
        if self.ok_to_clear:
            self.stdout.write(CLEARSCREEN)
        if fnln:
            print(fnln, file=self.stdout)
            if int(lineno) > 1:
                num_color = self.config.line_number_color
                print(Color.set(num_color, dots), file=self.stdout)
            else:
                print(file=self.stdout)
        print("\n".join(lines), file=self.stdout, end="\n\n\033[F")

    do_ll = do_longlist

    def do_list(self, arg):
        oldstdout = self.stdout
        self.stdout = StringIO()
        super(Pdb, self).do_list(arg)
        src = self.format_source(self.stdout.getvalue())
        self.stdout = oldstdout
        print(src, file=self.stdout, end="")

    do_list.__doc__ = pdb.Pdb.do_list.__doc__
    do_l = do_list

    def do_continue(self, arg):
        if arg != "":
            self.do_tbreak(arg)
        return super(Pdb, self).do_continue("")
    do_continue.__doc__ = pdb.Pdb.do_continue.__doc__
    do_c = do_cont = do_continue

    def do_pp(self, arg):
        width, height = self.get_terminal_size()
        try:
            pprint.pprint(self._getval(arg), self.stdout, width=width)
        except Exception:
            pass
    do_pp.__doc__ = pdb.Pdb.do_pp.__doc__

    def do_debug(self, arg):
        Config = self.ConfigFactory

        class PdbpWithConfig(self.__class__):
            def __init__(self_withcfg, *args, **kwargs):
                kwargs.setdefault("Config", Config)
                super(PdbpWithConfig, self_withcfg).__init__(*args, **kwargs)
                self_withcfg.use_rawinput = self.use_rawinput
        if sys.version_info < (3, ):
            do_debug_func = pdb.Pdb.do_debug.im_func
        else:
            do_debug_func = pdb.Pdb.do_debug
        newglobals = do_debug_func.__globals__.copy()
        newglobals["Pdb"] = PdbpWithConfig
        orig_do_debug = rebind_globals(do_debug_func, newglobals)
        try:
            return orig_do_debug(self, arg)
        except Exception:
            exc_info = sys.exc_info()[:2]
            msg = traceback.format_exception_only(*exc_info)[-1].strip()
            self.error(msg)

    do_debug.__doc__ = pdb.Pdb.do_debug.__doc__

    def do_interact(self, arg):
        ns = self.curframe.f_globals.copy()
        ns.update(self.curframe.f_locals)
        code.interact("*interactive*", local=ns)

    def do_track(self, arg):
        try:
            from rpython.translator.tool.reftracker import track
        except ImportError:
            print("** cannot import pypy.translator.tool.reftracker **",
                  file=self.stdout)
            return
        try:
            val = self._getval(arg)
        except Exception:
            pass
        else:
            track(val)

    def _get_display_list(self):
        return self.display_list.setdefault(self.curframe, {})

    def _getval_or_undefined(self, arg):
        try:
            return eval(arg, self.curframe.f_globals,
                        self.curframe.f_locals)
        except NameError:
            return undefined

    def do_display(self, arg):
        try:
            value = self._getval_or_undefined(arg)
        except Exception:
            return
        self._get_display_list()[arg] = value

    def do_undisplay(self, arg):
        try:
            del self._get_display_list()[arg]
        except KeyError:
            print("** %s not in the display list **" % arg, file=self.stdout)

    def __get_return_color(self, s):
        frame, lineno = self.stack[self.curindex]
        if self.has_traceback or "__exception__" in frame.f_locals:
            self.config.last_return_color = self.config.pm_return_value_color
            return self.config.last_return_color
        the_return_color = None
        return_value = s.strip().split("return ")[-1]
        if return_value == "None":
            the_return_color = self.config.none_return_value_color
        elif return_value == "True":
            the_return_color = self.config.true_return_value_color
        elif return_value in ["False", "", "[]", r"{}"]:
            the_return_color = self.config.false_return_value_color
        elif len(return_value) > 0 and return_value[0].isdecimal():
            the_return_color = self.config.num_return_value_color
        else:
            the_return_color = self.config.return_value_color
        self.config.last_return_color = the_return_color
        return self.config.last_return_color

    def _print_if_sticky(self):
        if self.sticky:
            if self.first_time_sticky:
                self.first_time_sticky = False
            self.ok_to_clear = True
            frame, lineno = self.stack[self.curindex]
            filename = self.canonic(frame.f_code.co_filename)
            lno = Color.set(self.config.line_number_color, "%r" % lineno)
            fname = Color.set(self.config.filename_color, filename)
            fnln = None
            if not self.curindex:
                self.curindex = 0
            colored_index = Color.set(self.config.stack_color, self.curindex)
            fnln = "[%s] > %s(%s)" % (colored_index, fname, lno)
            sticky_range = self.sticky_ranges.get(self.curframe, None)
            self._printlonglist(sticky_range, fnln=fnln)
            needs_extra_line = False
            if "__exception__" in frame.f_locals:
                s = self._format_exc_for_sticky(
                    frame.f_locals["__exception__"]
                )
                if s:
                    last_return_color = self.config.last_return_color
                    if (
                        last_return_color == self.config.pm_return_value_color
                        and not self.config.exception_caught
                    ):
                        print(s, file=self.stdout)
                    needs_extra_line = True
            if "__return__" in frame.f_locals:
                rv = frame.f_locals["__return__"]
                try:
                    s = repr(rv)
                except KeyboardInterrupt:
                    raise
                except Exception:
                    s = "(unprintable return value)"
                s = " return " + s
                if self.config.highlight:
                    if (
                        needs_extra_line
                        and frame.f_locals["__return__"] is None
                    ):
                        # There was an Exception. And returning None.
                        the_return_color = self.config.exc_line_color
                        s = s + " "
                    else:
                        the_return_color = self.__get_return_color(s)
                    s = Color.set(the_return_color, s)
                print(s, file=self.stdout)
                needs_extra_line = True
            if needs_extra_line:
                print(file=self.stdout, end="\n\033[F")

    def _format_exc_for_sticky(self, exc):
        if len(exc) != 2:
            return "pdbp: got unexpected __exception__: %r" % (exc,)
        exc_type, exc_value = exc
        s = ""
        try:
            try:
                s = exc_type.__name__
            except AttributeError:
                s = str(exc_type)
            if exc_value is not None:
                s += ": "
                s += str(exc_value)
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            try:
                s += "(unprintable exception: %r)" % (exc,)
            except Exception:
                s += "(unprintable exception)"
        if self.config.highlight:
            the_return_color = self.__get_return_color(s)
            s = Color.set(the_return_color, s)
        return s

    def do_sticky(self, arg):
        """Toggle sticky mode. Usage: sticky [start end]"""
        if arg:
            try:
                start, end = map(int, arg.split())
            except ValueError:
                print("** Error when parsing argument: %s **" % arg,
                      file=self.stdout)
                return
            self.sticky = True
            self.sticky_ranges[self.curframe] = start, end + 1
        else:
            self.sticky = not self.sticky
            self.sticky_range = None
        if self.sticky:
            self._print_if_sticky()
        else:
            print(file=self.stdout)
            self.print_stack_entry(self.stack[self.curindex])
            print(file=self.stdout, end="\n\033[F")

    def print_stack_trace(self):
        try:
            for frame_index, frame_lineno in enumerate(self.stack):
                self.print_stack_entry(frame_lineno, frame_index=frame_index)
        except KeyboardInterrupt:
            pass

    def print_stack_entry(
        self, frame_lineno, prompt_prefix=pdb.line_prefix, frame_index=None
    ):
        if self.sticky:
            return
        frame_index = frame_index if frame_index is not None else self.curindex
        frame, lineno = frame_lineno
        colored_index = Color.set(self.config.stack_color, frame_index)
        if frame is self.curframe:
            print("[%s] >" % colored_index, file=self.stdout, end=" ")
        else:
            print("[%s]  " % colored_index, file=self.stdout, end=" ")
        stack_entry = self.format_stack_entry(frame_lineno, prompt_prefix)
        print(stack_entry, file=self.stdout)
        if not self.sticky:
            print(file=self.stdout, end="\n\033[F")
            if (
                "\n-> except " in stack_entry or "\n-> except:" in stack_entry
            ):
                self.config.exception_caught = True

    def print_current_stack_entry(self):
        if self.sticky:
            self._print_if_sticky()
        else:
            print(file=self.stdout)
            self.print_stack_entry(self.stack[self.curindex])
            print(file=self.stdout, end="\n\033[F")

    def preloop(self):
        self._print_if_sticky()
        display_list = self._get_display_list()
        for expr, oldvalue in display_list.items():
            newvalue = self._getval_or_undefined(expr)
            if newvalue is not oldvalue or newvalue != oldvalue:
                display_list[expr] = newvalue
                print("%s: %r --> %r" % (expr, oldvalue, newvalue),
                      file=self.stdout)

    def _get_position_of_arg(self, arg):
        try:
            obj = self._getval(arg)
        except Exception:
            return None, None, None
        if isinstance(obj, str):
            return obj, 1, None
        try:
            filename = inspect.getabsfile(obj)
            lines, lineno = inspect.getsourcelines(obj)
        except (IOError, TypeError) as e:
            print("** Error: %s **" % e, file=self.stdout)
            return None, None, None
        return filename, lineno, lines

    def do_source(self, arg):
        _, lineno, lines = self._get_position_of_arg(arg)
        if lineno is None:
            return
        self._print_lines_pdbp(lines, lineno, print_markers=False)

    def do_frame(self, arg):
        try:
            arg = int(arg)
        except (ValueError, TypeError):
            print(
                '*** Expected a number, got "{0}"'.format(arg),
                file=self.stdout
            )
            return
        if arg < 0 or arg >= len(self.stack):
            print("*** Out of range", file=self.stdout)
        else:
            self.curindex = arg
            self.curframe = self.stack[self.curindex][0]
            self.curframe_locals = self.curframe.f_locals
            self.print_current_stack_entry()
            self.lineno = None
    do_f = do_frame

    def do_up(self, arg="1"):
        arg = "1" if arg == "" else arg
        try:
            arg = int(arg)
        except (ValueError, TypeError):
            print(
                '*** Expected a number, got "{0}"'.format(arg),
                file=self.stdout
            )
            return
        if self.curindex - arg < 0:
            print("*** Oldest frame", file=self.stdout)
        else:
            self.curindex = self.curindex - arg
            self.curframe = self.stack[self.curindex][0]
            self.curframe_locals = self.curframe.f_locals
            self.print_current_stack_entry()
            self.lineno = None
    do_up.__doc__ = pdb.Pdb.do_up.__doc__
    do_u = do_up

    def do_down(self, arg="1"):
        arg = "1" if arg == "" else arg
        try:
            arg = int(arg)
        except (ValueError, TypeError):
            print(
                '*** Expected a number, got "{0}"'.format(arg),
                file=self.stdout
            )
            return
        if self.curindex + arg >= len(self.stack):
            print("*** Newest frame", file=self.stdout)
        else:
            self.curindex = self.curindex + arg
            self.curframe = self.stack[self.curindex][0]
            self.curframe_locals = self.curframe.f_locals
            self.print_current_stack_entry()
            self.lineno = None
    do_down.__doc__ = pdb.Pdb.do_down.__doc__
    do_d = do_down

    @staticmethod
    def get_terminal_size():
        fallback = (80, 24)
        try:
            from shutil import get_terminal_size
        except ImportError:
            try:
                import termios
                import fcntl
                import struct
                call = fcntl.ioctl(0, termios.TIOCGWINSZ, "\x00" * 8)
                height, width = struct.unpack("hhhh", call)[:2]
            except (SystemExit, KeyboardInterrupt):
                raise
            except Exception:
                width = int(os.environ.get("COLUMNS", fallback[0]))
                height = int(os.environ.get("COLUMNS", fallback[1]))
            width = width if width != 0 else fallback[0]
            height = height if height != 0 else fallback[1]
            return width, height
        else:
            width, height = get_terminal_size(fallback)  # shutil
            return width, height

    def _open_editor(self, editor, lineno, filename):
        filename = filename.replace('"', '\\"')
        os.system('%s +%d "%s"' % (editor, lineno, filename))

    def _get_current_position(self):
        frame = self.curframe
        lineno = frame.f_lineno
        filename = os.path.abspath(frame.f_code.co_filename)
        return filename, lineno

    def do_edit(self, arg):
        "Open an editor visiting the current file at the current line"
        if arg == "":
            filename, lineno = self._get_current_position()
        else:
            filename, lineno, _ = self._get_position_of_arg(arg)
            if filename is None:
                return
        match = re.match(r".*<\d+-codegen (.*):(\d+)>", filename)
        if match:
            filename = match.group(1)
            lineno = int(match.group(2))
        editor = self.config.editor
        self._open_editor(editor, lineno, filename)

    do_ed = do_edit

    def _get_history(self):
        return [s for s in self.history if not side_effects_free.match(s)]

    def _get_history_text(self):
        import linecache
        line = linecache.getline(self.start_filename, self.start_lineno)
        nspaces = len(line) - len(line.lstrip())
        indent = " " * nspaces
        history = [indent + s for s in self._get_history()]
        return "\n".join(history) + "\n"

    def _open_stdin_paste(self, stdin_paste, lineno, filename, text):
        proc = subprocess.Popen([stdin_paste, "+%d" % lineno, filename],
                                stdin=subprocess.PIPE)
        proc.stdin.write(text)
        proc.stdin.close()

    def _put(self, text):
        stdin_paste = self.config.stdin_paste
        if stdin_paste is None:
            print('** Error: the "stdin_paste" option is not configured **',
                  file=self.stdout)
        filename = self.start_filename
        lineno = self.start_lineno
        self._open_stdin_paste(stdin_paste, lineno, filename, text)

    def do_put(self, arg):
        text = self._get_history_text()
        self._put(text)

    def do_paste(self, arg):
        arg = arg.strip()
        old_stdout = self.stdout
        self.stdout = StringIO()
        self.onecmd(arg)
        text = self.stdout.getvalue()
        self.stdout = old_stdout
        sys.stdout.write(text)
        self._put(text)

    def set_trace(self, frame=None):
        """Remember starting frame. Used with pytest."""
        if frame is None:
            frame = sys._getframe().f_back
        self._via_set_trace_frame = frame
        return super(Pdb, self).set_trace(frame)

    def is_skipped_module(self, module_name):
        if module_name is None:
            return False
        return super(Pdb, self).is_skipped_module(module_name)

    if not hasattr(pdb.Pdb, "message"):  # For py27.

        def message(self, msg):
            print(msg, file=self.stdout)

    def error(self, msg):
        """Override/enhance default error method to display tracebacks."""
        print("***", msg, file=self.stdout)

        if not self.config.show_traceback_on_error:
            return

        etype, evalue, tb = sys.exc_info()
        if tb and tb.tb_frame.f_code.co_name == "default":
            tb = tb.tb_next
            if tb and tb.tb_frame.f_code.co_filename == "<stdin>":
                tb = tb.tb_next
                if tb:
                    self._remove_bdb_context(evalue)
                    tb_limit = self.config.show_traceback_on_error_limit
                    fmt_exc = traceback.format_exception(
                        etype, evalue, tb, limit=tb_limit
                    )
                    # Remove the last line (exception string again).
                    if len(fmt_exc) > 1 and fmt_exc[-1][0] != " ":
                        fmt_exc.pop()
                    print("".join(fmt_exc).rstrip(), file=self.stdout)

    @staticmethod
    def _remove_bdb_context(evalue):
        removed_bdb_context = evalue
        while removed_bdb_context.__context__:
            ctx = removed_bdb_context.__context__
            if (
                isinstance(ctx, AttributeError)
                and ctx.__traceback__.tb_frame.f_code.co_name == "onecmd"
            ):
                removed_bdb_context.__context__ = None
                break
            removed_bdb_context = removed_bdb_context.__context__


if hasattr(pdb, "Restart"):
    Restart = pdb.Restart

if hasattr(pdb, "_usage"):
    _usage = pdb._usage

# Copy some functions from pdb.py, but rebind the global dictionary.
for name in "run runeval runctx runcall pm main".split():
    func = getattr(pdb, name)
    globals()[name] = rebind_globals(func, globals())
del name, func


def post_mortem(t=None, Pdb=Pdb):
    if t is None:
        t = sys.exc_info()[2]
        assert t is not None, "post_mortem outside of exception context"
    p = Pdb()
    p.reset()
    p.interaction(None, t)


GLOBAL_PDB = None


def set_trace(frame=None, header=None, Pdb=Pdb, **kwds):
    global GLOBAL_PDB
    if GLOBAL_PDB and hasattr(GLOBAL_PDB, "_pdbp_completing"):
        return
    if frame is None:
        frame = sys._getframe().f_back
    if GLOBAL_PDB:
        pdb = GLOBAL_PDB
        sys.settrace(None)
    else:
        filename = frame.f_code.co_filename
        lineno = frame.f_lineno
        pdb = Pdb(start_lineno=lineno, start_filename=filename, **kwds)
        GLOBAL_PDB = pdb
    if header is not None:
        pdb.message(header)
    pdb.set_trace(frame)


def cleanup():
    global GLOBAL_PDB
    GLOBAL_PDB = None


def xpm(Pdb=Pdb):
    """
    Enter a post-mortem pdb related to the exception just catched.
    (Used inside an except clause.)
    """
    info = sys.exc_info()
    print(traceback.format_exc())
    post_mortem(info[2], Pdb)


def enable():
    global set_trace
    set_trace = enable.set_trace


enable.set_trace = set_trace


def disable():
    global set_trace
    set_trace = disable.set_trace


disable.set_trace = lambda frame=None, Pdb=Pdb: None


def set_tracex():
    print("PDB!")


set_tracex._dont_inline_ = True

_HIDE_FRAME = object()


def hideframe(func):
    c = func.__code__
    new_co_consts = c.co_consts + (_HIDE_FRAME,)
    if hasattr(c, "replace"):
        c = c.replace(co_consts=new_co_consts)
    elif sys.version_info < (3, ):
        c = types.CodeType(
            c.co_argcount, c.co_nlocals, c.co_stacksize,
            c.co_flags, c.co_code,
            new_co_consts,
            c.co_names, c.co_varnames, c.co_filename,
            c.co_name, c.co_firstlineno, c.co_lnotab,
            c.co_freevars, c.co_cellvars)
    else:
        c = types.CodeType(
            c.co_argcount, c.co_kwonlyargcount, c.co_nlocals, c.co_stacksize,
            c.co_flags, c.co_code,
            c.co_consts + (_HIDE_FRAME,),
            c.co_names, c.co_varnames, c.co_filename,
            c.co_name, c.co_firstlineno, c.co_lnotab,
            c.co_freevars, c.co_cellvars)
    func.__code__ = c
    return func


def always(obj, value):
    return True


def break_on_setattr(attrname, condition=always, Pdb=Pdb):
    def decorator(cls):
        old___setattr__ = cls.__setattr__

        @hideframe
        def __setattr__(self, attr, value):
            if attr == attrname and condition(self, value):
                frame = sys._getframe().f_back
                pdb_ = Pdb()
                pdb_.set_trace(frame)
                pdb_.stopframe = frame
                pdb_.interaction(frame, None)
            old___setattr__(self, attr, value)
        cls.__setattr__ = __setattr__
        return cls
    return decorator


if sys.version_info[0] >= 3:
    import pdb
    pdb.Pdb = Pdb
    pdb.Color = Color
    pdb.DefaultConfig = DefaultConfig
    pdb.OrderedDict = OrderedDict
    pdb.Completer = Completer
    pdb.CLEARSCREEN = CLEARSCREEN
    pdb.GLOBAL_PDB = GLOBAL_PDB
    pdb.import_from_stdlib = import_from_stdlib
    pdb.ConfigurableClass = ConfigurableClass
    pdb.side_effects_free = side_effects_free
    pdb.rebind_globals = rebind_globals
    pdb.lasti2lineno = lasti2lineno
    pdb.tabcompleter = tabcompleter
    pdb.post_mortem = post_mortem
    pdb.set_tracex = set_tracex
    pdb.setbgcolor = setbgcolor
    pdb.set_trace = set_trace
    pdb.signature = signature
    pdb.Undefined = Undefined
    pdb.cleanup = cleanup
    pdb.xpm = xpm

if __name__ == "__main__":
    import pdb
    pdb.main()
