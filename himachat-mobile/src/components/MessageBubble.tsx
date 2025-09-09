import React from 'react';
import { View, Text, StyleSheet } from 'react-native';

type Props = {
  text: string;
  mine?: boolean;
};

export default function MessageBubble({ text, mine }: Props) {
  return (
    <View style={[styles.wrap, mine ? styles.mine : styles.theirs]}>
      <Text style={[styles.text, mine ? styles.mineText : styles.theirsText]}>{text}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    maxWidth: '80%',
    marginVertical: 4,
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 12,
  },
  mine: {
    alignSelf: 'flex-end',
    backgroundColor: '#e91e63',
  },
  theirs: {
    alignSelf: 'flex-start',
    backgroundColor: '#e0e0e0',
  },
  text: { fontSize: 16 },
  mineText: { color: 'white' },
  theirsText: { color: '#111' },
});
