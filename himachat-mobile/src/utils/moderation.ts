import { NG_WORDS, MAX_MESSAGE_LENGTH } from '../config';

export type CheckResult = { ok: true; text: string } | { ok: false; reason: string };

export function checkMessage(text: string): CheckResult {
  const t = (text || '').trim();
  if (!t) return { ok: false, reason: '空のメッセージは送れません' };
  if (t.length > MAX_MESSAGE_LENGTH) return { ok: false, reason: `長すぎます（最大${MAX_MESSAGE_LENGTH}文字）` };
  const lowered = t.toLowerCase();
  for (const w of NG_WORDS) {
    if (!w) continue;
    if (lowered.includes(w.toLowerCase())) {
      return { ok: false, reason: '不適切な表現が含まれています' };
    }
  }
  return { ok: true, text: t };
}

