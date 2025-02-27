from io import BytesIO
from typing import BinaryIO, ByteString, Iterator
from warnings import warn

from tivars.models import *
from tivars.tokenizer import TokenizedString
from .data import *


class TIHeader:
    class Raw:
        __slots__ = "magic", "extra", "product_id", "comment"

        def bytes(self) -> bytes:
            return self.magic + self.extra + self.product_id + self.comment

    def __init__(self, model: TIModel = None, *,
                 magic: str = None, extra: bytes = b'\x1a\x0a', product_id: bytes = b'\x00',
                 comment: str = "Created with tivars_lib_py v0.6"):
        self.raw = self.Raw()

        model = model or TI_82AEP

        self.magic = magic or model.magic
        self.extra = extra
        self.product_id = product_id or model.product_id
        self.comment = comment

    def __bytes__(self) -> bytes:
        return self.bytes()

    def __copy__(self) -> 'TIHeader':
        new = TIHeader()
        new.load_bytes(self.bytes())
        return new

    def __eq__(self, other: 'TIHeader') -> bool:
        try:
            return self.__class__ == other.__class__ and self.bytes() == other.bytes()

        except AttributeError:
            return False

    def __or__(self, other: list['TIEntry']):
        new = other[0].export(header=self, name=other[0].name, model=self.derive_model())

        for entry in other[1:]:
            new.add_entry(entry)

        return new

    def __len__(self) -> int:
        return 53

    @Section(8, String)
    def magic(self) -> str:
        """
        The file magic for the var

        Used to identify if the file is intended for the TI-82, TI-83, or TI-83+ and onward
        Can be one of **TI82**, **TI83**, or **TI83F*
        """

    @Section(2)
    def extra(self) -> bytes:
        """
        Extra export bytes for the var

        Exact meaning and interpretation of these bytes is not yet determined
        These bytes are set by different export tools and can often be "incorrect" without causing issues
        """

    @Section(1)
    def product_id(self) -> bytes:
        """
        The product ID for the var

        Used to identify the model the var was created on, though has no actual functional ramifications
        Does not constitute a 1-to-1 mapping to distinct models
        """

    @Section(42, String)
    def comment(self) -> str:
        """
        The comment attached to the var
        """

    def derive_model(self) -> TIModel:
        match self.magic:
            case TI_82.magic:
                model = TI_82
            case TI_83.magic:
                model = TI_83
            case TI_84P.magic:
                try:
                    models = [m for m in MODELS if m.magic == self.magic]
                    if self.product_id != b'\x00':
                        models = [m for m in models if m.product_id == self.product_id]

                    model = max(models, key=lambda m: m.flags)

                except ValueError:
                    warn(f"The var product ID ({self.product_id}) is not recognized.",
                         BytesWarning)
                    model = None

            case _:
                warn(f"The var file magic ({self.magic}) is not recognized.",
                     BytesWarning)
                model = None

        return model

    def load_bytes(self, data: bytes | BytesIO):
        try:
            data = BytesIO(data.read())

        except AttributeError:
            data = BytesIO(data)

        # Read magic
        self.raw.magic = data.read(8)

        # Read export bytes
        self.raw.extra = data.read(2)

        # Read product ID
        self.raw.product_id = data.read(1)

        # Read comment
        self.raw.comment = data.read(42)

    def bytes(self) -> bytes:
        return self.raw.bytes()

    def load_from_file(self, file: BinaryIO):
        self.load_bytes(file.read(len(self)))

    def open(self, filename: str):
        with open(filename, 'rb') as file:
            self.load_bytes(file.read())


