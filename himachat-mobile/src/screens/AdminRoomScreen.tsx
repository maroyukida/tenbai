import React, { useEffect, useLayoutEffect, useState } from 'react';
import { View, Text, FlatList, StyleSheet, TouchableOpacity, Alert } from 'react-native';
import { collection, doc, onSnapshot, orderBy, query } from 'firebase/firestore';
import { db } from '../firebase';
import { useAdmin } from '../hooks/useAdmin';
import { deleteMessage } from '../services/admin';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

type RootStackParamList = {
  AdminRoom: { roomId: string };
};

type Props = NativeStackScreenProps<RootStackParamList, 'AdminRoom'>;

type Msg = { id: string; text: string; senderId: string };

export default function AdminRoomScreen({ route, navigation }: Props) {
  const { roomId } = route.params;
  const isAdmin = useAdmin();
  const [messages, setMessages] = useState<Msg[]>([]);

  useLayoutEffect(() => {
    navigation.setOptions({ headerTitle: `管理: 部屋 ${roomId}` });
  }, [navigation, roomId]);

  useEffect(() => {
    if (!isAdmin) return;
    const q = query(collection(db, 'rooms', roomId, 'messages'), orderBy('createdAt', 'asc'));
    const unsub = onSnapshot(q, (snap) => {
      const list: Msg[] = [];
      snap.forEach((d) => list.push({ id: d.id, ...(d.data() as any) }));
      setMessages(list);
    });
    return () => unsub();
  }, [isAdmin, roomId]);

  if (!isAdmin) {
    return (
      <View style={styles.center}>
        <Text>管理者専用画面です</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <FlatList
        data={messages}
        keyExtractor={(item) => item.id}
        ItemSeparatorComponent={() => <View style={styles.sep} />}
        renderItem={({ item }) => (
          <View style={styles.row}>
            <View style={{ flex: 1 }}>
              <Text style={styles.msg}>{item.text}</Text>
              <Text style={styles.meta}>from {item.senderId}</Text>
            </View>
            <TouchableOpacity
              style={styles.btn}
              onPress={async () => {
                try {
                  await deleteMessage(roomId, item.id);
                } catch (e) {
                  Alert.alert('エラー', '削除に失敗しました');
                }
              }}
            >
              <Text style={styles.btnText}>削除</Text>
            </TouchableOpacity>
          </View>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff', padding: 12 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  sep: { height: 1, backgroundColor: '#eee', marginVertical: 8 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  msg: { fontSize: 16 },
  meta: { color: '#777', fontSize: 12 },
  btn: { backgroundColor: '#9e9e9e', paddingHorizontal: 12, paddingVertical: 8, borderRadius: 8 },
  btnText: { color: 'white' },
});

