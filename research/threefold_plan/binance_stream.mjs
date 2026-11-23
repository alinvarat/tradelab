// Public read-only depth capture. Node 20: --experimental-websocket.
import { closeSync, openSync, writeSync } from 'node:fs';

const [output, secondsArg = '12', symbol = 'BTCUSDT'] = process.argv.slice(2);
const seconds = Number(secondsArg);
if (!output || !/^[A-Z0-9]+$/.test(symbol) || !Number.isInteger(seconds) || seconds < 1 || seconds > 600) {
  throw new Error('Usage: binance_stream.mjs output.jsonl [seconds] [SYMBOL]');
}
const url = `wss://data-stream.binance.vision/ws/${symbol.toLowerCase()}@depth@100ms`;
const rest = `https://data-api.binance.vision/api/v3/depth?symbol=${symbol}&limit=100`;
const fd = openSync(output, 'wx');
const log = (kind, data) => writeSync(fd, JSON.stringify({ kind, utc: new Date().toISOString(), data }) + '\n');
log('start', { url, rest, seconds, symbol });
const ws = new WebSocket(url);
let finished = false;
let requested = false;
let receivedSnapshot = false;
let timer;
function finish(reason, failure = false) {
  if (finished) return;
  finished = true;
  clearTimeout(timer);
  log('stop', { reason, failure });
  closeSync(fd);
  if (failure) process.exitCode = 1;
  ws.close();
}
timer = setTimeout(() => finish('connection_timeout', true), 12_000);
ws.addEventListener('open', () => {
  clearTimeout(timer);
  timer = setTimeout(() => finish('capture_window_complete', !receivedSnapshot), seconds * 1000);
});
ws.addEventListener('message', async ({ data }) => {
  if (finished) return;
  log('diff', JSON.parse(data));
  if (requested) return;
  requested = true;
  try {
    const response = await fetch(rest, { signal: AbortSignal.timeout(8000) });
    if (!response.ok) throw new Error(`Snapshot HTTP ${response.status}`);
    const snapshot = await response.json();
    if (!finished) {
      log('snapshot', snapshot);
      receivedSnapshot = true;
    }
  } catch (error) {
    if (!finished) {
      log('error', { message: String(error) });
      finish('snapshot_error', true);
    }
  }
});
ws.addEventListener('close', () => finish('unexpected_close', true));
ws.addEventListener('error', () => finish('websocket_error', true));
