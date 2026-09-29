/** Read-only HTTP observation proxy for an authorized test device.
 * node http-capture-proxy.js [port] [hostFilter]
 * On iPhone or HarmonyOS: Wi-Fi -> connected network -> manual proxy -> host LAN IP and port.
 * Record prior settings and restore them after capture. This does not support HTTPS CONNECT.
 * Use a test account. Redact credentials and personal data before retaining or sharing evidence.
 * Source requests are evidence of this session only; unavailable traffic stays unverified.
 */
const http = require('http');

const PORT = parseInt(process.argv[2] || '8888', 10);
const HOST_FILTER = process.argv[3] || '';

const server = http.createServer((creq, cres) => {
  const chunks = [];
  creq.on('data', (c) => chunks.push(c));
  creq.on('end', () => {
    const body = Buffer.concat(chunks);
    const url = creq.url; // HTTP 代理请求里 url 是绝对地址 http://host/path
    const interesting = HOST_FILTER === '' || url.indexOf(HOST_FILTER) !== -1;

    if (interesting) {
      console.log('\n>>> ' + creq.method + ' ' + url);
      console.log('    HEADERS ' + JSON.stringify(creq.headers));
      if (body.length > 0) {
        console.log('    BODY ' + body.toString('utf8').slice(0, 4000));
      }
    }

    let u;
    try {
      u = new URL(url);
    } catch (e) {
      cres.writeHead(400);
      cres.end('proxy: bad url');
      return;
    }

    const preq = http.request(
      {
        hostname: u.hostname,
        port: u.port || 80,
        path: u.pathname + u.search,
        method: creq.method,
        headers: creq.headers,
      },
      (pres) => {
        const rchunks = [];
        pres.on('data', (d) => rchunks.push(d));
        pres.on('end', () => {
          const rbody = Buffer.concat(rchunks);
          if (interesting) {
            console.log('<<< ' + pres.statusCode + ' ' + url + '  ' +
              rbody.toString('utf8').slice(0, 2000));
          }
          cres.writeHead(pres.statusCode, pres.headers);
          cres.end(rbody);
        });
      }
    );
    preq.on('error', (e) => {
      console.log('PROXY ERR ' + e.message + '  for ' + url);
      cres.writeHead(502);
      cres.end('proxy error');
    });
    if (body.length > 0) preq.write(body);
    preq.end();
  });
});

// CONNECT（HTTPS 隧道）不在本脚本范围 —— 直接拒绝，避免连接挂死
server.on('connect', (req, sock) => {
  try { sock.write('HTTP/1.1 405 Method Not Allowed\r\n\r\n'); sock.destroy(); } catch (e) { /* ignore */ }
});
server.on('clientError', (err, sock) => {
  try { sock.destroy(); } catch (e) { /* ignore */ }
});
server.listen(PORT, '0.0.0.0', () => {
  console.log('http-capture-proxy listening on 0.0.0.0:' + PORT +
    (HOST_FILTER ? '  (filter: ' + HOST_FILTER + ')' : '  (logging all hosts)'));
});
