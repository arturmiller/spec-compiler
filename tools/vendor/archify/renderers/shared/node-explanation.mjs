// Local extension: readable summaries and authored details, without inference.
import { esc, textUnits } from './utils.mjs';

export function summaryLines(text, width, fontSize = 9.5) {
  const limit = (width - 28) / (fontSize * 0.57);
  const lines = [];
  let line = '';
  for (const word of String(text || '').trim().split(/\s+/).filter(Boolean)) {
    if (textUnits(word) > limit) throw new Error('Summary contains a word too wide for its node.');
    if (line && textUnits(line + ' ' + word) > limit) { lines.push(line); line = word; }
    else line = line ? line + ' ' + word : word;
  }
  if (line) lines.push(line);
  return lines;
}

export function renderSummary(node, cx, y, width, height, offset = 66) {
  if (!node.summary) return '';
  const lines = summaryLines(node.summary, width);
  if (offset + (lines.length - 1) * 12 + 12 > height) {
    throw new Error(`Summary in node "${node.id}" needs more height; enlarge the authored node instead of reducing text.`);
  }
  return `<text class="t-primary" data-node-summary="" data-detail="context" x="${cx}" y="${y + offset}" font-size="9.5" text-anchor="middle">`
    + lines.map((line, index) => `<tspan x="${cx}" dy="${index ? 12 : 0}">${esc(line)}</tspan>`).join('') + '</text>';
}

export function explanationMetadata(node) {
  return { summary: node.summary, description: node.description, links: node.links };
}
