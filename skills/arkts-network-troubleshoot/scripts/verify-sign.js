/** Offline source-request comparison. Copy this template into project evidence.
 * Supply independent, redacted source vectors and implement the actual algorithm.
 * Preserve Swift fixed-width overflow, truncation toward zero, UTF-8 and key order.
 * Empty inputs and an unimplemented candidate fail; matching vectors are not full protocol proof.
 */
'use strict';
const fs = require('fs');
function computeSign(vector) {
  throw new Error('Implement the candidate from the source algorithm before running vectors');
}
function main() {
  if (!process.argv[2]) throw new Error('Usage: node verify-sign.js VECTORS.json');
  const vectors = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  if (!Array.isArray(vectors) || vectors.length === 0) throw new Error('No source vectors');
  let failed = 0;
  for (const vector of vectors) {
    if (typeof vector.expectedSign !== 'string') throw new Error('Missing independent expectedSign');
    const passed = computeSign(vector) === vector.expectedSign;
    console.log(JSON.stringify({id: vector.id, passed}));
    if (!passed) failed++;
  }
  process.exitCode = failed ? 1 : 0;
}
try { main(); } catch (error) { console.error(error.message); process.exitCode = 2; }
