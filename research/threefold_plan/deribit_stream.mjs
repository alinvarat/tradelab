// Public read-only order-book stream pilot. Node 20: --experimental-websocket.
import { closeSync, openSync, readFileSync, writeSync } from 'node:fs';

const [output, secondsArg = '15'] = process.argv.slice(2);
const seconds = Number(secondsArg);
if (!output || !Number.isInteger(seconds) || seconds < 1 || seconds > 600) {
  throw new Error('Usage: deribit_stream.mjs output.jsonl [seconds between 1 and 600]');
}
const probe = JSON.parse(readFileSync(new URL('./source_probe.json', import.meta.url)));
const symbol = probe.deribit.instrument.instrument_name;
const channel = `book.${symbol}.100ms`;
const channels = [channel, `ticker.${symbol}.100ms`];
const url = 'wss://www.deribit.com/ws/api/v2';
const fd = openSync(output, 'wx');
const log = (kind, data) => writeSync(fd, JSON.stringify({ kind, utc: new Date().toISOString(), data }) + '\n');
log('start', { url, channel, channels, seconds });
const ws = new WebSocket(url);
let finished = false, timer;
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
  ws.send(JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'public/subscribe', params: { channels } }));
  timer = setTimeout(() => finish('capture_window_complete'), seconds * 1000);
});
ws.addEventListener('message', ({ data }) => {
  if (finished) return;
  const msg = JSON.parse(data);
  log('message', msg);
  if (msg.error) finish('server_error', true);
});
ws.addEventListener('error', () => finish('websocket_error', true));
ws.addEventListener('close', () => finish('unexpected_close', true));
