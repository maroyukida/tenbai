import { findMatchOrEnqueue } from '../src/services/matchmaker';

// firebase/firestore を最小限モック
jest.mock('firebase/firestore', () => {
  const docs: any[] = [];
  return {
    collection: jest.fn(() => ({})),
    doc: jest.fn((...args: any[]) => {
      // doc(collectionRef) または doc(db, 'col', id)
      if (args.length === 1) return { id: 'room_mock' };
      return { id: args[2] };
    }),
    getDoc: jest.fn(async () => ({ exists: () => false })),
    deleteDoc: jest.fn(async () => {}),
    getDocs: jest.fn(async () => ({ docs })),
    orderBy: jest.fn(),
    where: jest.fn(),
    limit: jest.fn(),
    query: jest.fn(),
    serverTimestamp: jest.fn(() => new Date()),
    addDoc: jest.fn(async () => ({ id: 'room_mock' })),
    setDoc: jest.fn(async () => {}),
    updateDoc: jest.fn(async () => {}),
    runTransaction: jest.fn(async (_db, fn) => fn({
      get: jest.fn(async () => ({ exists: () => true, data: () => ({ status: 'waiting' }) })),
      update: jest.fn(),
      set: jest.fn(),
    })),
  };
});

jest.mock('../src/firebase', () => ({ db: {} }));

describe('findMatchOrEnqueue', () => {
  it('returns waiting when no candidate', async () => {
    const res = await findMatchOrEnqueue('u1');
    expect(res.status).toBe('waiting');
  });

  it('returns matched when candidate exists', async () => {
    const firestore = require('firebase/firestore');
    // 候補を1件追加（自分以外）
    firestore.getDocs.mockResolvedValueOnce({
      docs: [{ id: 'u2' }],
    });
    const res = await findMatchOrEnqueue('u1');
    expect(res.status).toBe('matched');
    if (res.status === 'matched') expect(res.roomId).toBe('room_mock');
  });
});
