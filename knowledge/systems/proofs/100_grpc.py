"""gRPC rides on Protocol Buffers: a contract (.proto) compiled to typed stubs, carried over HTTP/2. Protobuf's
wire format is the heart of its compatibility story, so this experiment reproduces that format and its two rules:
a field is identified by its NUMBER (not its name or position), and unknown field numbers are skipped. That is
why you can add fields without breaking old readers -- and why you must NEVER reuse a field number.

Minimal protobuf wire format: each field is a tag varint (field_number << 3 | wire_type) then its value.
wire types used: 0 = varint (ints), 2 = length-delimited (strings/bytes).

A. Add a field: writer v2 adds field 3; a v1 reader that knows only fields {1,2} decodes it fine, skipping 3.
   -> backward/forward compatible, the whole point of field numbers.
B. Reuse a field number: writer v2' repurposes field 2 from string to int. A v1 reader still expects a string
   at field 2 and now reads garbage / wrong type -> silent corruption. Never reuse a number; reserve it.
Pure Python; no protoc, no network."""


def varint(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        out.append(b | (0x80 if n else 0))
        if not n:
            return bytes(out)


def read_varint(buf, i):
    n = shift = 0
    while True:
        b = buf[i]; i += 1
        n |= (b & 0x7F) << shift
        if not b & 0x80:
            return n, i
        shift += 7


def encode(fields):
    """fields: list of (number, wire_type, value). value is int for wt 0, bytes for wt 2."""
    out = bytearray()
    for num, wt, val in fields:
        out += varint(num << 3 | wt)
        if wt == 0:
            out += varint(val)
        else:
            out += varint(len(val)) + val
    return bytes(out)


def decode(buf, schema):
    """schema: {number: ('int'|'str', name)}. Returns parsed dict; unknown numbers are skipped (as protobuf does)."""
    i, out, skipped = 0, {}, []
    while i < len(buf):
        tag, i = read_varint(buf, i)
        num, wt = tag >> 3, tag & 0x7
        if wt == 0:
            val, i = read_varint(buf, i)
        else:
            ln, i = read_varint(buf, i)
            val, i = buf[i:i + ln], i + ln
        if num in schema:
            kind, name = schema[num]
            want_wt = 0 if kind == "int" else 2
            if wt != want_wt:                       # wire type does not match what this reader expects
                out[name] = f"<TYPE MISMATCH: expected {kind}, got wire-type {wt}>"
            else:
                out[name] = val.decode() if kind == "str" else val
        else:
            skipped.append(num)
    return out, skipped


V1_SCHEMA = {1: ("int", "id"), 2: ("str", "name")}  # the reader deployed in production

# A. writer adds field 3 (priority). v1 reader knows only 1 and 2.
msg_with_new_field = encode([(1, 0, 7), (2, 2, b"deploy"), (3, 0, 5)])
parsed, skipped = decode(msg_with_new_field, V1_SCHEMA)
print(f"A  v1 reader on v2 message: {parsed}, skipped unknown field(s) {skipped}  -> compatible")

# B. writer REUSES field number 2 as an int instead of a string.
msg_reused_number = encode([(1, 0, 7), (2, 0, 42)])
parsed, _ = decode(msg_reused_number, V1_SCHEMA)
print(f"B  v1 reader on reused-number message: {parsed}  -> field 2 read as the wrong type (corruption)")
print("B  rule: add fields with NEW numbers; reserve retired numbers; never repurpose one")
