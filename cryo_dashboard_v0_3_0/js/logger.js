export class CalculationLogger {
  constructor(maxEntries = 200) {
    this.maxEntries = maxEntries;
    this.entries = [];
  }

  add(eventType, payload = {}) {
    const entry = {
      timestamp: new Date().toISOString(),
      eventType,
      payload
    };

    this.entries.unshift(entry);

    if (this.entries.length > this.maxEntries) {
      this.entries.pop();
    }

    return entry;
  }

  clear() {
    this.entries = [];
  }

  toText() {
    return this.entries
      .map(e => `[${e.timestamp}] ${e.eventType}: ${JSON.stringify(e.payload)}`)
      .join("\n");
  }

  toJSON() {
    return JSON.stringify(this.entries, null, 2);
  }
}
