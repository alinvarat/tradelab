// Read-only spot depth capture for the five pairs in the verified notice.
import { closeSync, openSync, readFileSync, writeSync } from 'node:fs';
const [output, length = '18'] = process.argv.slice(2);
const seconds = Number(length);
if (!output || !Number.isInteger(seconds) || seconds < 1 || seconds > 600) throw Error('Invalid capture arguments');
const notice = JSON.parse(readFileSync(new URL('./delist_event_20261120.json',import.meta.url)));
if (Date.now() >= Date.parse(notice.stop_utc)) throw Error('The notice has reached its scheduled removal time');
const host = process.argv[4] ?? 'stream.bybit.com';
if (!['stream.bybit.com','stream.bytick.com'].includes(host)) throw Error('Unsupported host');
const url = `wss://${host}/v5/public/spot`;
const topics = notice.symbols.map(s => `orderbook.50.${s}`);
const fd = openSync(output,'wx');
const log = (kind,data) => writeSync(fd,JSON.stringify({kind,utc:new Date().toISOString(),data})+'\n');
log('start',{url,topics,notice:notice.notice,seconds});
const ws = new WebSocket(url);
const seen = new Set();
let finished = false, timer;
function stop(reason,failure = false) {
  if (finished) return;
  finished = true;
  clearTimeout(timer);
  log('stop',{reason,failure,snapshots:seen.size});
  closeSync(fd);
  if (failure) process.exitCode = 1;
  ws.close();
}
timer = setTimeout(() => stop('connection_timeout',true),10000);
ws.addEventListener('open',() => {
  clearTimeout(timer);
  ws.send(JSON.stringify({op:'subscribe',args:topics}));
  timer = setTimeout(() => stop('window_complete',seen.size!==topics.length),seconds*1000);
});
ws.addEventListener('message',({data}) => {
  if (finished) return;
  const message = JSON.parse(data);
  log('message',message);
  if (message.type==='snapshot') seen.add(message.topic);
  if (message.success===false) stop('subscription_failed',true);
});
ws.addEventListener('error',() => stop('websocket_error',true));
ws.addEventListener('close',() => stop('unexpected_close',true));
