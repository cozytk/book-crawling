/** SSE fields persist across network chunks until a blank line ends the event. */
export class SSEParser {
  private buffer = "";
  private event = "message";
  private data: string[] = [];

  constructor(private readonly emit: (event: string, data: string) => void) {}

  push(chunk: string) {
    this.buffer += chunk;
    let end: number;
    while ((end = this.buffer.indexOf("\n")) !== -1) {
      const line = this.buffer.slice(0, end).replace(/\r$/, "");
      this.buffer = this.buffer.slice(end + 1);
      if (!line) {
        if (this.data.length) this.emit(this.event, this.data.join("\n"));
        this.event = "message";
        this.data = [];
      } else if (!line.startsWith(":")) {
        const colon = line.indexOf(":");
        const field = colon < 0 ? line : line.slice(0, colon);
        const value = colon < 0 ? "" : line.slice(colon + 1).replace(/^ /, "");
        if (field === "event") this.event = value;
        if (field === "data") this.data.push(value);
      }
    }
  }
}
