import React, { useEffect, useLayoutEffect, useState } from 'react';
import { View, Text, FlatList, StyleSheet, TouchableOpacity, Alert } from 'react-native';
import { collection, onSnapshot, orderBy, query } from 'firebase/firestore';
import { db } from '../firebase';
import { useAdmin } from '../hooks/useAdmin';
import { deactivateRoom } from '../services/admin';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

type RootStackParamList = {
  AdminReports: undefined;
  AdminRoom: { roomId: string };
};

type Props = NativeStackScreenProps<RootStackParamList, 'AdminReports'>;

type Report = { id: string; roomId: string; reporterId: string; reason: string; createdAt?: any };

export default function AdminReportsScreen({ navigation }: Props) {
  const isAdmin = useAdmin();
  const [reports, setReports] = useState<Report[]>([]);

  useLayoutEffect(() => {
    navigation.setOptions({ headerTitle: '管理: 通報一覧' });
  }, [navigation]);

  useEffect(() => {
    if (!isAdmin) return;
    const q = query(collection(db, 'reports'), orderBy('createdAt', 'desc'));
    const unsub = onSnapshot(q, (snap) => {
      const list: Report[] = [];
      snap.forEach((d) => list.push({ id: d.id, ...(d.data() as any) }));
      setReports(list);
    });
    return () => unsub();
  }, [isAdmin]);

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
        data={reports}
        keyExtractor={(item) => item.id}
        ItemSeparatorComponent={() => <View style={styles.sep} />}
        renderItem={({ item }) => (
          <View style={styles.row}>
            <View style={{ flex: 1 }}>
              <Text style={styles.title}>部屋: {item.roomId}</Text>
              <Text>通報者: {item.reporterId}</Text>
              <Text>理由: {item.reason}</Text>
            </View>
            <View style={styles.actions}>
              <TouchableOpacity style={[styles.btn, { backgroundColor: '#e91e63' }]} onPress={() => navigation.navigate('AdminRoom', { roomId: item.roomId })}>
                <Text style={styles.btnText}>開く</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.btn, { backgroundColor: '#9e9e9e' }]}
                onPress={async () => {
                  try {
                    await deactivateRoom(item.roomId);
                    Alert.alert('部屋を停止しました');
                  } catch (e) {
                    Alert.alert('エラー', '停止に失敗しました');
                  }
                }}
              >
                <Text style={styles.btnText}>停止</Text>
              </TouchableOpacity>
            </View>
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
  row: { flexDirection: 'row', alignItems: 'flex-start', gap: 12 },
  title: { fontWeight: 'bold' },
  actions: { gap: 8 },
  btn: { paddingHorizontal: 12, paddingVertical: 8, borderRadius: 8 },
  btnText: { color: 'white' },
});

