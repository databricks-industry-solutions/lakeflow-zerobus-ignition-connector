import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import ComparisonTable from '../../components/ComparisonTable';

describe('ComparisonTable', () => {
  it('renders all 7 dimension rows', () => {
    render(<ComparisonTable />);

    const dimensions = [
      'Components',
      'Compression',
      'New site onboarding',
      'Scaling',
      'Data format',
      'Query access',
      'Licensing',
    ];

    for (const dim of dimensions) {
      expect(screen.getByText(dim)).toBeInTheDocument();
    }
  });
});