class TIEntry(Dock, Converter):
    _T = 'TIEntry'

    flash_only = False

    extensions = {None: "8xg"}
    type_ids = {}

    versions = []

    base_meta_length = 11
    flash_meta_length = 13
    min_data_length = 0

    _type_id = None

    class Raw:
        __slots__ = "meta_length", "type_id", "name", "version", "archived", "data"

        def bytes(self) -> bytes:
            return self.meta_length + self.data_length + \
                self.type_id + self.name + self.version + self.archived + \
                self.data_length + self.data

        @property
        def data_length(self) -> bytes:
            return int.to_bytes(len(self.data), 2, 'little')

        @property
        def flash_bytes(self) -> bytes:
            return (self.version + self.archived)[
                   :int.from_bytes(self.meta_length, 'little') - TIEntry.base_meta_length]

        @property
        def meta(self) -> bytes:
            return self.bytes()[2:int.from_bytes(self.meta_length, 'little') + 2]

    def __init__(self, init=None, *,
                 for_flash: bool = True, name: str = "UNNAMED",
                 version: bytes = None, archived: bool = None,
                 data: ByteString = None):
        self.raw = self.Raw()

        self.meta_length = TIEntry.flash_meta_length if for_flash else TIEntry.base_meta_length
        self.type_id = self._type_id if self._type_id else b'\xFF'
        self.name = name
        self.version = version or b'\x00'
        self.archived = archived or False

        if not for_flash:
            if version is not None or archived is not None:
                warn("Models without flash chips do not support versioning or archiving.",
                     UserWarning)

            if self.flash_only:
                warn(f"{type(self)} entries are not compatible with flashless chips.",
                     UserWarning)

        self.clear()
        if data:
            self.data[:len(data)] = bytearray(data)
        elif init is not None:
            try:
                self.load_bytes(init.bytes())
            except AttributeError:
                self.load(init)

    def __bool__(self) -> bool:
        return not self.is_empty

    def __bytes__(self) -> bytes:
        return self.bytes()

    def __copy__(self) -> 'TIEntry':
        new = self.__class__()
        new.load_bytes(self.bytes())
        return new

    def __eq__(self, other: 'TIEntry') -> bool:
        try:
            return self.__class__ == other.__class__ and self.bytes() == other.bytes()

        except AttributeError:
            return False

    def __format__(self, format_spec: str) -> str:
        raise TypeError(f"unsupported format string passed to {type(self)}.__format__")

    def __iter__(self) -> Iterator:
        raise NotImplementedError

    def __len__(self) -> int:
        return 2 + self.meta_length + 2 + self.data_length

    def __str__(self) -> str:
        return self.string()

    @Section(2, Integer)
    def meta_length(self) -> int:
        """
        The length of the meta section of the entry

        Can be 13 (contains flash) or 11 (lacks flash)
        """

    @property
    def data_length(self) -> int:
        """
        The length of the data section of the entry

        Can be zero
        """

        return len(self.data)

    @Section(1, Bytes)
    def type_id(self) -> bytes:
        """
        The type ID of the entry

        Used the interpret the contents of the data section of the entry
        """

    @Section(8, TokenizedString)
    def name(self) -> str:
        """
        The name of the entry

        Interpretation as text depends on the entry type; see individual types for details
        """

    @Section(1, Bytes)
    def version(self) -> bytes:
        """
        The version number of the entry

        Is not present for vars without flash bytes
        """

    @Section(1, Boolean)
    def archived(self) -> bool:
        """
        Whether the entry is archived
        A value of 0x80 is truthy; all others are falsy

        Is not present for vars without flash bytes
        """

    @Section()
    def data(self) -> bytearray:
        """
        The data section of the entry

        See individual entry types for how this data is interpreted
        """

    @classmethod
    def get(cls, data: bytes, instance) -> _T:
        return cls(data=data)

    @classmethod
    def set(cls, value: _T, instance) -> bytes:
        return value.data

    @property
    def flash_bytes(self) -> bytes:
        return (self.raw.version + self.raw.archived)[:self.meta_length - TIEntry.base_meta_length]

    @property
    def is_empty(self) -> bool:
        return self.data_length == 0

    @property
    def meta(self) -> bytes:
        return self.raw.data_length + self.raw.type_id + self.raw.name + self.raw.version + self.raw.archived

    @staticmethod
    def next_entry_length(stream: BinaryIO) -> int:
        meta_length = int.from_bytes(stream.read(2), 'little')
        data_length = int.from_bytes(stream.read(2), 'little')
        stream.seek(-4, 1)

        return 2 + meta_length + 2 + data_length

    @classmethod
    def register(cls, var_type: type['TIEntry']):
        cls.type_ids[var_type._type_id] = var_type

    def archive(self):
        if self.flash_bytes:
            self.archived = True
        else:
            raise TypeError("entry does not support archiving.")

    def clear(self):
        self.raw.data = bytearray(0)
        self.set_length()

    def set_length(self, length: int = None):
        length = length or self.min_data_length
        if length > self.data_length:
            self.raw.data.extend(bytearray(length - self.data_length))

    def unarchive(self):
        if self.flash_bytes:
            self.archived = False
        else:
            raise TypeError("entry does not support archiving.")

    @Loader[ByteString, BytesIO]
    def load_bytes(self, data: bytes | BytesIO):
        try:
            data = BytesIO(data.read())

        except AttributeError:
            data = BytesIO(data)

        # Read meta length
        self.raw.meta_length = data.read(2)

        # Read data length
        data_length = data.read(2)

        # Read and check type ID
        self.raw.type_id = data.read(1)

        if self._type_id is not None and self.raw.type_id != self._type_id:
            if self.raw.type_id in TIEntry.type_ids:
                warn(f"The entry type is incorrect (expected {type(self)}, got {TIEntry.type_ids[self.raw.type_id]}).",
                     BytesWarning)

            else:
                warn(f"The entry type is incorrect (expected {type(self)}, got an unknown type). "
                     f"Load the var file into a TIVar instance if you don't know the entry type(s).",
                     BytesWarning)

        # Read varname
        self.raw.name = data.read(8)

        # Read flash bytes
        match self.meta_length:
            case TIEntry.flash_meta_length:
                self.raw.version = data.read(1)
                self.raw.archived = data.read(1)

                if self.versions and self.raw.version not in self.versions:
                    warn(f"The version ({self.raw.version.hex()}) is not recognized.",
                         BytesWarning)

                if self.raw.archived not in b'\x00\x80':
                    warn(f"The archive flag ({self.raw.archived.hex()}) is set to an unexpected value.",
                         BytesWarning)

            case TIEntry.base_meta_length:
                self.raw.version = b'\x00'
                self.raw.archived = b'\x00'

                if self.flash_only:
                    warn(f"{type(self)} vars are not compatible with flashless chips.",
                         BytesWarning)

            case _:
                warn(f"The entry meta length has an unexpected value ({self.meta_length}); "
                     f"attempting to read flash bytes anyway.",
                     BytesWarning)
                self.raw.version = data.read(1)
                self.raw.archived = data.read(1)

                if self.raw.archived not in b'\x00\x80':
                    warn(f"The archive flag is set to an unexpected value.",
                         BytesWarning)

        # Read data and check length
        data_length2 = data.read(2)
        if data_length != data_length2:
            warn(f"The var entry data lengths are mismatched ({data_length} vs. {data_length2}); "
                 f"using {data_length2} to read the data section.",
                 BytesWarning)

        self.raw.data = bytearray(data.read(int.from_bytes(data_length2, 'little')))

        try:
            self.coerce()

        except TypeError:
            warn(f"Type ID 0x{self.raw.type_id.hex()} is not recognized; entry will not be coerced to a subclass.",
                 BytesWarning)

    def bytes(self) -> bytes:
        return self.raw.bytes()

    def load_data_section(self, data: BytesIO):
        self.raw.data = bytearray(data.read(type(self).data.length))

    @Loader[BinaryIO]
    def load_from_file(self, file: BinaryIO, *, offset: int = 0):
        # Load header
        header = TIHeader()
        header.load_from_file(file)
        file.seek(2, 1)

        # Seek to offset
        while offset:
            file.seek(self.next_entry_length(file), 1)
            offset -= 1

        self.load_bytes(file.read(self.next_entry_length(file)))
        file.seek(2, 1)

    @Loader[str]
    def load_string(self, string: str):
        raise NotImplementedError

    def string(self) -> str:
        raise NotImplementedError

    def open(self, filename: str):
        if self._type_id is not None and \
                not any(filename.endswith(extension) for extension in self.extensions.values()):
            warn(f"File extension .{filename.split('.')[-1]} not recognized for var type {type(self)}; "
                 f"attempting to read anyway.")

        with open(filename, 'rb') as file:
            file.seek(55)
            self.load_bytes(file.read(self.next_entry_length(file)))
            file.seek(2, 1)

            if file.read():
                warn("The selected var file contains multiple entries; only the first will be loaded. "
                     "Use load_from_file to select a particular entry, or load the entire file in a TIVar object.",
                     UserWarning)

    def save(self, filename: str = None, *, header: TIHeader = None, model: TIModel = None):
        self.export(header=header, model=model).save(filename)

    def export(self, *, header: TIHeader = None, name: str = 'UNNAMED', model: TIModel = None) -> 'TIVar':
        var = TIVar(header=header, name=name or self.name, model=model)
        var.add_entry(self)
        return var

    def coerce(self):
        if self._type_id is None:
            try:
                self.__class__ = self.type_ids[self.raw.type_id]
                self.set_length()
                self.coerce()

            except KeyError:
                raise TypeError(f"type ID 0x{self.raw.type_id.hex()} not recognized")


