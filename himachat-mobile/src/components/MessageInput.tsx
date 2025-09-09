import React, { useState } from 'react';
import { View, TextInput, TouchableOpacity, Text, StyleSheet } from 'react-native';

type Props = {
  onSend: (text: string) => void;
  disabled?: boolean;
  maxLength?: number;
  onChangeText?: (text: string) => void;
};

export default function MessageInput({ onSend, disabled, maxLength, onChangeText }: Props) {
  const [value, setValue] = useState('');
  const send = () => {
    const t = value.trim();
    if (!t) return;
    onSend(t);
    setValue('');
  };
  return (
    <View style={styles.row}>
      <TextInput
        style={styles.input}
        placeholder="メッセージを入力"
        value={value}
        onChangeText={(t) => { setValue(t); onChangeText?.(t); }}
        editable={!disabled}
        maxLength={maxLength}
      />
      <TouchableOpacity style={[styles.btn, disabled && { opacity: 0.5 }]} onPress={send} disabled={disabled}>
        <Text style={styles.btnText}>送信</Text>
      </TouchableOpacity>
      {!!maxLength && (
        <Text style={styles.counter}>{value.length}/{maxLength}</Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', padding: 8, gap: 8, borderTopWidth: StyleSheet.hairlineWidth, borderColor: '#ddd' },
  input: { flex: 1, backgroundColor: 'white', borderWidth: 1, borderColor: '#ddd', borderRadius: 8, paddingHorizontal: 12, height: 44 },
  btn: { height: 44, paddingHorizontal: 16, backgroundColor: '#1976d2', borderRadius: 8, alignItems: 'center', justifyContent: 'center' },
  btnText: { color: 'white', fontWeight: 'bold' },
  counter: { marginLeft: 4, color: '#888', fontSize: 12 },
});
