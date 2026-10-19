# 100. gRPC

Track: J. Networking · Status: proven · Updated: 2026-10-19

## What it is
gRPC is a contract-first RPC framework: you write a service and its messages in a `.proto` file (Protocol Buffers), compile it to typed client and server stubs in many languages, and call remote methods as if they were local functions. On the wire it uses **Protocol Buffers** — a compact binary format — over **HTTP/2** (099-http2-http3.md), so it gets multiplexed streams, header compression and long-lived connections. It offers four call types: unary (one request, one response), server-streaming, client-streaming, and bidirectional streaming. The contract is the point: the `.proto` is the single source of truth, stubs are generated, and Protobuf's compatibility rules let the contract evolve. Those rules turn on **field numbers**: every field has a number, the number (not the name or position) identifies it on the wire, and a reader skips field numbers it does not know — which is exactly what makes adding fields safe and reusing a number catastrophic (proof).

## When it is worth it
- Worth it for **internal service-to-service APIs** at volume, especially polyglot ones: the generated stubs remove hand-written client code, the binary format and HTTP/2 cut latency and bandwidth versus JSON/REST, streaming is first-class, and the `.proto` is an enforced contract. Strong fit for a microservice mesh or a high-throughput backend link.
- Over-engineering when:
  - the client is a **browser** — browsers cannot speak raw gRPC, so you need gRPC-web and a proxy, and for most web apps JSON/REST or an RPC-over-JSON is simpler;
  - the API is **low-volume or public** — the cost of Protobuf tooling, code generation and binary opacity (you cannot `curl` and read it) buys nothing over JSON;
  - there is **one endpoint and one caller** — a single JSON webhook does not need a schema compiler and HTTP/2 RPC.

## How it fails
- **Reusing a field number:** a retired field's number is repurposed for a new field, so an old reader interprets new data as the old field — silent corruption, not an error (proof B). The rule is to add new numbers and `reserve` retired ones.
- **Incompatible type change:** changing a field's type (or `required`-ness in proto2) breaks the wire contract even if the number stays; the reader misreads the bytes.
- **Breaking the contract without regenerating:** server and clients drift because stubs were not regenerated from the new `.proto`, so a renamed method or message mismatches at runtime.
- **Browser/edge assumptions:** code assumes raw gRPC reaches a browser or passes a proxy that only understands HTTP/1.1, and calls fail (099: edge/origin protocol mismatch).
- **Streaming resource leaks:** long-lived streams without deadlines, flow control or cancellation pile up on the server (044-backpressure.md, 011-timeouts.md).
- **Opaque debugging:** binary frames mean you cannot inspect traffic with ordinary HTTP tools, so problems are harder to see without reflection/tooling.

## Review checklist
- [ ] **Does a `.proto` change keep wire compatibility?** · Applies when: the diff edits a `.proto` (or any Protobuf/gRPC schema). · Block if: it reuses or renumbers an existing field, changes a field's type, or removes a field without reserving its number — any of which silently corrupts old readers.
- [ ] **Are generated stubs regenerated and shipped with the contract change?** · Applies when: the diff changes a gRPC service or message definition. · Block if: server and clients are not regenerated from the same `.proto`, so the contract drifts at runtime.
- [ ] **Do streams and calls have deadlines and cancellation?** · Applies when: the diff adds a gRPC call, especially a streaming one. · Block if: there is no deadline/timeout or cancellation path, so a slow or abandoned call holds server resources.
- [ ] **Is gRPC justified for this caller and volume?** · Applies when: the diff introduces gRPC for an endpoint. · Block if: the caller is a browser, the API is public/low-volume, or there is a single JSON endpoint — where REST/JSON is simpler and gRPC's tooling buys nothing.

## In the factory
- **The factory uses JSON over HTTP, not gRPC, and that is correct.** The intake is one signed JSON webhook (`TriggerPayload`, 005-api-gateways.md) and the dashboard is a browser page fetching JSON (`/command/data`). A browser cannot speak raw gRPC, and there is one endpoint with one caller — gRPC would add a schema compiler, code generation and binary opacity for nothing. JSON is inspectable with `curl`, which suits a one-operator system.
- **The compatibility lesson still applies to the factory's JSON contract.** `TriggerPayload` must evolve the same way a `.proto` does: add optional fields, never repurpose an existing one. This is the JSON analogue of Protobuf field numbers and is already covered by 082-schema-versioning.md and 102-api-versioning.md (the `/command/data` shape the dashboard depends on). No separate gap.
- Not applicable at today's load: Protobuf schemas, generated stubs, HTTP/2 RPC, streaming, gRPC-web proxies.

## Proof
`python3 100_grpc.py`, a minimal reimplementation of the Protobuf wire format (tag = `field_number << 3 | wire_type`, varint and length-delimited values), with a v1 reader that knows only fields {1: id, 2: name}:
```
A  v1 reader on v2 message: {'id': 7, 'name': 'deploy'}, skipped unknown field(s) [3]  -> compatible
B  v1 reader on reused-number message: {'id': 7, 'name': '<TYPE MISMATCH: expected str, got wire-type 0>'}  -> field 2 read as the wrong type (corruption)
```
A: a v2 writer adds field 3; the v1 reader parses fields 1 and 2 and skips the unknown 3 — adding fields is safe. B: a writer repurposes field number 2 from string to int; the v1 reader still expects a string there and misreads it. The field number, not the name, is the contract — so you add numbers and reserve retired ones, never reuse them.

## Related
099-http2-http3.md, 098-tcp-vs-udp.md, 082-schema-versioning.md, 102-api-versioning.md, 005-api-gateways.md, 044-backpressure.md

## Sources
- "Introduction to gRPC" and "Core concepts", grpc.io: https://grpc.io/docs/what-is-grpc/introduction/
- "Proto Best Practices" / "Updating a Message Type" (field-number rules, reserved), Protocol Buffers docs: https://protobuf.dev/programming-guides/proto3/#updating
