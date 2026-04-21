import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import SkeletonLoader from '../../components/SkeletonLoader';

describe('SkeletonLoader', () => {
  it('renders placeholder animation', () => {
    const { container } = render(<SkeletonLoader />);

    const skeleton = container.querySelector('.animate-pulse');
    expect(skeleton).toBeInTheDocument();
  });

  it('renders multiple rows when count specified', () => {
    const { container } = render(<SkeletonLoader rows={3} />);

    const bars = container.querySelectorAll('.animate-pulse > div');
    expect(bars.length).toBeGreaterThanOrEqual(3);
  });
});
