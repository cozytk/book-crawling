import { test } from "node:test";
import assert from "node:assert/strict";
import { SSEParser } from "../src/lib/sse.ts";

const stream = ': keepalive\r\nevent: description_chunk\r\ndata: {"chunk":"한글"}\r\n\r\nevent: rating\ndata: {"platform":"yes24"}\n\nevent: done\ndata: {"source":"crawl"}\n\n';

test("SSE produces the same events at every possible network boundary", () => {
  for (let split = 0; split <= stream.length; split++) {
    const events: unknown[] = [];
    const parser = new SSEParser((event, data) => events.push([event, JSON.parse(data)]));
    parser.push(stream.slice(0, split));
    parser.push(stream.slice(split));
    assert.deepEqual(events, [["description_chunk", { chunk: "한글" }], ["rating", { platform: "yes24" }], ["done", { source: "crawl" }]]);
  }
});

test("UTF-8 bytes may split inside a Korean character", () => {
  const decoder = new TextDecoder();
  const events: unknown[] = [];
  const parser = new SSEParser((event, data) => events.push([event, JSON.parse(data)]));
  for (const byte of new TextEncoder().encode(stream)) parser.push(decoder.decode(Uint8Array.of(byte), { stream: true }));
  parser.push(decoder.decode());
  assert.equal(events.length, 3);
  assert.deepEqual(events[0], ["description_chunk", { chunk: "한글" }]);
});
