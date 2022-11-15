class Protobuf:
    page_size = 0
    pos = 0

    def __init__(self, raw: bytes):
        self.raw = raw

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
            t = b & 0b111
            k = b >> 3

            if t == 0:
                v = self.read_varint()
            elif t == 1:
                v = self.read(8)
            elif t == 2:
                v = self.read_bytes()
                if v[0] >> 3 == 1:
                    pb = Protobuf(v)
                    v = pb.read_dict()
            elif t == 5:
                v = self.read(4)
            else:
                raise NotImplementedError

            if k in res:
                if isinstance(res[k], list):
                    res[k] += [v]
                else:
                    res[k] = [res[k], v]
            else:
                res[k] = v

        return res
