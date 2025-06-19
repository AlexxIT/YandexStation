import base64


class Protobuf:
    page_size = 0
    pos = 0

    def __init__(self, raw: str | bytes):
        self.raw = base64.b64decode(raw) if isinstance(raw, str) else raw

    def read(self, length: int) -> bytes:
        self.pos += length
        return self.raw[self.pos - length : self.pos]

    def read_byte(self):
        res = self.raw[self.pos]
        self.pos += 1
        return res

    # https://developers.google.com/protocol-buffers/docs/encoding#varints
    def read_varint(self) -> int:
        res = 0
        shift = 0
        while True:
            b = self.read_byte()
            res += (b & 0x7F) << shift
            if b & 0x80 == 0:
                break
            shift += 7
        return res

    def read_bytes(self) -> bytes:
        length = self.read_varint()
        return self.read(length)

    def read_dict(self) -> dict:
        res = {}
        while self.pos < len(self.raw):
            b = self.read_varint()
            typ = b & 0b111
            tag = b >> 3

            if typ == 0:  # VARINT
                v = self.read_varint()
            elif typ == 1:  # I64
                v = self.read(8)
            elif typ == 2:  # LEN
                v = self.read_bytes()
                try:
                    v = Protobuf(v).read_dict()
                except:
                    pass
            elif typ == 5:  # I32
                v = self.read(4)
            else:
                raise NotImplementedError

            if tag in res:
                if isinstance(res[tag], list):
                    res[tag] += [v]
                else:
                    res[tag] = [res[tag], v]
            else:
                res[tag] = v

        return res


def append_varint(b: bytearray, i: int):
    while i >= 0x80:
        b.append(0x80 | (i & 0x7F))
        i >>= 7
    b.append(i)


def loads(raw: str | bytes) -> dict:
    return Protobuf(raw).read_dict()


def dumps(data: dict) -> bytes:
    b = bytearray()
    for tag, value in data.items():
        assert isinstance(tag, int)
        if isinstance(value, str):
            b.append(tag << 3 | 2)
            append_varint(b, len(value))
            b.extend(value.encode())
        else:
            raise NotImplementedError
    return bytes(b)
