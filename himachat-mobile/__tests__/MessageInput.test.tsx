import React from 'react';
import { fireEvent, render } from '@testing-library/react-native';
import MessageInput from '../src/components/MessageInput';

describe('MessageInput', () => {
  it('calls onSend and clears input', () => {
    const onSend = jest.fn();
    const { getByPlaceholderText, getByText } = render(<MessageInput onSend={onSend} />);
    const input = getByPlaceholderText('メッセージを入力');
    fireEvent.changeText(input, 'テスト');
    fireEvent.press(getByText('送信'));
    expect(onSend).toHaveBeenCalledWith('テスト');
  });
});

