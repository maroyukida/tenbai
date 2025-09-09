import React from 'react';
import { render } from '@testing-library/react-native';
import MessageBubble from '../src/components/MessageBubble';

describe('MessageBubble', () => {
  it('renders text', () => {
    const { getByText } = render(<MessageBubble text="こんにちは" />);
    expect(getByText('こんにちは')).toBeTruthy();
  });

  it('applies mine style when mine=true', () => {
    const { getByText } = render(<MessageBubble text="自分です" mine />);
    const node = getByText('自分です');
    expect(node).toBeTruthy();
  });
});

