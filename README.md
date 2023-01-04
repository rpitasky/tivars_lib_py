# tivars_lib_py

`tivars_lib_py` is a Python package for interacting with TI-(e)z80 (82/83/84 series) calculator files, i.e. lists, programs, matrices, appvars, etc.

Much of the functionality of this package has been ported over from [tivars_lib_cpp](https://github.com/adriweb/tivars_lib_cpp). However, a number of changes have made to the API to better suit Python's strengths and capabilities as a language (e.g. scripting).

## Installation

Clone this repository into your next project and import the package via `import tivars`. You can run the test suite via `__main__.py`, or run individual tests found in `tests/` with `unittest`.

Official releases are coming soon. All versions require Python 3.10+ to run.

## How to Use

### Creating vars

To create an empty var, instantiate its corresponding type from `tivars.types` with a name and calculator model:

```python
from tivars.models import *
from tivars.types import *

my_program = TIProgram("HELLO", TI_84p)
```

If you're not sure of a var's type or model, use `TIVar.infer` to guess given a file's contents:

```python
with open("MyVar", 'rb') as file:
    my_var = TIVar.infer(file)
    my_var_for83p = TIVar.infer(file, model=TI_83p)
```

### Reading and writing

Load an existing file via `load` or interpret from a string using `loads`:

```python
with open("HELLO.8xp", 'rb') as file:
    my_program.load(file)
    
# Alternative
my_program.open("HELLO.8xp")

# See the type classes for string formats
my_program.loads("Disp \"HELLO WORLD!\"")

```
Write the contents of a var as bytes or as a string with `dump` and `dumps`:

```python
with open("HELLO.8xp", 'wb+') as file:
    file.write(my_program.dump())
    
# Alternative
my_program.save("HELLO.8xp")

# Infer the output filename
my_program.save()

print(my_program.dumps())

```
### Headers and Entries

Each var is composed of a _header_ and _entry_ section, which can be exported as read-only `TIHeader` and `TIEntry` objects respectively from a var object:

```python
header, entry = my_var.header, my_var.entry
```

It is generally ill-advised to generate these independently, as the header specifies the length of the entry (and thus their contents are interdependent).

### Models

All TI-82/83/84 series calcs are represented as `TIModel` objects stored in `tivars.models`. Each model contains its name, signature, and feature flags; use `has` on a `TIFeature` to check that a model has a given a feature. Models are also used to determine var file extensions and token sheets.

For these reasons, it is _not_ recommended to instantiate your own models.

### Corrupt files

Files with corrupted metadata will not initialize with `load` or `open` unless `strict=False` is set. Corrupt vars can be identified by the `corrupt` attribute.

## Other Functionalities

### Tokenization

Functions to decode and encode strings from various token sheets can be found in `tivars.tokenizer`. Support currently exists for all forms of 82/83/84 series BASIC, Axe, Grammer, Prizm, and DCS8, as well as custom token sheets; PR's concerning the sheets themselves should be directed upstream to [CE-Fauxgramming/tokens](https://github.com/CE-Fauxgramming/tokens).
