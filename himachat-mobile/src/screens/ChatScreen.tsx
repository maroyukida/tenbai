import React, { useEffect, useMemo, useRef, useState } from 'react';
import { View, Text, FlatList, StyleSheet, Alert, TouchableOpacity } from 'react-native';
import { auth, db } from '../firebase';
import MessageBubble from '../components/MessageBubble';
import MessageInput from '../components/MessageInput';
import { heartbeat, reportRoom, sendMessage, leaveRoom, setTyping } from '../services/matchmaker';
import { checkMessage } from '../utils/moderation';
import { MAX_MESSAGE_LENGTH, SEND_COOLDOWN_MS } from '../config';
import { blockUser } from '../services/profile';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import {
  collection,
  doc,
  onSnapshot,
  orderBy,
  query,
  serverTimestamp,
  Timestamp,
  limit,
  getDoc,
} from 'firebase/firestore';

type RootStackParamList = {
  FindMatch: undefined;
  Chat: { roomId: string };
};

type Props = NativeStackScreenProps<RootStackParamList, 'Chat'>;

type Msg = { id: string; text: string; senderId: string; createdAt?: Timestamp };

export default function ChatScreen({ route, navigation }: Props) {
  const { roomId } = route.params;
  const uid = auth.currentUser?.uid!;
  const [messages, setMessages] = useState<Msg[]>([]);
  const [online, setOnline] = useState(false);
  const [otherTyping, setOtherTyping] = useState(false);
  const lastSentAtRef = useRef<number>(0);
  const typingTimerRef = useRef<any>();

  useEffect(() => {
    navigation.setOptions({
      headerTitle: 'ぽっちゃりチャット',
      headerLeft: () => (
        <TouchableOpacity
          onPress={() => {
            Alert.alert('退室', 'このチャットを終了しますか？', [
              { text: 'キャンセル', style: 'cancel' },
              {
                text: '退室',
                style: 'destructive',
                onPress: async () => {
                  await leaveRoom(roomId, uid);
                  navigation.popToTop();
                },
              },
            ]);
          }}
          style={{ marginLeft: 8 }}
        >
          <Text style={{ color: '#e91e63', fontWeight: 'bold' }}>退室</Text>
        </TouchableOpacity>
      ),
      headerRight: () => (
        <TouchableOpacity
          onPress={() => {
            Alert.alert('通報', '不適切な内容を通報しますか？', [
              { text: 'キャンセル', style: 'cancel' },
              {
                text: '通報する',
                style: 'destructive',
                onPress: async () => {
                  try {
                    await reportRoom(roomId, uid, 'inappropriate');
                    Alert.alert('ありがとうございます', '通報を受け付けました。');
                  } catch (e) {
                    Alert.alert('エラー', '通報に失敗しました');
                  }
                },
              },
              {
                text: 'ブロック',
                onPress: async () => {
                  try {
                    // 相手UIDを取得
                    const roomSnap = await getDoc(doc(db, 'rooms', roomId));
                    const participants: string[] = (roomSnap.data() as any)?.participants || [];
                    const other = participants.find((p) => p !== uid);
                    if (!other) return;
                    await blockUser(uid, other);
                    Alert.alert('ブロックしました', 'この相手とはマッチングされません');
                    await leaveRoom(roomId, uid);
                    navigation.popToTop();
                  } catch (e) {
                    Alert.alert('エラー', 'ブロックに失敗しました');
                  }
                },
              },
            ]);
          }}
          style={{ marginRight: 12 }}
        >
          <Text style={{ color: '#e91e63', fontWeight: 'bold' }}>通報</Text>
        </TouchableOpacity>
      ),
    });
  }, [navigation, roomId, uid]);

  useEffect(() => {
    const q = query(collection(db, 'rooms', roomId, 'messages'), orderBy('createdAt', 'asc'), limit(100));
    const unsub = onSnapshot(q, (snap) => {
      const list: Msg[] = [];
      snap.forEach((d) => list.push({ id: d.id, ...(d.data() as any) }));
      setMessages(list);
    });
    return () => unsub();
  }, [roomId]);

  useEffect(() => {
    const interval = setInterval(() => heartbeat(roomId, uid), 20_000);
    heartbeat(roomId, uid);
    return () => clearInterval(interval);
  }, [roomId, uid]);

  useEffect(() => {
    // 相手のオンライン判定
    let unsub: any;
    (async () => {
      const roomSnap = await getDoc(doc(db, 'rooms', roomId));
      const participants: string[] = (roomSnap.data() as any)?.participants || [];
      const other = participants.find((p) => p !== uid);
      if (!other) return;
      unsub = onSnapshot(doc(db, 'rooms', roomId, 'presence', other), (s) => {
        const last = (s.data() as any)?.lastActive?.toDate?.() as Date | undefined;
        if (!last) return setOnline(false);
        setOnline(Date.now() - last.getTime() < 30_000);
      });
    })();
    return () => unsub && unsub();
  }, [roomId, uid]);

  useEffect(() => {
    // 相手のタイピング監視
    let unsub: any;
    (async () => {
      const roomSnap = await getDoc(doc(db, 'rooms', roomId));
      const participants: string[] = (roomSnap.data() as any)?.participants || [];
      const other = participants.find((p) => p !== uid);
      if (!other) return;
      unsub = onSnapshot(doc(db, 'rooms', roomId, 'typing', other), (s) => {
        const d = s.data() as any;
        if (!d?.typing) return setOtherTyping(false);
        const t = d?.updatedAt?.toDate?.();
        if (!t) return setOtherTyping(false);
        setOtherTyping(Date.now() - t.getTime() < 5000);
      });
    })();
    return () => unsub && unsub();
  }, [roomId, uid]);

  const onSend = async (text: string) => {
    try {
      const now = Date.now();
      if (now - lastSentAtRef.current < SEND_COOLDOWN_MS) {
        Alert.alert('少し待ってから送信してください');
        return;
      }
      const checked = checkMessage(text);
      if (!checked.ok) {
        Alert.alert('送信できません', checked.reason);
        return;
      }
      await sendMessage(roomId, uid, checked.text);
      lastSentAtRef.current = now;
      // 送信後はタイピングOFF
      try { await setTyping(roomId, uid, false); } catch {}
    } catch (e) {
      Alert.alert('エラー', '送信に失敗しました');
    }
  };

  return (
    <View style={styles.container}>
      <View style={styles.headerRow}>
        <View style={[styles.dot, { backgroundColor: online ? '#4caf50' : '#9e9e9e' }]} />
        <Text>{online ? 'オンライン' : 'オフライン'}</Text>
        {otherTyping && <Text style={styles.typing}>（入力中…）</Text>}
      </View>
      <FlatList
        style={{ flex: 1 }}
        contentContainerStyle={{ padding: 12 }}
        data={messages}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => (
          <MessageBubble text={item.text} mine={item.senderId === uid} />
        )}
      />
      <MessageInput
        onSend={onSend}
        maxLength={MAX_MESSAGE_LENGTH}
        onChangeText={(t) => {
          if (typingTimerRef.current) clearTimeout(typingTimerRef.current);
          // 入力開始でON
          setTyping(roomId, uid, true).catch(() => {});
          // 一定時間入力が無ければOFF
          typingTimerRef.current = setTimeout(() => setTyping(roomId, uid, false).catch(() => {}), 1500);
        }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fafafa' },
  headerRow: { flexDirection: 'row', alignItems: 'center', gap: 8, padding: 8, borderBottomWidth: StyleSheet.hairlineWidth, borderColor: '#ddd' },
  dot: { width: 10, height: 10, borderRadius: 5 },
  typing: { marginLeft: 8, color: '#e91e63' },
});
