// A local test double for the native HTTP contract. No live accounts or tokens are used.
import { createServer } from 'node:http';
import { readFileSync } from 'node:fs';
const token = 'b'.repeat(64) + '.' + 'c'.repeat(64);
const state = JSON.parse(readFileSync(new URL('../project/assets/game.json', import.meta.url))).demo;
state.playerId = 'native-qa-player';
let mode = 'online';
createServer((req, res) => {
  const reply = (status, data) => {
    res.writeHead(status, { 'content-type': 'application/json' });
    res.end(JSON.stringify(data));
  };
  if (['/test/offline', '/test/online', '/test/expired'].includes(req.url)) {
    mode = req.url.split('/').at(-1);
    return reply(200, { mode });
  }
  if (req.url === '/api/native/exchange' && req.method === 'POST') {
    return reply(200, { session: token });
  }
  if (req.headers['x-drenovar-session'] !== token || mode === 'expired') {
    return reply(401, { error: 'Сессия истекла' });
  }
  if (mode === 'offline') return reply(503, { error: 'Связь временно недоступна' });
  if (req.url === '/api/native/game/state') return reply(200, { ...state, serverTime: Date.now() });
  if (req.url === '/api/native/logout') return reply(200, { signedOut: true });
  reply(404, { error: 'Нет такого метода' });
}).listen(8426, '127.0.0.1', () => console.log('Native session fixture ready'));
