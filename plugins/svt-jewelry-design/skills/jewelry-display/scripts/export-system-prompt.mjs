import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const referencePath = path.join(__dirname, '..', 'references', 'product-display-image2-system-prompt.md');
const markdown = fs.readFileSync(referencePath, 'utf8');
const match = markdown.match(/## System Prompt\s+```text\s*([\s\S]*?)\s*```/);

const args = process.argv.slice(2);
const has = (flag) => args.includes(flag);
const valueAfter = (flag) => {
  const index = args.indexOf(flag);
  if (index === -1) return null;
  return args[index + 1] ?? null;
};

if (!match) {
  console.error(`System prompt block not found in ${referencePath}`);
  process.exit(1);
}

const prompt = match[1].trim();

if (has('--check')) {
  const requiredPhrases = [
    'negative-space',
    'asymmetry',
    'Props are display supports',
    'Occlusion is allowed only at believable support points',
    'product display, not a campaign poster',
  ];
  const missing = requiredPhrases.filter((phrase) => !prompt.includes(phrase));
  if (missing.length > 0) {
    console.error(`System prompt is missing required product-display phrases: ${missing.join(', ')}`);
    process.exit(1);
  }
}

const asJson = has('--json');
const output = asJson
  ? `${JSON.stringify({ role: 'jewelry-display', source: referencePath, system_prompt: prompt }, null, 2)}\n`
  : `${prompt}\n`;

const outputPath = valueAfter('--output');
if (outputPath) {
  fs.mkdirSync(path.dirname(path.resolve(outputPath)), { recursive: true });
  fs.writeFileSync(outputPath, output, 'utf8');
} else {
  process.stdout.write(output);
}