class TIVar:
    def __init__(self, *, header: TIHeader = None, name: str = 'UNNAMED', model: TIModel = None):
        super().__init__()

        self.header = header or TIHeader(magic=model.magic if model is not None else None)
        self.entries = []

        self.name = name
        self._model = model

        if self._model and self._model != self.header.derive_model():
            warn(f"The var's model ({self._model}) doesn't match its header's ({self.header.derive_model()}).",
                 UserWarning)

    def __bool__(self) -> bool:
        return not self.is_empty

    def __bytes__(self) -> bytes:
        return self.bytes()

    def __copy__(self) -> 'TIVar':
        new = TIVar()
        new.load_bytes(self.bytes())
        return new

    def __eq__(self, other: 'TIVar'):
        try:
            eq = self.__class__ == other.__class__ and len(self.entries) == len(other.entries)
            return eq and all(entry == other_entry for entry, other_entry in zip(self.entries, other.entries))

        except AttributeError:
            return False

    def __len__(self):
        return len(self.header) + self.entry_length + 2

    @property
    def entry_length(self) -> int:
        """
        The total length of the var entries

        Should be 57 less than the total var size
        """

        return sum(len(entry) for entry in self.entries)

    @property
    def checksum(self):
        """
        The checksum for the var

        This is equal to the lower 2 bytes of the sum of all bytes in the entries
        """

        return int.to_bytes(sum(sum(entry.bytes()) for entry in self.entries) & 0xFFFF, 2, 'little')

    @property
    def extension(self) -> str:
        try:
            extension = self.entries[0].extensions[self._model]
            if not extension:
                raise TypeError(f"The {self._model} does not support this var type.")

        except KeyError:
            warn(f"Model {self._model} not recognized.")
            extension = self.entries[0].extensions[None]

        if len(self.entries) == 1:
            return extension

        else:
            return "8xg"

    @property
    def is_empty(self) -> bool:
        return len(self.entries) == 0

    @property
    def model(self) -> TIModel:
        return self.model

    def add_entry(self, entry: TIEntry = None):
        entry = entry or TIEntry()

        if not self.is_empty:
            if entry.meta_length != self.entries[0].meta_length:
                warn(f"The new entry has a conflicting meta length "
                     f"(expected {self.entries[0].meta_length}, got {entry.meta_length}).",
                     UserWarning)

        self.entries.append(entry)

    def clear(self):
        self.entries.clear()

    def load_bytes(self, data: bytes | BytesIO):
        try:
            data = BytesIO(data.read())

        except AttributeError:
            data = BytesIO(data)

        # Read header
        self.header.load_bytes(data.read(53))
        entry_length = int.from_bytes(data.read(2), 'little')

        # Read entries
        while entry_length:
            self.add_entry()

            length = TIEntry.next_entry_length(data)
            self.entries[-1].load_bytes(data.read(length))

            entry_length -= length

        # Read checksum
        checksum = data.read(2)

        # Discern model
        model = self.header.derive_model()

        if self._model is None:
            self._model = model

        elif self._model != model:
            warn(f"The var file comes from a different model (expected {self._model}, got {model}).")

        # Check² sum
        if checksum != self.checksum:
            warn(f"The checksum is incorrect (expected {self.checksum}, got {checksum}).",
                 BytesWarning)

    def bytes(self):
        dump = self.header.bytes()
        dump += int.to_bytes(self.entry_length, 2, 'little')

        for entry in self.entries:
            dump += entry.bytes()

        dump += self.checksum
        return dump

    def load_var_file(self, file: BinaryIO):
        self.load_bytes(file.read())

    def open(self, filename: str):
        with open(filename, 'rb') as file:
            self.load_bytes(file.read())

    def save(self, filename: str = None):
        with open(filename or f"{self.name}.{self.extension}", 'wb+') as file:
            file.write(self.bytes())


class SizedEntry(TIEntry):
    @Section()
    def data(self) -> bytearray:
        """
        The data section of the entry

        Contains the length of the remaining data as its first two bytes
        """

    @View(data, Integer)[0:2]
    def length(self) -> int:
        """
        The length of the data section following this entry
        """

    def load_bytes(self, data: ByteString):
        super().load_bytes(data)

        if self.length != len(self.data[2:]):
            warn(f"The entry has an unexpected data length (expected {self.length}, got {len(self.data[2:])}).",
                 BytesWarning)


__all__ = ["TIHeader", "TIEntry", "TIVar", "SizedEntry"]
