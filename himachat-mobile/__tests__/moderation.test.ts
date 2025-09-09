import { checkMessage } from '../src/utils/moderation';

describe('moderation.checkMessage', () => {
  it('rejects empty', () => {
    expect(checkMessage('   ').ok).toBe(false);
  });
  it('rejects too long', () => {
    const long = 'あ'.repeat(1000);
    expect(checkMessage(long).ok).toBe(false);
  });
  it('rejects NG words', () => {
    expect(checkMessage('これは殺すという語を含む').ok).toBe(false);
  });
  it('accepts normal text', () => {
    expect(checkMessage('こんにちは').ok).toBe(true);
  });
});

