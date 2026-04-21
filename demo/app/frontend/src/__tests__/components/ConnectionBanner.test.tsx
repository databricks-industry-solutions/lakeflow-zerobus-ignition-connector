import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import ConnectionBanner from '../../components/ConnectionBanner';

describe('ConnectionBanner', () => {
  it('renders "Connection Lost" text when connection is down', () => {
    render(<ConnectionBanner connected={false} />);

    expect(screen.getByText(/Connection Lost/i)).toBeInTheDocument();
  });

  it('is hidden when connection is healthy', () => {
    const { container } = render(<ConnectionBanner connected={true} />);

    expect(screen.queryByText(/Connection Lost/i)).not.toBeInTheDocument();
    // Component should render nothing or be hidden
    expect(container.firstChild).toBeNull();
  });
});
