const httpProxy = require('./frontend/node_modules/http-proxy');
const http = require('http');

const BACKEND_PORT = 8000;
const METRO_PORT = 8081;
const PROXY_PORT = 5000;

const proxy = httpProxy.createProxyServer({});

proxy.on('error', (err, req, res) => {
  console.error('Proxy error:', err.message);
  if (!res.headersSent) {
    res.writeHead(502, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Proxy error', message: err.message }));
  }
});

const server = http.createServer((req, res) => {
  const url = req.url || '/';
  
  if (url.startsWith('/api/') || url === '/api' || url.startsWith('/docs') || url.startsWith('/openapi') || url.startsWith('/redoc')) {
    proxy.web(req, res, { target: `http://localhost:${BACKEND_PORT}` });
  } else {
    proxy.web(req, res, { target: `http://localhost:${METRO_PORT}` });
  }
});

server.on('upgrade', (req, socket, head) => {
  proxy.ws(req, socket, head, { target: `http://localhost:${METRO_PORT}` });
});

server.listen(PROXY_PORT, '0.0.0.0', () => {
  console.log(`Proxy server running on port ${PROXY_PORT}`);
  console.log(`  /api/* -> http://localhost:${BACKEND_PORT}`);
  console.log(`  /* -> http://localhost:${METRO_PORT}`);
});
