import fs from 'node:fs';
import { parseImageStream, decodeMaskToRaster, recordsOfKind } from '@meta-sam/parser';
const lines = fs.readFileSync(process.argv[2], 'utf8').split('\n');
const evs = [];
for (const l of lines) if (l.startsWith('data: ') && l !== 'data: [DONE]') evs.push(JSON.parse(l.slice(6)));
async function* gen() { for (const e of evs) if (e.type?.startsWith('response.output_text') || e.type === 'response.completed') yield e; }
const p = parseImageStream(gen());
for await (const _ of p) {}
const r = await p.finalResult;
console.error('outcome', JSON.stringify(r.outcome), 'diagnostics', r.diagnostics.length);
const out = recordsOfKind(r.records, 'mask').map(m => {
  const ras = decodeMaskToRaster(m.mask);
  return { id: m.objectId, bounds: m.bounds, len: ras.length, b64: Buffer.from(ras).toString('base64') };
});
fs.writeFileSync(process.argv[3], JSON.stringify(out));
console.error(out.length, 'masks', out.map(o => `${o.id}:${o.bounds.right-o.bounds.left}x${o.bounds.bottom-o.bounds.top}=${o.len}`).join(' '));
